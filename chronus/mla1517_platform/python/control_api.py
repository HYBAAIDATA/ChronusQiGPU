#!/usr/bin/env python3
"""PYTHIA control API with typed, auditable worker startup contracts."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import mimetypes
import os
import re
import signal
import subprocess
import sys
import threading
import time
import traceback
from dataclasses import dataclass
from dataclasses import field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs
from urllib.parse import unquote
from urllib.parse import urlparse

import runtime_config
import system_fabric
import autonomous_supervisor
from startup_contract import METRICS
from startup_contract import AppendOnlyAudit
from startup_contract import BootLock
from startup_contract import StartupConfigError
from startup_contract import WorkerRecord
from startup_contract import fs_selfcheck
from startup_contract import identity_hmac_status
from startup_contract import now_iso
from startup_contract import resolve_stratum_identity

try:
    from al_haras_pythia import pythia_guardian_api
except ModuleNotFoundError as exc:
    if exc.name != "al_haras":
        raise
    pythia_guardian_api = None
from worker_lifecycle import HeartbeatReader

_SCHEMA_VERSION = "chronus.mla1517.status/1"
_READY_SCHEMA_VERSION = "chronus.mla1517.ready/1"
_TOE_SCHEMA_VERSION = "chronus.mla1517.toe_collapse/1"
_TOE_MAX_BODY_BYTES = 4 * 1024 * 1024
_STATUS_BACKEND = "Python/C/OpenCL"
_CANONICAL_DEVICE = "canonical-python-backend"
PRIVILEGED_MEDIATION_INSTALLED = True
_PRIVILEGED_PREFIXES = (
    "/api/v1/mining/",
    "/api/v1/policy/",
    "/api/v1/worker/",
    "/api/v1/recovery/",
    "/api/v1/admin/",
    "/api/v1/toe/",
    "/api/v1/quantum/",
    "/api/v1/scale/",
    "/api/v1/assembly/",
    "/api/v1/security/",
)
from lucas.ladder import FULL_LADDER

_EXACT_LADDER = list(FULL_LADDER)
_MAX_RESTARTS_WINDOW = 5
_RESTART_WINDOW_SECONDS = 600
_WORKER_SPECS = {
    "agentic-mining": "mining_runtime.py",
    "salamander": "salamander_engine.py",
    "discovery": "discovery_runtime.py",
}
# Workers that drive the mining device. The discovery worker experiments on a
# simulated twin, so it runs (and learns) on a host with no device bound.
_DEVICE_WORKERS = frozenset({"agentic-mining", "salamander"})
# With PYTHIA_EXECUTION_DEVICE declared, the mining worker drives the
# Execution Router directly (OpenCL or the labelled CPU reference) and needs
# no MMIO bridge. Salamander supervises the bridge, so it still waits for one.
_EXECUTION_DEVICE_WORKERS = frozenset({"agentic-mining"})
_EXECUTION_DEVICES = ("opencl", "cpu")
_LOCK_HELD = False
_LOCK_GUARD = threading.Lock()
_AUDIT: AppendOnlyAudit | None = None
_BOOT_LOCK: BootLock | None = None
_CONTROL: "ControlPlane" | None = None
_CONTROL_GUARD = threading.Lock()

_PY_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _PY_DIR.parent.parent.parent
_REPO_ROOT = _PROJECT_ROOT.parent

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_GPU_CACHE: dict[str, Any] = {"at": 0.0, "payload": None}
_GPU_CACHE_TTL_S = 30.0
_TOE_BRIDGE: Any = None
_TOE_BRIDGE_GUARD = threading.Lock()


def gpu_payload() -> dict[str, Any]:
    """Full GPU truth surface: logical substrate and observed host backends.

    Result is cached for ``_GPU_CACHE_TTL_S`` so the 5 s UI poll does not
    pay OpenCL enumeration + hasher/punch init on every tick. Failures
    degrade to an unavailable substrate — never raise, never invent.
    """
    now = time.monotonic()
    cached = _GPU_CACHE.get("payload")
    if cached is not None and (now - float(_GPU_CACHE.get("at", 0.0))) < _GPU_CACHE_TTL_S:
        return cached
    payload: dict[str, Any] = {
        "available": False,
        "count": 0,
        "opencl_device_count": 0,
        "physical_gpu_available": False,
        "physical_gpu_count": 0,
        "devices": [],
        "logical_substrate": {
            "name": "hyba-super-gpu",
            "available": False,
            "active": False,
            "host_backend": "none",
            "fallback_used": False,
        },
    }
    try:
        from chronus.report import report as _gpu_report

        doc = _gpu_report()
        devices = []
        if isinstance(doc.get("opencl"), dict):
            devices = doc["opencl"].get("devices") or []
        gpu_devices = [
            device
            for device in devices
            if isinstance(device, dict) and bool(device.get("is_gpu", False))
        ]
        hasher = doc.get("hasher") if isinstance(doc.get("hasher"), dict) else {}
        punch = doc.get("punch") if isinstance(doc.get("punch"), dict) else {}
        vendors = doc.get("vendors") if isinstance(doc.get("vendors"), dict) else {}
        detected_backend = str(hasher.get("backend") or punch.get("backend") or "none")
        substrate_available = detected_backend == "cpu" or detected_backend.startswith("opencl:")
        fallback_used = bool(hasher.get("fallback_reason"))
        member_count = len(devices) + int(detected_backend == "cpu")
        payload = {
            "available": substrate_available,
            "count": member_count,
            "opencl_device_count": len(devices),
            "physical_gpu_available": bool(gpu_devices),
            "physical_gpu_count": len(gpu_devices),
            "devices": devices,
            "backend_active": False,
            "detected_backend": detected_backend,
            "detected_device": str(hasher.get("device") or ""),
            "logical_substrate": {
                "name": "hyba-super-gpu",
                "available": substrate_available,
                "active": False,
                "host_backend": detected_backend,
                "fallback_used": fallback_used,
            },
            "hasher": hasher,
            "punch": {
                "use_opencl": bool(punch.get("use_opencl", False)),
                "backend": str(punch.get("backend") or "none"),
                "gpu_error": punch.get("gpu_error"),
            },
            "vendors": vendors,
            "generated_at": now_iso(),
        }
    except Exception as exc:
        payload["error"] = f"{type(exc).__name__}: {exc}"
    _GPU_CACHE["at"] = now
    _GPU_CACHE["payload"] = payload
    return payload


def _load_env_file() -> None:
    """Populate os.environ from the repo .env so config is always present —
    no separate loader step. Process env wins; .env only fills gaps."""
    env_file = _PROJECT_ROOT / ".env"
    if not env_file.is_file():
        return
    loaded = 0
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip()
        value = value.strip()
        if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        if name.isidentifier() and name not in os.environ:
            os.environ[name] = value
            loaded += 1
    if loaded:
        print(f"[pythia-control] loaded {loaded} vars from {env_file.name}")


class RestartBudgetExhausted(RuntimeError):
    """Raised when a worker exceeds the allowed restart window and must fail closed."""


@dataclass
class WorkerHandle:
    record: WorkerRecord
    script: Path
    reader: HeartbeatReader
    restarts: list[float] = field(default_factory=list)
    process: subprocess.Popen[str] | None = None


def _ensure_boot_lock() -> None:
    global _LOCK_HELD
    with _LOCK_GUARD:
        if _LOCK_HELD:
            return
        _LOCK_HELD = _boot_lock().acquire()
        if not _LOCK_HELD:
            raise RuntimeError("canonical control plane already running")
        _audit().append("control_api_boot_lock_acquired", pid=os.getpid())


def _audit() -> AppendOnlyAudit:
    global _AUDIT
    if _AUDIT is None:
        path = os.getenv("PYTHIA_BOOT_AUDIT", "/tmp/pythia/BOOT_AUDIT.log")
        _AUDIT = AppendOnlyAudit(path)
    return _AUDIT


def _boot_lock() -> BootLock:
    global _BOOT_LOCK
    if _BOOT_LOCK is None:
        path = os.getenv("PYTHIA_BOOT_LOCK", "/tmp/pythia/pythia-main.lock")
        _BOOT_LOCK = BootLock(path)
    return _BOOT_LOCK


def _heartbeat_dir() -> Path:
    raw = os.getenv("PYTHIA_WORKER_HEARTBEAT_DIR", "/run/pythia/hb")
    return Path(raw)


def _metrics_path(worker_id: str) -> Path:
    return _heartbeat_dir() / f"{worker_id}.metrics.json"


def _is_truthy(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() not in {"", "0", "false", "no", "off"}


def _worker_ids() -> list[str]:
    configured = [
        item.strip()
        for item in os.getenv(
            "PYTHIA_CONTROL_WORKERS", "agentic-mining,salamander,discovery"
        ).split(",")
        if item.strip()
    ]
    return [worker_id for worker_id in configured if worker_id in _WORKER_SPECS]


def _execution_device_env() -> str:
    value = os.getenv("PYTHIA_EXECUTION_DEVICE", "").strip().lower()
    if value and value not in _EXECUTION_DEVICES:
        raise StartupConfigError(
            f"PYTHIA_EXECUTION_DEVICE must be one of {', '.join(_EXECUTION_DEVICES)}"
        )
    return value


def _read_metrics(worker_id: str) -> dict[str, Any]:
    path = _metrics_path(worker_id)
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    counters = payload.get("counters")
    return counters if isinstance(counters, dict) else {}


def _measured_hashrate(metrics: dict[str, Any]) -> float | None:
    """Worker hashrate from its metrics sidecar; ``None`` when not measured."""
    try:
        value = float(metrics["hashrate_hs"])
    except (KeyError, TypeError, ValueError):
        return None
    return value if math.isfinite(value) and value >= 0.0 else None


def _total_hashrate(records: list[WorkerRecord]) -> float | None:
    """Sum of measured worker hashrates; ``None`` when no worker measured one."""
    measured = [record.hashrate for record in records if record.hashrate is not None]
    return sum(measured) if measured else None


def _refresh_evidence(record: WorkerRecord) -> WorkerRecord:
    """Update a worker record from authenticated heartbeat and measured counters."""
    evidence = HeartbeatReader(record.worker_id).poll()
    kind = str(evidence.get("kind"))
    record.last_heartbeat = now_iso() if kind in {"fresh", "epoch_change", "stale"} else None
    record.liveness = kind in {"fresh", "epoch_change", "stale"}
    metrics = _read_metrics(record.worker_id)
    record.hashrate = _measured_hashrate(metrics)
    try:
        record.shares_accepted = int(metrics.get("shares_accepted", record.shares_accepted) or 0)
    except (TypeError, ValueError):
        record.shares_accepted = 0
    record.readiness = record.liveness and record.state in {"ready", "running", "starting"}
    if kind not in {"fresh", "epoch_change", "stale", "missing"}:
        record.last_error = {"kind": kind}
    if backend := metrics.get("backend"):
        record.last_error = None if record.last_error and kind == "fresh" else record.last_error
        METRICS.set(
            f'pythia_worker_backend_info{{name="{record.worker_id}",backend="{backend}"}}', 1.0
        )
    return record


class ControlPlane:
    def __init__(self) -> None:
        self.audit = _audit()
        self.started_monotonic = time.monotonic()
        self.started_at = now_iso()
        self.python_root = Path(__file__).resolve().parent
        self.heartbeat_dir = _heartbeat_dir()
        self.heartbeat_dir.mkdir(parents=True, exist_ok=True)
        self.identity = resolve_stratum_identity()
        self.fs_contract = fs_selfcheck(self.heartbeat_dir, self.audit)
        self.handles: dict[str, WorkerHandle] = {
            worker_id: WorkerHandle(
                record=WorkerRecord(worker_id, script_name, "disabled"),
                script=self.python_root / script_name,
                reader=HeartbeatReader(worker_id),
            )
            for worker_id, script_name in (
                (worker_id, _WORKER_SPECS[worker_id]) for worker_id in _worker_ids()
            )
        }
        self.stop_event = threading.Event()
        self.lock = threading.RLock()
        self.autostart = _is_truthy(os.getenv("PYTHIA_AUTOSTART_WORKERS"), default=True)
        self.mmio_device = os.getenv("MLA1517_MMIO_DEVICE", "").strip()
        self.execution_device = _execution_device_env()
        self.audit.append(
            "control_api_initialized",
            workers=list(self.handles),
            autostart=self.autostart,
            mmio_device=bool(self.mmio_device),
            execution_device=self.execution_device or None,
            stratum=self.identity.public(),
            alias_policy=os.getenv("PYTHIA_ALIAS_POLICY", "compat").strip().lower() or "compat",
        )
        self._prime_worker_states()
        self.ensure_workers()

    def _prime_worker_states(self) -> None:
        for handle in self.handles.values():
            if not self.autostart:
                handle.record.state = "disabled"
            elif not self._device_ready(handle):
                handle.record.state = "armed_no_device"
            else:
                handle.record.state = "stopped"

    def mining_device_bound(self) -> bool:
        return bool(self.mmio_device) or bool(self.execution_device)

    def _device_ready(self, handle: WorkerHandle) -> bool:
        worker_id = handle.record.worker_id
        if worker_id not in _DEVICE_WORKERS or self.mmio_device:
            return True
        return bool(self.execution_device) and worker_id in _EXECUTION_DEVICE_WORKERS

    def ensure_workers(self) -> None:
        with self.lock:
            for handle in self.handles.values():
                self._ensure_worker(handle)

    def _ensure_worker(self, handle: WorkerHandle) -> None:
        if self.stop_event.is_set():
            return
        if not self.autostart:
            return
        if not self._device_ready(handle):
            return
        if handle.process is not None and handle.process.poll() is None:
            return
        if handle.process is not None:
            returncode = handle.process.poll()
            if returncode is not None:
                handle.record.last_error = {
                    "kind": "worker_exit",
                    "message": f"{handle.record.worker_id} exited with code {returncode}",
                }
        self._consume_restart_budget(handle)
        if handle.record.state in {"disabled", "armed_no_device", "stopped", "failed"}:
            handle.record.transition("starting", self.audit, "spawn_worker")
        elif handle.record.state == "running":
            handle.record.transition("restarting", self.audit, "respawn_worker")
            handle.record.transition("starting", self.audit, "respawn_worker")
        elif handle.record.state == "restarting":
            handle.record.transition("starting", self.audit, "respawn_worker")
        handle.record.attempts_total += 1
        handle.record.attempts_window = len(handle.restarts)
        env = os.environ.copy()
        env.setdefault("PYTHONPATH", str(self.python_root))
        # Workers inherit the service's stdout/stderr so a container log
        # shows why a worker exited; the restart budget still bounds it.
        handle.process = subprocess.Popen(
            [sys.executable, str(handle.script)],
            cwd=str(self.python_root),
            env=env,
            text=True,
        )
        self.audit.append(
            "worker_spawned",
            worker=handle.record.worker_id,
            pid=handle.process.pid,
            script=handle.script.name,
        )

    def _consume_restart_budget(self, handle: WorkerHandle) -> None:
        now = time.time()
        handle.restarts = [
            stamp for stamp in handle.restarts if now - stamp <= _RESTART_WINDOW_SECONDS
        ]
        if len(handle.restarts) >= _MAX_RESTARTS_WINDOW:
            if handle.record.state != "failed":
                if handle.record.state == "stopped":
                    handle.record.transition("starting", self.audit, "restart_budget_exhausted")
                if handle.record.state in {"running", "starting", "restarting"}:
                    handle.record.transition("failed", self.audit, "restart_budget_exhausted")
                else:
                    old = handle.record.state
                    handle.record.state = "failed"
                    handle.record.since = now_iso()
                    self.audit.append(
                        "worker_transition",
                        worker=handle.record.worker_id,
                        from_state=old,
                        to_state="failed",
                        reason="restart_budget_exhausted",
                    )
            METRICS.inc(
                f'pythia_worker_restart_budget_exhaustions_total{{name="{handle.record.worker_id}"}}'
            )
            raise RestartBudgetExhausted(handle.record.worker_id)
        handle.restarts.append(now)

    def records(self) -> list[WorkerRecord]:
        with self.lock:
            self.ensure_workers()
            return [self._refresh_evidence(handle) for handle in self.handles.values()]

    def _refresh_evidence(self, handle: WorkerHandle) -> WorkerRecord:
        record = handle.record
        evidence = handle.reader.poll()
        kind = str(evidence.get("kind"))
        fresh = kind in {"fresh", "epoch_change"}
        record.last_heartbeat = now_iso() if kind in {"fresh", "epoch_change", "stale"} else None
        record.liveness = kind in {"fresh", "epoch_change", "stale"}
        metrics = _read_metrics(record.worker_id)
        record.hashrate = _measured_hashrate(metrics)
        try:
            record.shares_accepted = int(
                metrics.get("shares_accepted", record.shares_accepted) or 0
            )
        except (TypeError, ValueError):
            record.shares_accepted = 0
        if backend := metrics.get("backend"):
            METRICS.set(
                f'pythia_worker_backend_info{{name="{record.worker_id}",backend="{backend}"}}',
                1.0,
            )
        if (
            handle.process is not None
            and handle.process.poll() is not None
            and record.state == "running"
        ):
            record.transition("restarting", self.audit, "worker_process_exited")
        if fresh and record.state == "starting":
            record.transition("ready", self.audit, "heartbeat_authenticated")
            record.transition("running", self.audit, "heartbeat_authenticated")
        elif fresh and record.state == "ready":
            record.transition("running", self.audit, "heartbeat_authenticated")
        elif kind == "stale" and record.state == "starting":
            record.transition("ready", self.audit, "heartbeat_stale")
        record.readiness = record.state in {"ready", "running"} and record.liveness
        if kind not in {"fresh", "epoch_change", "stale", "missing"}:
            record.last_error = {"kind": kind, "message": str(evidence.get("error", kind))}
        elif record.last_error and fresh:
            record.last_error = None
        return record

    def set_autostart(self, enabled: bool) -> None:
        """Operator mining on/off. Re-arms disabled workers to the correct
        pre-start posture; disabling retires live processes."""
        with self.lock:
            self.autostart = enabled
            for handle in self.handles.values():
                record = handle.record
                if enabled:
                    if record.state == "disabled":
                        target = "stopped" if self._device_ready(handle) else "armed_no_device"
                        record.transition(target, self.audit, "mining_start")
                else:
                    self._retire_handle(handle, "mining_stop")
        if enabled:
            self.ensure_workers()

    def _retire_handle(self, handle: WorkerHandle, reason: str) -> None:
        """Terminate a live process and land the record on disabled."""
        record = handle.record
        proc = handle.process
        if proc is not None and proc.poll() is None:
            try:
                record.transition("stopping", self.audit, reason)
            except Exception:
                pass
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)
        handle.process = None
        if record.state != "disabled":
            try:
                if record.state != "stopped":
                    record.transition("stopped", self.audit, reason)
                record.transition("disabled", self.audit, reason)
            except Exception:
                old = record.state
                record.state = "disabled"
                record.since = now_iso()
                self.audit.append(
                    "worker_transition",
                    worker=record.worker_id,
                    from_state=old,
                    to_state="disabled",
                    reason=f"{reason}_forced",
                )

    def stop_workers(self) -> list[str]:
        """Retire every supervised worker and cease supervision."""
        with self.lock:
            self.autostart = False
            retired: list[str] = []
            for handle in self.handles.values():
                had_process = handle.process is not None and handle.process.poll() is None
                self._retire_handle(handle, "mining_stop")
                if had_process or handle.record.state == "disabled":
                    retired.append(handle.record.worker_id)
            return retired

    def restart_running(self) -> list[str]:
        """Bounce live worker processes so they pick up a new runtime config."""
        with self.lock:
            restarted: list[str] = []
            for handle in self.handles.values():
                proc = handle.process
                if proc is None or proc.poll() is not None:
                    continue
                self._retire_handle(handle, "config_restart")
                restarted.append(handle.record.worker_id)
            if self.autostart and self.mining_device_bound():
                for handle in self.handles.values():
                    if handle.record.worker_id in restarted:
                        try:
                            handle.record.transition(
                                "armed_no_device", self.audit, "config_restart"
                            )
                        except Exception:
                            pass
                        self._ensure_worker(handle)
            return restarted

    def shutdown(self) -> None:
        self.stop_event.set()
        with self.lock:
            for handle in self.handles.values():
                proc = handle.process
                if proc is None or proc.poll() is not None:
                    continue
                try:
                    handle.record.transition("stopping", self.audit, "control_api_shutdown")
                except Exception:
                    pass
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=2)
                try:
                    handle.record.transition("stopped", self.audit, "control_api_shutdown")
                except Exception:
                    pass


def _control_plane() -> ControlPlane:
    global _CONTROL
    _ensure_boot_lock()
    with _CONTROL_GUARD:
        if _CONTROL is None:
            _CONTROL = ControlPlane()
        return _CONTROL


def _identity_payload() -> dict[str, Any]:
    ok, reason = identity_hmac_status()
    return {"ok": ok, "reason": reason}


def _stratum_status_payload(
    control: ControlPlane,
    records: list[WorkerRecord],
) -> dict[str, Any]:
    identity = control.identity.public()
    endpoint = f"{identity['host']}:{identity['port']}"
    fallback: dict[str, Any] = {
        "schema": "chronus.mla1517.stratum/1",
        "state": "CONFIGURED",
        "ready": False,
        "connected": False,
        "status": "runtime_evidence_unavailable",
        "evidence_available": False,
        "primary": {
            "configured": True,
            "pool_id": identity["profile"],
            "transport": "DISCONNECTED",
            "subscribed": False,
            "authorized": False,
            "endpoint": endpoint,
            "worker": identity["user_redacted"],
            "connected_at": None,
            "last_message_at": None,
            "last_error": "runtime evidence unavailable",
        },
        "job": {
            "active": False,
            "generation": None,
            "invalidated_generation": None,
            "job_id": None,
            "fingerprint": None,
            "received_at": None,
            "age_ms": None,
            "clean_jobs": None,
            "difficulty": None,
            "difficulty_source": None,
            "difficulty_received_at": None,
            "share_target": None,
            "target_generation": 0,
        },
        "submission": {
            "state": "IDLE",
            "last_result": None,
            "last_submit_at": None,
            "last_response_at": None,
            "generation": None,
            "job_id": None,
            "job_fingerprint": None,
        },
        "counters": {
            "jobs_received": 0,
            "jobs_invalidated": 0,
            "disconnects": 0,
            "submitted": 0,
            "accepted": 0,
            "rejected": 0,
            "unknown": 0,
        },
    }
    raw = _read_metrics("agentic-mining").get("stratum_status")
    try:
        observed = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError):
        return fallback
    if not isinstance(observed, dict):
        return fallback
    primary = observed.get("primary")
    job = observed.get("job")
    submission = observed.get("submission")
    counters = observed.get("counters")
    if not all(isinstance(item, dict) for item in (primary, job, submission, counters)):
        return fallback

    primary = dict(primary)
    job = dict(job)
    submission = dict(submission)
    counters = dict(counters)
    connected = primary.get("transport") == "CONNECTED"
    active_job = job.get("active") is True and job.get("generation") is not None
    target_available = isinstance(job.get("share_target"), str) and bool(job.get("share_target"))
    worker_live = any(
        record.worker_id == "agentic-mining" and record.liveness for record in records
    )
    ready = (
        worker_live
        and connected
        and primary.get("subscribed") is True
        and primary.get("authorized") is True
        and active_job
        and target_available
    )
    primary["configured"] = True
    primary["transport"] = "CONNECTED" if connected else "DISCONNECTED"
    primary.setdefault("endpoint", endpoint)
    primary.setdefault("worker", identity["user_redacted"])
    state = str(observed.get("state") or "DEGRADED")
    return {
        "schema": "chronus.mla1517.stratum/1",
        "state": state,
        "ready": ready,
        "connected": connected,
        "status": state.lower(),
        "evidence_available": True,
        "primary": primary,
        "job": job,
        "submission": submission,
        "counters": counters,
    }


def _ready_to_mine_reason(
    records: list[WorkerRecord],
    stratum: dict[str, Any],
) -> tuple[bool, str]:
    identity = _identity_payload()
    if not identity["ok"]:
        return False, str(identity["reason"])
    if any(record.state == "failed" for record in records):
        return False, "supervisor_degraded"
    if not any(record.readiness for record in records):
        return False, "worker_unavailable"
    primary = stratum.get("primary", {})
    job = stratum.get("job", {})
    if primary.get("transport") != "CONNECTED":
        return False, "stratum_disconnected"
    if primary.get("subscribed") is not True:
        return False, "stratum_not_subscribed"
    if primary.get("authorized") is not True:
        if stratum.get("state") == "AUTH_FAILED":
            return False, "stratum_auth_failed"
        return False, "stratum_not_authorized"
    if job.get("active") is not True or job.get("generation") is None:
        return False, "stratum_waiting_job"
    if not job.get("share_target"):
        return False, "stratum_target_unavailable"
    if stratum.get("ready") is not True:
        return False, "stratum_not_ready"
    return True, "ok"


MINING_EVIDENCE_SCHEMA = "pythia.mining_evidence/1"


_KNOWLEDGE: Any = None


def knowledge_payload() -> dict[str, Any]:
    """Every intelligence's shared knowledge, replayed from the fabric journal."""
    global _KNOWLEDGE
    from chronus.mla1517.knowledge import KnowledgeFabric
    from chronus.mla1517.knowledge import default_journal_path

    if _KNOWLEDGE is None:
        _KNOWLEDGE = KnowledgeFabric(default_journal_path())
    _KNOWLEDGE.sync()
    return _KNOWLEDGE.snapshot(recent=50)


ADMIN_KEY_ENV = "EUCLID_ADMIN_API_KEY"
UNAUTHENTICATED_ENV = "PYTHIA_ALLOW_UNAUTHENTICATED_CONTROL"


def control_authorization(headers: Any) -> tuple[HTTPStatus, str] | None:
    """None when a state-changing request is authorized, else (status, reason).

    Fail closed: every POST and PUT that changes state (start, stop, switch,
    elevate, escalate, config) needs ``Authorization: Bearer <key>`` matching
    EUCLID_ADMIN_API_KEY. With no key configured nothing may change state,
    unless PYTHIA_ALLOW_UNAUTHENTICATED_CONTROL=1 declares a local dev box.
    """
    key = os.getenv(ADMIN_KEY_ENV, "").strip()
    if not key:
        if _is_truthy(os.getenv(UNAUTHENTICATED_ENV)):
            return None
        return HTTPStatus.FORBIDDEN, f"{ADMIN_KEY_ENV} is not configured; control is closed"
    header = str(headers.get("Authorization", "") or "")
    token = header[7:].strip() if header[:7].lower() == "bearer " else ""
    if not token or not hmac.compare_digest(token.encode("utf-8"), key.encode("utf-8")):
        return HTTPStatus.UNAUTHORIZED, "operator key required"
    return None


def start_repo_engineer() -> bool:
    """Load the repo engineer; an optional service never keeps the control
    API from serving. A failure is audited and printed, and the engineer's
    own route reports it when asked."""
    try:
        system_fabric.initialize_repo_engineer()
        return True
    except Exception as exc:  # noqa: BLE001 - reported, never fatal to the control plane
        _audit().append("repo_engineer_unavailable", error=f"{type(exc).__name__}: {exc}")
        print(f"[pythia-control] repo engineer unavailable: {type(exc).__name__}: {exc}")
        return False


def announce_skills() -> int:
    """Tell every intelligence which skills Salamander holds.

    Publishes each verified skill graft to the knowledge fabric; a rejected
    graft is never announced. The control plane comes up regardless.
    """
    try:
        from chronus.mla1517.knowledge import KnowledgeFabric
        from chronus.mla1517.knowledge import default_journal_path

        from Intelligence.skill_graft import announce

        return len(announce(KnowledgeFabric(default_journal_path())))
    except Exception as exc:  # noqa: BLE001 - reported, never fatal to the control plane
        print(f"[pythia-control] skill announcement failed: {type(exc).__name__}: {exc}")
        return 0


def mining_evidence_payload() -> dict[str, Any]:
    """The live miner's own evidence snapshot, exactly as it published it.

    Nothing is synthesised here: when the miner has not published, or the
    payload is malformed, the answer says evidence is unavailable instead of
    showing zeros. ``worker_live`` states whether the publisher is alive now.
    """
    records = _control_plane().records()
    worker_live = any(
        record.worker_id == "agentic-mining" and record.liveness for record in records
    )
    raw = _read_metrics("agentic-mining").get("mining_evidence")
    try:
        observed = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError):
        observed = None
    if not isinstance(observed, dict) or observed.get("schema") != MINING_EVIDENCE_SCHEMA:
        return {
            "schema": MINING_EVIDENCE_SCHEMA,
            "evidence_available": False,
            "worker_live": worker_live,
            "reason": "the miner has not published evidence",
        }
    return {**observed, "evidence_available": True, "worker_live": worker_live}


def status_payload() -> dict[str, Any]:
    """Public status contract for the canonical operator UI."""
    control = _control_plane()
    records = control.records()
    stratum = _stratum_status_payload(control, records)
    ready, reason = _ready_to_mine_reason(records, stratum)
    total_hashrate = _total_hashrate(records)
    total_shares = sum(record.shares_accepted for record in records)
    worker_map = {record.worker_id: record.public() for record in records}
    device_present = control.mining_device_bound()
    gpu = gpu_payload()
    device_entries = []
    if isinstance(gpu.get("devices"), list) and gpu["devices"]:
        for entry in gpu["devices"]:
            if isinstance(entry, dict):
                device_entries.append(
                    {
                        "platform": str(entry.get("platform") or entry.get("vendor") or ""),
                        "device": str(entry.get("name") or ""),
                        "vendor": str(entry.get("vendor") or ""),
                        "family": entry.get("family"),
                        "dispatch": entry.get("dispatch"),
                        "known": bool(entry.get("known", False)),
                        "hyba_alias": entry.get("hyba_alias"),
                        "is_gpu": bool(entry.get("is_gpu", False)),
                    }
                )
    gpu_available = bool(gpu.get("available", False)) or device_present
    return {
        "schema_version": _SCHEMA_VERSION,
        "generated_at": now_iso(),
        "product": "PYTHIA",
        "backend": _STATUS_BACKEND,
        "measurement": "observed",
        "canonicalEngine": {
            "product": "MLA1517",
            "path": "main.py → control_api.py → chronus/mla1517_platform/python",
            "backend": _STATUS_BACKEND,
            "ladder": _EXACT_LADDER,
            "execution": "canonical_python_control_api",
            "hashrate": "measured",
            "fallback": False,
        },
        "host": {
            "profile": control.identity.profile,
            "stratum": control.identity.public(),
        },
        "solvers": {
            "arms": _desired_arms(),
            "lanes_per_arm": 32,
            "lane_ceiling": 32,
            "nonce_partition": "strict_m32_geometric_partition",
            "hashrate": "measured",
        },
        "runtime": _config_public_payload(),
        "device": {
            "name": _CANONICAL_DEVICE,
            "available": gpu_available,
            "count": int(gpu.get("count", 0) or (1 if device_present else 0)),
            "devices": device_entries,
            "execution_boundary": "canonical_python_control_api",
        },
        "gpu": gpu,
        "workers": worker_map,
        "stratum": stratum,
        "identity": _identity_payload(),
        "ready_to_mine": {
            "ready": ready,
            "reason": reason,
            "details": {
                "hashrate_hs": total_hashrate,
                "shares_accepted": total_shares,
                "workers": list(worker_map),
            },
        },
    }


def _worker_live(records: list[WorkerRecord], worker_id: str = "agentic-mining") -> bool:
    return any(record.worker_id == worker_id and record.liveness for record in records)


def _metrics_json(worker_id: str, key: str) -> Any:
    raw = _read_metrics(worker_id).get(key)
    try:
        return json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError):
        return None


def stratum_status_payload() -> dict[str, Any]:
    """The mining worker's Stratum session (``/api/v1/stratum/status``)."""
    control = _control_plane()
    records = control.records()
    return {
        **_stratum_status_payload(control, records),
        "worker_live": _worker_live(records),
        "generated_at": now_iso(),
    }


def telemetry_events_payload(limit: Any = 100) -> dict[str, Any]:
    """Recent Stratum events the mining worker observed (jobs, targets, shares)."""
    try:
        count = max(1, min(int(limit), 200))
    except (TypeError, ValueError):
        count = 100
    control = _control_plane()
    records = control.records()
    base = {
        "schema": "pythia.telemetry_events/1",
        "generated_at": now_iso(),
        "source": "agentic-mining",
        "worker_live": _worker_live(records),
    }
    observed = _metrics_json("agentic-mining", "stratum_events")
    if not isinstance(observed, dict) or not isinstance(observed.get("events"), list):
        return base | {
            "available": False,
            "reason": "the mining worker has not reported Stratum telemetry",
            "events": [],
            "totals": None,
        }
    return base | {
        "available": True,
        "events": observed["events"][-count:],
        "totals": observed.get("totals"),
        "last_seq": observed.get("last_seq"),
    }


def hardware_status_payload() -> dict[str, Any]:
    """Mining device binding, OpenCL inventory and the worker's live execution."""
    control = _control_plane()
    records = control.records()
    gpu = gpu_payload()
    bound = control.mining_device_bound()
    metrics = _read_metrics("agentic-mining")
    evidence = _metrics_json("agentic-mining", "mining_evidence")
    hashing = None
    if "hashrate_hs" in metrics:
        hashing = {
            key: metrics.get(key)
            for key in ("hashrate_hs", "hashes_total", "executions_total", "backend")
        }
    devices = [
        {
            "name": entry.get("name"),
            "vendor": entry.get("vendor"),
            "family": entry.get("family"),
            "is_gpu": bool(entry.get("is_gpu", False)),
        }
        for entry in gpu.get("devices") or []
        if isinstance(entry, dict)
    ]
    return {
        "schema": "pythia.hardware_status/1",
        "generated_at": now_iso(),
        "mining_device": {
            "bound": bound,
            "mmio_bridge_configured": bool(control.mmio_device),
            "execution_device": control.execution_device or None,
            "reason": (
                None
                if bound
                else _mining_device_reason(control)
                or "no mining device bound — set PYTHIA_EXECUTION_DEVICE=opencl or MLA1517_MMIO_DEVICE"
            ),
        },
        "opencl": {
            "available": bool(gpu.get("available", False)),
            "device_count": int(gpu.get("opencl_device_count", 0) or 0),
            "physical_gpu_count": int(gpu.get("physical_gpu_count", 0) or 0),
            "devices": devices,
            "error": gpu.get("error"),
        },
        "execution": evidence.get("execution_backend") if isinstance(evidence, dict) else None,
        "hashing": hashing,
        "workers": {
            record.worker_id: {"state": record.state, "liveness": record.liveness}
            for record in records
        },
    }


def security_status_payload() -> tuple[HTTPStatus, dict[str, Any]]:
    """AL HARAS public status; 503 only when the guardian cannot exist here."""
    if pythia_guardian_api is None:
        return HTTPStatus.SERVICE_UNAVAILABLE, {
            "available": False,
            "reason": "guardian_dependency_unavailable",
        }
    try:
        return HTTPStatus.OK, pythia_guardian_api().public_status()
    except Exception as exc:  # noqa: BLE001 - reported, never a dropped socket
        return HTTPStatus.SERVICE_UNAVAILABLE, {
            "available": False,
            "reason": f"guardian_unavailable: {type(exc).__name__}: {exc}",
        }


def telemetry_summary_payload() -> dict[str, Any]:
    control = _control_plane()
    records = control.records()
    total_hashrate = _total_hashrate(records)
    total_shares = sum(record.shares_accepted for record in records)
    return {
        "schema_version": _SCHEMA_VERSION,
        "generated_at": now_iso(),
        "backend": _STATUS_BACKEND,
        "hashrate": total_hashrate,
        "shares_accepted": total_shares,
        "session": {
            "supervisor_started_at": control.started_at,
            "uptime_s": round(time.monotonic() - control.started_monotonic, 1),
            "attempts_total": sum(r.attempts_total for r in records),
        },
        "workers": {record.worker_id: record.public() for record in records},
    }


def audit_tail_payload(limit: int = 50) -> dict[str, Any]:
    """Historical telemetry — the append-only operator audit trail."""
    try:
        n = max(1, min(int(limit), 500))
    except (TypeError, ValueError):
        n = 50
    records = _audit().tail(n)
    return {
        "schema": "pythia.audit_tail/1",
        "generated_at": now_iso(),
        "count": len(records),
        "records": records,
    }


def _reason_metrics(records: list[WorkerRecord], stratum: dict[str, Any]) -> str:
    ready, reason = _ready_to_mine_reason(records, stratum)
    reasons = (
        "ok",
        "identity_hmac_missing",
        "identity_hmac_malformed",
        "supervisor_degraded",
        "worker_unavailable",
        "stratum_disconnected",
        "stratum_not_subscribed",
        "stratum_not_authorized",
        "stratum_auth_failed",
        "stratum_waiting_job",
        "stratum_target_unavailable",
        "stratum_not_ready",
    )
    lines = [
        f'pythia_ready_to_mine{{reason="{name}"}} {1 if name == reason else 0}' for name in reasons
    ]
    lines.append(f"pythia_ready_to_mine_value {1 if ready else 0}")
    identity = _identity_payload()
    lines.append(f"pythia_identity_verify_ok {1 if identity['ok'] else 0}")
    for record in records:
        lines.append(f'pythia_worker_up{{name="{record.worker_id}"}} {1 if record.liveness else 0}')
        if record.hashrate is not None:
            lines.append(f'pythia_worker_hashrate{{name="{record.worker_id}"}} {record.hashrate}')
    return "\n".join(lines)


def metrics_payload() -> str:
    control = _control_plane()
    records = control.records()
    stratum = _stratum_status_payload(control, records)
    extra = _reason_metrics(records, stratum)
    runtime = METRICS.prometheus().strip()
    chunks = [chunk for chunk in (runtime, extra) if chunk]
    return "\n".join(chunks) + ("\n" if chunks else "")


# ---------------------------------------------------------------------------
# Operator API: runtime config, system fabric runners, mining verbs.
#
# Every route here is honest — when hardware or a supervisor is absent the
# endpoint reports the gate instead of fabricating a result.
# ---------------------------------------------------------------------------

_CONFIG_SECTIONS = {"pools", "solvers", "hashrate", "live_submit", "window", "campaign"}


def _desired_arms() -> int:
    """Solver arm count: the runtime config file wins once it exists."""
    try:
        if runtime_config.config_path().is_file():
            return int(runtime_config.load().get("solvers", {}).get("arms", 1))
    except Exception:
        pass
    try:
        return max(1, int(os.getenv("PYTHIA_SOLVER_ARMS", "1") or "1"))
    except ValueError:
        return 1


def _live_arm_ids() -> list[str]:
    try:
        return [r.worker_id for r in _control_plane().records() if r.liveness]
    except Exception:
        return []


def _config_public_payload() -> dict[str, Any]:
    cfg = runtime_config.load()
    view = runtime_config.public_view(cfg)
    view["effective_arms"] = int(cfg.get("solvers", {}).get("arms", 1))
    view["live_arms"] = _live_arm_ids()
    return view


def _config_merge_sections(body: dict[str, Any]) -> dict[str, Any]:
    """Overlay the PUT sections onto the stored config.

    Pool rows may omit ``password`` — the stored secret is re-merged by
    endpoint|worker key so the UI never round-trips it. A pools write with
    no explicit live_submit section revokes arming: the approval is bound
    to an identity that may no longer exist.
    """
    cfg = runtime_config.load()
    pools_written = "pools" in body
    if pools_written:
        stored = {
            f"{p['endpoint']}|{p['worker']}": p.get("password", "")
            for p in cfg.get("pools", [])
            if isinstance(p, dict)
        }
        merged_pools = []
        for row in body["pools"] if isinstance(body["pools"], list) else []:
            entry = dict(row) if isinstance(row, dict) else {}
            if not entry.get("password"):
                entry["password"] = stored.get(f"{entry.get('endpoint')}|{entry.get('worker')}", "")
            merged_pools.append(entry)
        cfg["pools"] = merged_pools
    for key in ("solvers", "hashrate"):
        if key in body:
            section = dict(cfg.get(key) or {})
            if isinstance(body[key], dict):
                section.update(body[key])
            cfg[key] = section
    if "window" in body:
        cfg["window"] = body["window"]
    if "campaign" in body:
        cfg["campaign"] = body["campaign"]
    if "live_submit" in body:
        req = body["live_submit"] if isinstance(body["live_submit"], dict) else {}
        enabled = bool(req.get("enabled", False))
        approval = req.get("approval_id", "")
        if not isinstance(approval, str):
            approval = ""
        if enabled and not approval:
            enabled_pool = next((p for p in cfg.get("pools", []) if p.get("enabled")), None)
            if enabled_pool is not None:
                approval = runtime_config.identity_commit(
                    enabled_pool["endpoint"], enabled_pool["worker"]
                )
        cfg["live_submit"] = {"enabled": enabled, "approval_id": approval}
    elif pools_written:
        cfg["live_submit"] = {"enabled": False, "approval_id": ""}
    return cfg


def _apply_runtime_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """Push a saved config at the supervised arms.

    On a box with no mining device there is nothing to respawn — the
    config is durable and the arms stay honestly parked.
    """
    control = _control_plane()
    applied: dict[str, Any] = {"spawned": [], "retired": [], "restarted": []}
    if not control.mining_device_bound():
        applied["note"] = "no mining device — config saved, workers stay armed_no_device"
        return applied
    applied["restarted"] = control.restart_running()
    return applied


def _config_put(body: dict[str, Any]) -> tuple[HTTPStatus, dict[str, Any]]:
    unknown = sorted(set(body) - _CONFIG_SECTIONS)
    if unknown:
        return HTTPStatus.BAD_REQUEST, {"error": f"unknown config sections: {', '.join(unknown)}"}
    try:
        merged = _config_merge_sections(body)
        saved = runtime_config.save(merged)
    except ValueError as exc:
        return HTTPStatus.BAD_REQUEST, {"error": str(exc)}
    applied = _apply_runtime_config(saved)
    _audit().append("runtime_config_applied", sections=sorted(set(body) & _CONFIG_SECTIONS))
    out = runtime_config.public_view(saved)
    out["effective_arms"] = int(saved.get("solvers", {}).get("arms", 1))
    out["live_arms"] = _live_arm_ids()
    return HTTPStatus.OK, {"ok": True, "applied": applied, "config": out}


def _apply_config_dict(cfg: dict[str, Any]) -> dict[str, Any]:
    saved = runtime_config.save(cfg)
    return _apply_runtime_config(saved)


def _retire_all_arms() -> list[str]:
    try:
        return _control_plane().stop_workers()
    except Exception:
        return []


def _arm_counters() -> dict[str, float | None]:
    """Aggregate measured counters across live worker metrics sidecars.

    A worker rewrites its sidecar on every heartbeat tick; a clean exit
    removes the file, so a stale one belongs to a killed arm whose numbers
    must not leak into the campaign record. ``hashrate_hs`` is ``None``
    when no live arm reported one — a measured 0.0 stays distinguishable
    from "nothing was measured".
    """
    totals: dict[str, float | None] = {"hashrate_hs": None, "shares_accepted": 0.0}
    heartbeat_dir = _heartbeat_dir()
    try:
        paths = list(heartbeat_dir.glob("*.metrics.json"))
    except OSError:
        return totals
    try:
        max_age = float(os.getenv("PYTHIA_METRICS_SIDECAR_TTL_S", "30"))
    except ValueError:
        max_age = 30.0
    now = time.time()
    for path in paths:
        try:
            if now - path.stat().st_mtime > max_age:
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        counters = payload.get("counters")
        if not isinstance(counters, dict):
            continue
        rate = counters.get("hashrate_hs")
        if rate is not None:
            try:
                totals["hashrate_hs"] = (totals["hashrate_hs"] or 0.0) + float(rate)
            except (TypeError, ValueError):
                pass
        try:
            totals["shares_accepted"] = (totals["shares_accepted"] or 0.0) + float(
                counters.get("shares_accepted") or 0
            )
        except (TypeError, ValueError):
            continue
    return totals


def _fabric_map_payload() -> dict[str, Any]:
    control = _control_plane()
    gpu = gpu_payload()
    cfg = runtime_config.load()
    return system_fabric.forensic_map(
        opencl_count=int(gpu.get("count", 0) or 0),
        have_mmio=bool(control.mmio_device),
        have_credentials=bool(cfg.get("pools")) or bool(control.identity.user),
    )


def _runner_start(fn: Any) -> tuple[HTTPStatus, dict[str, Any]]:
    try:
        started = fn()
    except ValueError as exc:
        return HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)}
    if not started:
        return HTTPStatus.CONFLICT, {"ok": False, "error": "runner_busy"}
    return HTTPStatus.ACCEPTED, {"ok": True, "state": "running"}


def _runner_stop(runner: Any) -> tuple[HTTPStatus, dict[str, Any]]:
    stopped = runner.stop()
    return HTTPStatus.OK, {"ok": stopped, "state": runner.status()["state"]}


def _repo_engineer_ask(body: dict[str, Any]) -> tuple[HTTPStatus, dict[str, Any]]:
    prompt = body.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 2_000:
        return HTTPStatus.BAD_REQUEST, {"ok": False, "error": "prompt_must_be_1_to_2000_characters"}
    readiness = system_fabric.repo_engineer_status()
    if not readiness["ready"]:
        return (
            HTTPStatus.SERVICE_UNAVAILABLE,
            {"ok": False, "error": "repo_engineer_not_configured", "readiness": readiness},
        )
    try:
        started = system_fabric.start_repo_engineer(prompt)
    except ValueError as exc:
        return HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)}
    if not started:
        return HTTPStatus.CONFLICT, {"ok": False, "error": "runner_busy"}
    return HTTPStatus.ACCEPTED, {"ok": True, "state": "running"}


def _mining_device_reason(control: "ControlPlane") -> str | None:
    """None when a mining device is bound; otherwise the honest reason."""
    if control.mmio_device or getattr(control, "execution_device", ""):
        return None
    gpu = gpu_payload()
    if int(gpu.get("opencl_device_count", 0) or 0) > 0:
        return None
    return "no mining device — MLA1517_MMIO_DEVICE unset and no OpenCL device"


def _mining_start(_body: dict[str, Any]) -> tuple[HTTPStatus, dict[str, Any]]:
    control = _control_plane()
    reason = _mining_device_reason(control)
    if reason is not None:
        _audit().append("mining_start_refused", reason=reason)
        return HTTPStatus.OK, {"ok": False, "reason": reason}
    control.set_autostart(True)
    _audit().append("mining_start", workers=list(control.handles))
    records = {r.worker_id: r.state for r in control.records()}
    payload: dict[str, Any] = {"ok": True, "workers": records}
    if not control.mining_device_bound():
        payload["note"] = (
            "workers armed_no_device — no mining device bound; set "
            "PYTHIA_EXECUTION_DEVICE=opencl to mine on the OpenCL device, or "
            "MLA1517_MMIO_DEVICE for the MLA1517 bridge"
        )
    return HTTPStatus.OK, payload


def _mining_stop(_body: dict[str, Any]) -> tuple[HTTPStatus, dict[str, Any]]:
    retired = _control_plane().stop_workers()
    _audit().append("mining_stop", retired=retired)
    return HTTPStatus.OK, {"ok": True, "retired": retired}


def _mining_switch(body: dict[str, Any]) -> tuple[HTTPStatus, dict[str, Any]]:
    target = str(body.get("pool", "")).strip()
    cfg = runtime_config.load()
    pools = cfg.get("pools", [])
    selected = next(
        (p for p in pools if p.get("worker") == target or p.get("endpoint") == target),
        None,
    )
    if selected is None:
        return HTTPStatus.NOT_FOUND, {
            "ok": False,
            "error": f"pool {target!r} is not configured",
        }
    for p in pools:
        p["enabled"] = p is selected
    cfg["live_submit"] = {"enabled": False, "approval_id": ""}
    try:
        saved = runtime_config.save(cfg)
    except ValueError as exc:
        return HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)}
    applied = _apply_runtime_config(saved)
    _audit().append("mining_pool_switch", pool=target)
    out = runtime_config.public_view(saved)
    out["effective_arms"] = int(saved.get("solvers", {}).get("arms", 1))
    out["live_arms"] = _live_arm_ids()
    return HTTPStatus.OK, {"ok": True, "applied": applied, "config": out}


def _mining_elevate(body: dict[str, Any]) -> tuple[HTTPStatus, dict[str, Any]]:
    return _config_put({"hashrate": {"target_hs": body.get("target_hs")}})


def _mining_escalate(body: dict[str, Any]) -> tuple[HTTPStatus, dict[str, Any]]:
    return _config_put({"solvers": {"arms": body.get("arms")}})


def _agentic_start(body: dict[str, Any]) -> tuple[HTTPStatus, dict[str, Any]]:
    return _runner_start(
        lambda: system_fabric.start_agentic(
            count=int(body.get("count") or 128),
            cycles=int(body.get("cycles") or 3),
        )
    )


def _campaign_start(_body: dict[str, Any]) -> tuple[HTTPStatus, dict[str, Any]]:
    return _runner_start(
        lambda: system_fabric.start_campaign(
            apply_config=_apply_config_dict,
            retire_all=_retire_all_arms,
            counter_probe=_arm_counters,
        )
    )


def _salamander_fault(body: dict[str, Any]) -> tuple[HTTPStatus, dict[str, Any]]:
    """Operator-edge fault intake: recorded to the append-only audit so
    homeostasis decisions can consume it; never silently dropped."""
    kind = re.sub(r"[^a-zA-Z0-9_\-]", "_", str(body.get("kind", "unspecified")))[:96]
    source = str(body.get("source", "unknown"))[:200]
    detail = body.get("detail")
    _audit().append(
        "salamander_fault",
        source=source,
        kind=kind,
        detail=str(detail)[:500] if detail is not None else None,
        reported_at=body.get("at"),
    )
    METRICS.inc(f'pythia_salamander_faults_total{{kind="{kind}"}}')
    return HTTPStatus.OK, {"ok": True, "recorded": True}


def _toe_bridge() -> Any:
    """Lazily construct the single TOEBridge the collapse endpoint serves.

    Import of ``toe.bridge`` is deferred to the first POST so the control
    plane's startup and read-only GET surface never pay the tensor import.
    """
    global _TOE_BRIDGE
    with _TOE_BRIDGE_GUARD:
        if _TOE_BRIDGE is None:
            from toe.bridge import TOEBridge

            _TOE_BRIDGE = TOEBridge()
        return _TOE_BRIDGE


def toe_collapse_payload(data: Any) -> dict[str, Any]:
    """POST /api/v1/toe/collapse — the unified TOE collapse surface.

    One endpoint over the full bridge prediction: state tomography,
    Schrödinger trajectory, causal analysis, Pearl do-calculus ladder, and
    the exact-tensor witness. The bridge reports per-section ``available``
    honestly; transport failures are the only thing that raise here.
    """
    result = _toe_bridge().predict(data)
    return {
        "schema_version": _TOE_SCHEMA_VERSION,
        "generated_at": now_iso(),
        **result,
    }


class _Handler(BaseHTTPRequestHandler):
    server_version = "PYTHIAControlAPI/1.0"

    def _guardian_headers(self) -> dict[str, str]:
        return {
            "authorization": self.headers.get("Authorization", ""),
            "x-hyba-tenant": self.headers.get("X-HYBA-Tenant", ""),
            "x-hyba-actor": self.headers.get("X-HYBA-Actor", ""),
        }

    def _guardian_preflight(self, path: str, body: dict[str, Any] | None = None) -> bool:
        """Fail closed before any privileged handler is invoked."""
        if pythia_guardian_api is None:
            self._json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"available": False, "reason": "guardian_dependency_unavailable"},
            )
            return False
        operation = path.removeprefix("/api/v1/").replace("/", ".")
        if pythia_guardian_api is None:
            self._json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"available": False, "reason": "guardian_dependency_unavailable"},
            )
            return False
        evaluate_body = {
            "operation": operation,
            "resource": path.removeprefix("/api/v1/"),
            "payload": body or {},
        }
        if body is None:
            evaluate_body["observation"] = {
                "operation": operation,
                "resource": evaluate_body["resource"],
            }
        elif isinstance(body, dict) and "observation" in body:
            evaluate_body["observation"] = body["observation"]
        try:
            code, receipt = pythia_guardian_api().evaluate(
                headers=self._guardian_headers(),
                body=evaluate_body,
            )
        except Exception as exc:  # noqa: BLE001 - dependency failure: 503, never 500
            self._json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {
                    "available": False,
                    "error": "guardian_unavailable",
                    "reason": f"{type(exc).__name__}: {exc}",
                },
            )
            return False
        if code != HTTPStatus.OK:
            self._json(HTTPStatus(code), receipt)
            return False
        self._guardian_receipt = receipt
        return True

    def _guardian_commit_evidence(self, path: str, status: int, receipt: dict[str, Any]) -> None:
        digest = hashlib.sha256(
            json.dumps(receipt, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        _audit().append(
            "guardian_mediated",
            path=path,
            status=int(status),
            receipt_sha256=digest,
            allowed=bool(receipt.get("allowed")),
        )

    def do_GET(self) -> None:  # noqa: N802
        self._guarded(self._route_get)

    def do_POST(self) -> None:  # noqa: N802
        self._guarded(self._route_post)

    def _guarded(self, route: Any) -> None:
        """A failing route answers 500 JSON instead of dropping the connection."""
        try:
            route()
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except Exception as exc:  # noqa: BLE001 - reported to the client and stderr
            path = urlparse(self.path).path
            traceback.print_exc()
            try:
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"error": "internal_error", "detail": type(exc).__name__, "path": path},
                )
            except Exception:
                self.close_connection = True

    def _route_get(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith(_PRIVILEGED_PREFIXES):
            if not self._guardian_preflight(path):
                return
        if path in {"/api/health", "/healthz", "/api/v1/healthz"}:
            self._json(
                HTTPStatus.OK,
                {
                    "schema_version": _SCHEMA_VERSION,
                    "status": "ok",
                    "generated_at": now_iso(),
                },
            )
            return
        if path in {"/readyz", "/api/v1/readyz"}:
            identity = _identity_payload()
            status = HTTPStatus.OK if identity["ok"] else HTTPStatus.SERVICE_UNAVAILABLE
            self._json(
                status,
                {
                    "schema_version": _READY_SCHEMA_VERSION,
                    "ready": bool(identity["ok"]),
                    "reason": identity["reason"] if not identity["ok"] else "ok",
                    "generated_at": now_iso(),
                },
            )
            return
        if path in {"/ready-to-mine", "/api/v1/ready-to-mine"}:
            payload = status_payload()["ready_to_mine"]
            ready = bool(payload["ready"])
            self._json(
                HTTPStatus.OK if ready else HTTPStatus.SERVICE_UNAVAILABLE,
                payload
                | {
                    "schema_version": _READY_SCHEMA_VERSION,
                    "generated_at": now_iso(),
                },
            )
            return
        if path in {"/metrics", "/api/v1/metrics"}:
            body = metrics_payload().encode("utf-8")
            self._send(HTTPStatus.OK, "text/plain; version=0.0.4; charset=utf-8", body)
            return
        if path == "/api/v1/mla1517/status":
            self._json(HTTPStatus.OK, status_payload())
            return
        if path == "/api/v1/mining/evidence":
            self._json(HTTPStatus.OK, mining_evidence_payload())
            return
        if path == "/api/v1/knowledge":
            self._json(HTTPStatus.OK, knowledge_payload())
            return
        if path == "/api/v1/gpu":
            self._json(HTTPStatus.OK, gpu_payload())
            return
        if path == "/api/v1/telemetry/summary":
            self._json(HTTPStatus.OK, telemetry_summary_payload())
            return
        if path == "/api/v1/audit/tail":
            params = parse_qs(parsed.query)
            self._json(HTTPStatus.OK, audit_tail_payload(params.get("n", ["50"])[0]))
            return
        if path == "/api/v1/config":
            self._json(HTTPStatus.OK, _config_public_payload())
            return
        if path == "/api/v1/system/map":
            self._json(HTTPStatus.OK, _fabric_map_payload())
            return
        if path == "/api/v1/system/verify":
            self._json(HTTPStatus.OK, system_fabric.verification_status())
            return
        if path == "/api/v1/intelligence/status":
            self._json(HTTPStatus.OK, system_fabric.intelligence_status())
            return
        if path == "/api/v1/intelligence/selftest":
            self._json(HTTPStatus.OK, system_fabric.selftest_status())
            return
        if path == "/api/v1/intelligence/maintenance":
            self._json(HTTPStatus.OK, system_fabric.self_repair_status())
            return
        if path == "/api/v1/intelligence/autonomous":
            self._json(HTTPStatus.OK, system_fabric.autonomous_supervisor_status())
            return
        if path == "/api/v1/intelligence/engineer/status":
            self._json(HTTPStatus.OK, system_fabric.repo_engineer_status())
            return
        if path == "/api/v1/agentic/status":
            self._json(HTTPStatus.OK, system_fabric.agentic_status())
            return
        if path == "/api/v1/campaign/status":
            self._json(HTTPStatus.OK, system_fabric.campaign_status())
            return
        if path == "/api/v1/stratum/status":
            self._json(HTTPStatus.OK, stratum_status_payload())
            return
        if path == "/api/v1/telemetry/events":
            params = parse_qs(parsed.query)
            self._json(HTTPStatus.OK, telemetry_events_payload(params.get("n", ["100"])[0]))
            return
        if path == "/api/v1/hardware/status":
            self._json(HTTPStatus.OK, hardware_status_payload())
            return
        if path == "/api/v1/security/status":
            self._json(*security_status_payload())
            return
        if path == "/api/v1/security/subscribe":
            code, security = security_status_payload()
            if code != HTTPStatus.OK:
                self._json(code, security)
                return
            self._json(
                HTTPStatus.OK,
                {
                    "product": "HYBA Security",
                    "capability": security["capability"],
                    "subscription_required": True,
                    "subscription_url": security["subscription_url"],
                },
            )
            return
        self._static_or_404(path)

    _POST_TABLE: dict[str, Any] = {
        "/api/v1/system/verify": lambda _b: _runner_start(system_fabric.start_verification),
        "/api/v1/intelligence/selftest": lambda _b: _runner_start(system_fabric.start_selftest),
        "/api/v1/intelligence/maintenance/start": lambda _b: _runner_start(
            system_fabric.start_self_repair
        ),
        "/api/v1/intelligence/maintenance/run": lambda _b: _runner_start(
            system_fabric.run_self_repair_now
        ),
        "/api/v1/intelligence/maintenance/stop": lambda _b: (
            HTTPStatus.ACCEPTED,
            {
                "ok": system_fabric.stop_self_repair(),
                "state": system_fabric.self_repair_status()["state"],
                "detail": "stop takes effect after the current full diagnosis cycle",
            },
        ),
        "/api/v1/intelligence/autonomous/trigger": lambda _b: (
            HTTPStatus.OK,
            autonomous_supervisor.trigger_cycle(),
        ),
        "/api/v1/intelligence/engineer/ask": _repo_engineer_ask,
        "/api/v1/agentic/start": _agentic_start,
        "/api/v1/agentic/stop": lambda _b: _runner_stop(system_fabric.AGENTIC),
        "/api/v1/campaign/start": _campaign_start,
        "/api/v1/campaign/stop": lambda _b: _runner_stop(system_fabric.CAMPAIGN),
        "/api/v1/mining/start": _mining_start,
        "/api/v1/mining/stop": _mining_stop,
        "/api/v1/mining/switch": _mining_switch,
        "/api/v1/mining/elevate": _mining_elevate,
        "/api/v1/mining/escalate": _mining_escalate,
        "/api/v1/salamander/fault": _salamander_fault,
    }

    def _guardian_api(self):
        """Return the lazily-built guardian, or answer 503 instead of
        dropping the connection when it cannot be constructed."""
        if pythia_guardian_api is None:
            self._json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"allowed": False, "reason": "guardian_dependency_unavailable"},
            )
            return None
        try:
            return pythia_guardian_api()
        except Exception:
            self._json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"allowed": False, "reason": "guardian_unavailable"},
            )
            return None

    def _drain(self, length: int) -> None:
        """Discard a refused body, bounded so a hostile Content-Length cannot
        force unbounded reads; past the cap the connection is closed."""
        remaining = min(int(length), _TOE_MAX_BODY_BYTES * 4)
        if length > remaining:
            self.close_connection = True
        try:
            while remaining > 0:
                chunk = self.rfile.read(min(remaining, 65536))
                if not chunk:
                    break
                remaining -= len(chunk)
        except (OSError, ValueError):
            self.close_connection = True

    def _read_json_body(self) -> tuple[dict[str, Any] | None, str | None]:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None, "invalid_content_length"
        if length <= 0:
            return {}, None
        if length > _TOE_MAX_BODY_BYTES:
            # Empty the socket before the 413 so the client reads the status
            # instead of a connection reset mid-upload.
            self._drain(length)
            return None, "body_too_large"
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return None, "malformed_json"
        if not isinstance(body, dict):
            return None, "body_must_be_object"
        return body, None

    def _route_post(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/v1/security/evaluate":
            body, err = self._read_json_body()
            if body is None:
                status = (
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE
                    if err == "body_too_large"
                    else HTTPStatus.BAD_REQUEST
                )
                self._json(status, {"allowed": False, "reason": err})
                return
            if pythia_guardian_api is None:
                self._json(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    {"allowed": False, "reason": "guardian_dependency_unavailable"},
                )
                return
            guardian = self._guardian_api()
            if guardian is None:
                return
            code, payload = guardian.evaluate(
                headers={
                    "authorization": self.headers.get("Authorization", ""),
                    "x-hyba-tenant": self.headers.get("X-HYBA-Tenant", ""),
                    "x-hyba-actor": self.headers.get("X-HYBA-Actor", ""),
                },
                body=body,
            )
            self._json(HTTPStatus(code), payload)
            return
        if parsed.path == "/api/v1/toe/collapse":
            body, err = self._read_json_body()
            if body is None:
                status = (
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE
                    if err == "body_too_large"
                    else HTTPStatus.BAD_REQUEST
                )
                self._json(status, {"allowed": False, "reason": err})
                return
            if not body:
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"allowed": False, "reason": "empty_body"},
                )
                return
            if pythia_guardian_api is None:
                self._json(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    {"allowed": False, "reason": "guardian_dependency_unavailable"},
                )
                return
            data = body.get("data", body)
            observation = data if isinstance(data, dict) else {"value": data}
            guardian = self._guardian_api()
            if guardian is None:
                return
            code, decision = guardian.evaluate(
                headers={
                    "authorization": self.headers.get("Authorization", ""),
                    "x-hyba-tenant": self.headers.get("X-HYBA-Tenant", ""),
                    "x-hyba-actor": self.headers.get("X-HYBA-Actor", ""),
                },
                body={
                    "operation": "toe.collapse",
                    "resource": "toe/collapse",
                    "payload": {"data": data},
                    "observation": observation,
                },
                include_evidence=True,
            )
            if code != HTTPStatus.OK:
                self._json(HTTPStatus(code), decision)
                return
            evidence = decision.pop("intelligence_evidence")
            result = evidence["result"]
            self._json(
                HTTPStatus.OK,
                {
                    "schema_version": _TOE_SCHEMA_VERSION,
                    "generated_at": now_iso(),
                    "guardian_receipt": decision,
                    "execution_evidence": evidence["execution_evidence"],
                    **result,
                },
            )
            return
        handler = self._POST_TABLE.get(parsed.path)
        if handler is None:
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        privileged = parsed.path.startswith(_PRIVILEGED_PREFIXES)
        if not privileged and self._refuse_unauthorized():
            return
        body, err = self._read_json_body()
        if body is None:
            status = (
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE
                if err == "body_too_large"
                else HTTPStatus.BAD_REQUEST
            )
            self._json(status, {"error": err})
            return
        if privileged:
            if not self._guardian_preflight(parsed.path, body):
                return
        try:
            status, payload = handler(body)
        except ValueError as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return
        except Exception as exc:
            self._json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
            )
            return
        self._json(status, payload)

    def do_PUT(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/api/v1/config":
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        if self._refuse_unauthorized():
            return
        body, err = self._read_json_body()
        if body is None:
            status = (
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE
                if err == "body_too_large"
                else HTTPStatus.BAD_REQUEST
            )
            self._json(status, {"error": err})
            return
        status, payload = _config_put(body)
        self._json(status, payload)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[pythia-control] {self.address_string()} - {format % args}")

    # Every response carries the same defensive headers — the console is an
    # operator surface, so it denies framing, sniffing, and cross-origin
    # resource pulls beyond the font CDN the UI actually uses.
    _CSP = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )

    def _send(
        self,
        status: int,
        content_type: str,
        body: bytes,
        cache_control: str = "no-store",
    ) -> None:
        self.send_response(int(status))
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache_control)
        self.send_header("Content-Security-Policy", self._CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        if not getattr(self, "_head_only", False):
            self.wfile.write(body)

    def _json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        receipt = getattr(self, "_guardian_receipt", None)
        if receipt is not None:
            payload = dict(payload)
            payload.setdefault("guardian_receipt", receipt)
            self._guardian_commit_evidence(urlparse(self.path).path, int(status), receipt)
            del self._guardian_receipt
        body = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        self._send(int(status), "application/json; charset=utf-8", body)

    def _refuse_unauthorized(self) -> bool:
        refusal = control_authorization(self.headers)
        if refusal is None:
            return False
        status, reason = refusal
        _audit().append("control_refused", path=urlparse(self.path).path, reason=reason)
        self._json(status, {"ok": False, "error": reason})
        return True

    def _method_not_allowed(self) -> None:
        self._json(HTTPStatus.METHOD_NOT_ALLOWED, {"error": "method_not_allowed"})

    def do_HEAD(self) -> None:  # noqa: N802
        self._head_only = True
        try:
            self.do_GET()
        finally:
            self._head_only = False

    def do_DELETE(self) -> None:  # noqa: N802
        self._method_not_allowed()

    def do_PATCH(self) -> None:  # noqa: N802
        self._method_not_allowed()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._method_not_allowed()

    def _static_or_404(self, request_path: str) -> None:
        root = Path(getattr(self.server, "web_root", Path(".")))
        candidate = (root / unquote(request_path.lstrip("/"))).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        # API paths never fall through to the SPA shell — an unrouted
        # /api/* GET is a real 404, not index.html.
        if not candidate.is_file():
            if request_path.startswith("/api/"):
                self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            candidate = root / "index.html"
        if not candidate.is_file():
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        content = candidate.read_bytes()
        content_type, _ = mimetypes.guess_type(str(candidate))
        cache = (
            "public, max-age=31536000, immutable"
            if request_path.startswith("/assets/")
            else "no-cache"
        )
        self._send(HTTPStatus.OK, content_type or "application/octet-stream", content, cache)


def _active_ports_path() -> Path:
    return Path(os.getenv("PYTHIA_ACTIVE_PORTS_FILE", "/tmp/hyba_active_ports.json"))


def _write_active_ports(update: Any) -> None:
    """Merge-update the shared port file; other writers' keys survive."""
    path = _active_ports_path()
    try:
        current = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, ValueError):
        current = {}
    if not isinstance(current, dict):
        current = {}
    if not update(current):
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(current, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(temporary, path)
    except OSError as exc:
        print(f"[pythia-control] active port file {path} not updated: {exc}")


def publish_active_port(host: str, port: int) -> None:
    """Tell the frontend dev gateway where this control API listens."""
    reach = "127.0.0.1" if host in ("", "0.0.0.0", "::") else host

    def update(current: dict[str, Any]) -> bool:
        current.update(
            {
                "python_host": host,
                "python_port": int(port),
                "python_url": f"http://{reach}:{int(port)}",
                "python_pid": os.getpid(),
                "python_updated_at": now_iso(),
            }
        )
        return True

    _write_active_ports(update)


def retract_active_port() -> None:
    def update(current: dict[str, Any]) -> bool:
        if current.get("python_pid") != os.getpid():
            return False
        for key in ("python_host", "python_port", "python_url", "python_pid", "python_updated_at"):
            current.pop(key, None)
        return True

    _write_active_ports(update)


def serve(
    host: str = "0.0.0.0",
    port: int = 3000,
    web_root: str | Path = "dist/public",
) -> None:
    _control_plane()
    start_repo_engineer()
    announce_skills()
    if system_fabric.startup_self_repair_enabled():
        system_fabric.start_self_repair(startup=True)
    if os.getenv("PYTHIA_AUTONOMOUS_SUPERVISOR", "true").strip().lower() in {
        "1",
        "true",
        "yes",
    }:
        autonomous_supervisor.ensure_started()
    server = ThreadingHTTPServer((host, int(port)), _Handler)
    server.web_root = Path(web_root).resolve()
    bound = getattr(server, "server_address", None)
    if bound and bound[1]:
        publish_active_port(host, bound[1])
    # SIGTERM/SIGBREAK land on the serving thread; the shutdown request must
    # run on its own thread or serve_forever never leaves its poll loop.
    # Cleanup stays single-path in the finally below.

    def _graceful_stop(signum: int, _frame: Any) -> None:
        _audit().append("shutdown_signal", signum=signum)
        threading.Thread(target=server.shutdown, daemon=True).start()

    for signum in (signal.SIGTERM, getattr(signal, "SIGBREAK", None)):
        if signum is None:
            continue
        try:
            signal.signal(signum, _graceful_stop)
        except (OSError, ValueError):
            # Not on the main thread (embedded/imported use) — the caller's
            # own lifecycle governs shutdown.
            break
    try:
        server.serve_forever()
    finally:
        retract_active_port()
        if _CONTROL is not None:
            _CONTROL.shutdown()
        server.server_close()
        _boot_lock().release()


def main() -> None:
    _load_env_file()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.getenv("PYTHIA_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PYTHIA_PORT", "3000")))
    parser.add_argument("--web-root", default=os.getenv("PYTHIA_WEB_ROOT", "dist/public"))
    args = parser.parse_args()
    try:
        serve(host=args.host, port=args.port, web_root=args.web_root)
    except (RestartBudgetExhausted, StartupConfigError) as exc:
        raise SystemExit(str(exc)) from exc
    except KeyboardInterrupt:
        if _CONTROL is not None:
            _CONTROL.shutdown()
        _boot_lock().release()
        raise SystemExit(0)


if __name__ == "__main__":
    main()
