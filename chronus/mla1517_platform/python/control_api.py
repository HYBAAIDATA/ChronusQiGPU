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
import uuid
from collections import Counter
from collections import deque
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timezone
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
import failure_taxonomy
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
from worker_lifecycle import HeartbeatReader, _default_heartbeat_dir

_SCHEMA_VERSION = "chronus.mla1517.status/1"
_READY_SCHEMA_VERSION = "chronus.mla1517.ready/1"
_TOE_SCHEMA_VERSION = "chronus.mla1517.toe_collapse/1"
_TOE_MAX_BODY_BYTES = 4 * 1024 * 1024
_STATUS_BACKEND = "Python/C/OpenCL"
_CANONICAL_DEVICE = "canonical-python-backend"
# sane X-Request-Id/X-Correlation-Id = 1–128 chars, ASCII-alphanumeric
# leading character, then alphanumerics or any of . _ : @ - ; nothing else.
_REQUEST_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@-]{0,127}")
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
    "/api/v1/tensor/",
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
# Execution Router directly (OpenCL, the Chronus-owned CUDA or Metal lanes,
# the labelled CPU reference, or a remote GPU agent) and needs no MMIO bridge. Salamander supervises the bridge, so
# it still waits for one. The declared vocabulary matches
# mining_runtime.EXECUTION_DEVICES; lane availability itself is enforced by
# the backend registry's real probes, so requesting an absent lane fails
# closed rather than falling back silently.
_EXECUTION_DEVICE_WORKERS = frozenset({"agentic-mining"})
_EXECUTION_DEVICES = (
    "auto",
    "opencl",
    "gpu",
    "cpu",
    "cuda",
    "metal",
    "remote",
    "asic",
    "super_asic",
)
_LOCK_HELD = False
_LOCK_GUARD = threading.Lock()
_AUDIT: AppendOnlyAudit | None = None
_BOOT_LOCK: BootLock | None = None
_CONTROL: "ControlPlane" | None = None
_CONTROL_GUARD = threading.Lock()


class _RequestStats:
    """Golden-signal counters for the HTTP fabric (constitution §19).

    Counts every JSON response by result class and failure class so the
    metrics surface reports what the authoritative surface actually did —
    nothing fabricated, nothing suppressed.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counts: Counter[str] = Counter()

    def record(self, status: int, payload: dict[str, Any]) -> None:
        with self._lock:
            self._counts["requests_total"] += 1
            if status >= 400:
                self._counts["errors_total"] += 1
                cls = str(payload.get("failure_class") or "UNCLASSIFIED")
                self._counts[f"failure_class.{cls}"] += 1
            else:
                self._counts["success_total"] += 1

    def prometheus(self) -> str:
        with self._lock:
            counts = dict(self._counts)
        lines = []
        total = counts.pop("requests_total", 0)
        ok = counts.pop("success_total", 0)
        err = counts.pop("errors_total", 0)
        lines.append(f"pythia_control_requests_total {total}")
        lines.append(f"pythia_control_success_total {ok}")
        lines.append(f"pythia_control_errors_total {err}")
        for key in sorted(counts):
            if key.startswith("failure_class."):
                cls = key.split(".", 1)[1]
                lines.append(
                    f'pythia_control_failure_class_total{{failure_class="{cls}"}} '
                    f"{counts[key]}"
                )
        return "\n".join(lines)


_REQUEST_STATS = _RequestStats()

# Idempotency for mutating HTTP operations (constitution §10): a caller
# Idempotency-Key on a POST/PUT replays the recorded outcome inside the
# retention window instead of re-executing the mutation. Unknown-outcome
# retries remain impossible — a key is recorded only after the handler
# answered, and records expire.
_IDEMPOTENCY_RECORDS: "dict[str, tuple[float, int, dict]]" = {}
_IDEMPOTENCY_GUARD = threading.Lock()
_IDEMPOTENCY_TTL_S = 300.0
_IDEMPOTENCY_MAX = 512


def _idempotency_lookup(key: str) -> tuple[int, dict] | None:
    now = time.monotonic()
    with _IDEMPOTENCY_GUARD:
        entry = _IDEMPOTENCY_RECORDS.get(key)
        if entry is None:
            return None
        at, status, payload = entry
        if now - at > _IDEMPOTENCY_TTL_S:
            del _IDEMPOTENCY_RECORDS[key]
            return None
        return status, dict(payload)


def _idempotency_store(key: str, status: int, payload: dict) -> None:
    now = time.monotonic()
    with _IDEMPOTENCY_GUARD:
        stale = [k for k, (at, _s, _p) in _IDEMPOTENCY_RECORDS.items() if now - at > _IDEMPOTENCY_TTL_S]
        for k in stale:
            del _IDEMPOTENCY_RECORDS[k]
        while len(_IDEMPOTENCY_RECORDS) >= _IDEMPOTENCY_MAX:
            _IDEMPOTENCY_RECORDS.pop(next(iter(_IDEMPOTENCY_RECORDS)))
        _IDEMPOTENCY_RECORDS[key] = (now, int(status), dict(payload))


def _idempotency_key(headers: Any) -> str:
    """A sane caller-supplied Idempotency-Key, else ''. Malformed keys are
    ignored rather than trusted."""
    key = (headers.get("Idempotency-Key") or "").strip()
    return key if _REQUEST_ID_RE.fullmatch(key) else ""

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
        "contract_device": None,
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
        # "Active" means a GPU-class device is the executing dispatch path —
        # never merely detected. An `opencl:cpu` emulated backend and a
        # CPU-fallback hasher are detected, not active. Punch hosts report
        # `opencl:<device name>` without a class suffix, so a named backend
        # counts only when it matches a GPU-class device in the same
        # enumeration (an `opencl:<cpu device>` name alongside a GPU is not).
        backend_active = detected_backend == "opencl:gpu"
        if (
            not backend_active
            and detected_backend.startswith("opencl:")
            and detected_backend != "opencl:cpu"
        ):
            bound_name = detected_backend.split(":", 1)[1].strip()
            backend_active = bool(bound_name) and any(
                bound_name == str(device.get("name") or "").strip()
                for device in gpu_devices
            )
        # The Chronus contract device is the system's declared GPU identity —
        # enumerated from the loaded spec, not probed silicon. It is reported
        # alongside (never inside) the physical device counts so hardware
        # absence stays honest.
        contract_device: dict[str, Any] | None = None
        try:
            from chronus.detect import detect_chronus as _detect_chronus

            chronus_devices = _detect_chronus()
            if chronus_devices:
                contract_device = chronus_devices[0].as_dict()
        except Exception:
            contract_device = None
        payload = {
            "available": substrate_available,
            "count": member_count,
            "contract_device": contract_device,
            "opencl_device_count": len(devices),
            "physical_gpu_available": bool(gpu_devices),
            "physical_gpu_count": len(gpu_devices),
            "devices": devices,
            "backend_active": backend_active,
            "detected_backend": detected_backend,
            "detected_device": str(hasher.get("device") or ""),
            "logical_substrate": {
                "name": "hyba-super-gpu",
                "available": substrate_available,
                "active": backend_active,
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
    raw = os.getenv("PYTHIA_WORKER_HEARTBEAT_DIR", _default_heartbeat_dir())
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


def _readiness_components() -> dict[str, Any]:
    """Cheap, honest per-component readiness for the readyz payload.

    Each entry reports only what the readiness path can verify directly —
    configuration and filesystem facts, never a liveness promise for a
    subsystem it cannot observe here. ``ready`` itself is unchanged: it
    stays bound to worker identity readiness.

    Second-pass elevation (service constitution §20): components now also
    carry dependency health (stratum session, runtime config, remote
    execution lane config, custody mount) so readiness reports
    component-level truth instead of a collapsed boolean.
    """
    components: dict[str, Any] = {}
    ok, reason = identity_hmac_status()
    components["identity"] = {
        "state": "ready" if ok else "not_ready",
        "reason": reason,
    }
    try:
        audit = _audit()
        audit.path.parent.mkdir(parents=True, exist_ok=True)
        components["boot_audit"] = {"state": "ready", "path": str(audit.path)}
    except (OSError, StartupConfigError) as exc:
        components["boot_audit"] = {"state": "not_ready", "reason": str(exc)}
    try:
        heartbeat = _heartbeat_dir()
        heartbeat.mkdir(parents=True, exist_ok=True)
        components["worker_heartbeat_dir"] = {"state": "ready", "path": str(heartbeat)}
    except (OSError, StartupConfigError) as exc:
        components["worker_heartbeat_dir"] = {
            "state": "not_ready",
            "reason": str(exc),
        }
    if pythia_guardian_api is None:
        components["guardian"] = {
            "state": "unavailable",
            "reason": "al_haras dependency missing",
        }
    elif not os.getenv("AL_HARAS_SUBSCRIPTION_KEYS"):
        components["guardian"] = {
            "state": "not_configured",
            "reason": "AL_HARAS_SUBSCRIPTION_KEYS unset",
        }
    else:
        components["guardian"] = {"state": "configured"}
    # Dependency health (§20): observed/declared truth per dependency, no
    # liveness promises. These do not feed the top-level ``ready`` flag —
    # they are the per-component evidence a balancer/operator reads.
    try:
        cfg_path = runtime_config.config_path()
        if not cfg_path.is_file():
            components["runtime_config"] = {
                "state": "not_configured",
                "reason": f"{cfg_path} absent",
            }
        else:
            runtime_config.load()
            components["runtime_config"] = {"state": "ready", "path": str(cfg_path)}
    except (OSError, StartupConfigError, ValueError) as exc:
        components["runtime_config"] = {"state": "not_ready", "reason": str(exc)}
    try:
        stratum = stratum_status_payload()
        connected = bool(stratum.get("connected"))
        components["stratum"] = {
            "state": "connected" if connected else "disconnected",
            "ready": bool(stratum.get("ready")),
            "status": stratum.get("status"),
        }
    except Exception as exc:  # noqa: BLE001 - observation only, never blocks readiness
        components["stratum"] = {"state": "unavailable", "reason": type(exc).__name__}
    remote_eps = os.getenv("HYBA_REMOTE_OPENCL_ENDPOINTS") or os.getenv(
        "MLA1517_REMOTE_GPU_ENDPOINT"
    )
    components["remote_opencl"] = (
        {"state": "configured"}
        if remote_eps
        else {"state": "not_configured", "reason": "no remote endpoints declared"}
    )
    m3_storage = _metrics_json("agentic-mining", "m3_storage")
    if isinstance(m3_storage, dict):
        components["custody"] = {
            "state": "ready" if m3_storage.get("healthy") is True else "not_ready",
            "configured": bool(m3_storage.get("configured")),
            "reconciliation_ok": bool(m3_storage.get("reconciliation_ok")),
            "file_plane_ok": bool(m3_storage.get("file_plane_ok")),
            "mining_chain_ok": bool(m3_storage.get("mining_chain_ok")),
            "errors": m3_storage.get("errors"),
            "reason": m3_storage.get("last_error")
            or (None if m3_storage.get("healthy") is True else "M3 custody evidence unavailable"),
        }
    else:
        components["custody"] = {
            "state": "not_mounted",
            "reason": "mining worker has not published THESEUS/M3 storage health",
        }
    m3_authorization = _metrics_json("agentic-mining", "m3_authorization")
    components["m3_authorization"] = (
        {
            "state": "ready" if m3_authorization.get("configured") is True else "not_ready",
            "configured": bool(m3_authorization.get("configured")),
            "policy_version": m3_authorization.get("policy_version"),
        }
        if isinstance(m3_authorization, dict)
        else {"state": "unavailable", "configured": False}
    )
    return components


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
    payload: dict[str, Any] = {
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
    # The worker publishes more measured context than the curated minimum:
    # session identity, protocol, share outcome ratios, lifecycle flags, the
    # retarget window, measured effective hashrate and the pool topology.
    # These pass through verbatim — they are already canonical state.
    for key in (
        "session_id",
        "protocol",
        "outcomes",
        "lifecycle",
        "retarget_window",
        "effective_stratum_hashrate_hs",
        "pool",
    ):
        if observed.get(key) is not None:
            payload[key] = observed[key]
    return payload


def _m3_dependency_reason() -> tuple[bool, str]:
    """Strict M3 dependency gate derived only from worker-published evidence."""
    if not _is_truthy(os.getenv("PYTHIA_M3_REQUIRED")):
        return True, "not_required"
    storage = _metrics_json("agentic-mining", "m3_storage")
    authorization = _metrics_json("agentic-mining", "m3_authorization")
    runtime = _metrics_json("agentic-mining", "m3_runtime")
    if not isinstance(storage, dict):
        return False, "m3_storage_evidence_unavailable"
    if storage.get("healthy") is not True:
        return False, "m3_storage_unhealthy"
    if storage.get("reconciliation_ok") is not True:
        return False, "m3_storage_unreconciled"
    if storage.get("file_plane_ok") is not True or storage.get("mining_chain_ok") is not True:
        return False, "m3_storage_integrity_failed"
    if not isinstance(authorization, dict) or authorization.get("configured") is not True:
        return False, "m3_al_haras_unavailable"
    if not isinstance(runtime, dict):
        return False, "m3_runtime_evidence_unavailable"
    if runtime.get("blocked") is True:
        return False, "m3_runtime_blocked"
    if runtime.get("gate_configured") is not True:
        return False, "m3_submission_gate_unavailable"
    last_gate = runtime.get("last_submission_gate")
    if isinstance(last_gate, dict) and last_gate.get("allowed") is False:
        return False, str(last_gate.get("reason") or "m3_submission_denied").lower()
    if runtime.get("search_authority") != "PYTHIA":
        return False, "m3_pythia_authority_unavailable"
    if runtime.get("search_algorithm") != "hendrix_coprime_stride":
        return False, "m3_hendrix_not_bound"
    if runtime.get("search_architecture_ready") is not True:
        return False, "m3_search_architecture_unavailable"
    fabric = runtime.get("chronus_fabric")
    if not isinstance(fabric, dict) or int(fabric.get("logical_vertices") or 0) != 600:
        return False, "m3_chronus_fabric_unavailable"
    return True, "ok"


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
    m3_ready, m3_reason = _m3_dependency_reason()
    if not m3_ready:
        return False, m3_reason
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
OPERATOR_PRINCIPALS_ENV = "PYTHIA_OPERATOR_PRINCIPALS_JSON"
OPERATOR_PRINCIPAL_HEADER = "X-PYTHIA-Principal"
_CONTROL_ROLES = frozenset({"ceo", "operator"})
_PRINCIPAL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{0,127}$")


@dataclass(frozen=True)
class ControlPrincipal:
    principal_id: str
    role: str
    source: str


def _operator_principals() -> tuple[dict[str, dict[str, str]] | None, str | None]:
    """Load the server-side principal map without accepting plaintext secrets.

    The optional JSON object maps a principal id to a supported role and the
    SHA-256 digest of that principal's bearer token. When configured, this map
    takes precedence over the legacy shared admin key.
    """
    raw = os.getenv(OPERATOR_PRINCIPALS_ENV)
    if raw is None:
        return None, None
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return None, "operator principal mapping is invalid"
    if not isinstance(value, dict) or not value:
        return None, "operator principal mapping is invalid"
    principals: dict[str, dict[str, str]] = {}
    for principal_id, spec in value.items():
        if not isinstance(principal_id, str) or not _PRINCIPAL_ID_RE.fullmatch(principal_id):
            return None, "operator principal mapping is invalid"
        if not isinstance(spec, dict):
            return None, "operator principal mapping is invalid"
        role = spec.get("role")
        digest = spec.get("token_sha256")
        if (
            role not in _CONTROL_ROLES
            or not isinstance(digest, str)
            or re.fullmatch(r"[0-9a-fA-F]{64}", digest) is None
        ):
            return None, "operator principal mapping is invalid"
        principals[principal_id] = {
            "role": str(role),
            "token_sha256": digest.lower(),
        }
    return principals, None


def authenticate_control_principal(
    headers: Any,
) -> tuple[ControlPrincipal | None, tuple[HTTPStatus, str] | None]:
    """Authenticate a server-mapped operator or the legacy admin-key identity."""
    principals, mapping_error = _operator_principals()
    if mapping_error:
        return None, (HTTPStatus.SERVICE_UNAVAILABLE, mapping_error)
    header = str(headers.get("Authorization", "") or "")
    token = header[7:].strip() if header[:7].lower() == "bearer " else ""
    if principals is not None:
        principal_id = str(headers.get(OPERATOR_PRINCIPAL_HEADER, "") or "").strip()
        if not principal_id:
            return None, (HTTPStatus.UNAUTHORIZED, "operator principal required")
        spec = principals.get(principal_id)
        if spec is None:
            return None, (HTTPStatus.FORBIDDEN, "operator principal is not authorized")
        candidate = hashlib.sha256(token.encode("utf-8")).hexdigest() if token else ""
        if not candidate or not hmac.compare_digest(candidate, spec["token_sha256"]):
            return None, (HTTPStatus.UNAUTHORIZED, "operator credential required")
        return (
            ControlPrincipal(
                principal_id=principal_id,
                role=spec["role"],
                source="server_principal_map",
            ),
            None,
        )

    key = os.getenv(ADMIN_KEY_ENV, "").strip()
    if not key:
        if _is_truthy(os.getenv(UNAUTHENTICATED_ENV)):
            return ControlPrincipal("local-dev", "operator", "declared_dev_mode"), None
        return None, (
            HTTPStatus.FORBIDDEN,
            f"{ADMIN_KEY_ENV} is not configured; control is closed",
        )
    if not token or not hmac.compare_digest(token.encode("utf-8"), key.encode("utf-8")):
        return None, (HTTPStatus.UNAUTHORIZED, "operator key required")
    return ControlPrincipal("legacy-admin", "operator", "legacy_admin_key"), None


def control_authorization(headers: Any) -> tuple[HTTPStatus, str] | None:
    """None when a state-changing request is authorized, else (status, reason).

    Fail closed: when PYTHIA_OPERATOR_PRINCIPALS_JSON is configured, every
    non-guardian state change needs a bearer credential bound to the claimed
    X-PYTHIA-Principal by that server-side map. Otherwise the legacy shared
    EUCLID_ADMIN_API_KEY contract remains available for migration. With
    neither configured nothing may change state, unless the explicit local
    development opt-out is enabled.
    """
    _, refusal = authenticate_control_principal(headers)
    return refusal


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


# -- operational-observability surface (spec §1-§13) -------------------------
#
# One canonical contract assembled from the channels that already carry the
# truth: the worker's published Stratum snapshot and event log, the measured
# hashing counters, the supervisor's worker records, the persisted JSONL
# stores, and the guardian's public status. A section whose source has not
# reported yet answers available=false with a reason — the console shows
# "Unavailable", never a synthesized value.


def _iso_ts(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def _env_data_path(env_name: str, default_name: str) -> Path:
    """Worker-persisted data file. Workers run with cwd=_PY_DIR, so relative
    env overrides resolve there too — not against the API process's cwd."""
    raw = os.getenv(env_name)
    if raw:
        candidate = Path(raw)
        if candidate.is_absolute():
            return candidate
        return _PY_DIR / candidate
    return _PY_DIR / "data" / default_name


def _file_evidence(path: Path | None) -> dict[str, Any]:
    """Provenance of a persisted telemetry store — observed, never assumed."""
    info: dict[str, Any] = {
        "path": os.path.basename(str(path)) if path else None,
        "exists": False,
        "size_bytes": None,
        "modified_at": None,
    }
    if path is None:
        info["reason"] = "store not configured"
        return info
    try:
        stat = os.stat(path)
    except OSError:
        info["reason"] = "no persisted records yet"
        return info
    info["exists"] = True
    info["size_bytes"] = stat.st_size
    info["modified_at"] = _iso_ts(stat.st_mtime)
    return info


def _jsonl_tail(path: Path, limit: int, kinds: set[str] | None = None) -> list[dict[str, Any]]:
    """Newest ``limit`` records of a JSONL store; empty when absent."""
    records: deque[dict[str, Any]] = deque(maxlen=max(1, int(limit)))
    try:
        with open(path, "rb") as stream:
            for raw in stream:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    record = json.loads(raw)
                except ValueError:
                    continue
                if not isinstance(record, dict):
                    continue
                if kinds is not None and record.get("kind") not in kinds:
                    continue
                records.append(record)
    except OSError:
        return list(records)
    return list(records)


def _telemetry_history_path() -> Path:
    return _env_data_path("PYTHIA_TELEMETRY_HISTORY_PATH", "telemetry_history.jsonl")


def _causal_log_path() -> Path:
    return _env_data_path("PYTHIA_CAUSAL_LOG_PATH", "causal_ledger.jsonl")


def _mining_session_path() -> Path:
    return _env_data_path("PYTHIA_MINING_SESSION_PATH", "mining_session.json")


def telemetry_history_payload(limit: Any = 256, kind: Any = None) -> dict[str, Any]:
    """Durable operational history — real records the worker appended (§7)."""
    try:
        count = max(1, min(int(limit), 500))
    except (TypeError, ValueError):
        count = 256
    kinds = None
    if isinstance(kind, str) and kind.strip():
        kinds = {item.strip() for item in kind.split(",") if item.strip()}
    path = _telemetry_history_path()
    records = _jsonl_tail(path, count, kinds)
    return {
        "schema": "pythia.telemetry_history/1",
        "generated_at": now_iso(),
        "available": bool(records),
        "reason": (
            None if records else "the mining worker has not persisted telemetry history yet"
        ),
        "store": _file_evidence(path),
        "count": len(records),
        "records": records,
    }


def causal_events_payload(limit: Any = 128) -> dict[str, Any]:
    """The persisted causal ledger's tail — durable causal evidence (§10)."""
    try:
        count = max(1, min(int(limit), 500))
    except (TypeError, ValueError):
        count = 128
    path = _causal_log_path()
    records = _jsonl_tail(path, count)
    return {
        "schema": "pythia.causal_tail/1",
        "generated_at": now_iso(),
        "available": bool(records),
        "reason": (None if records else "the causal ledger has no persisted events yet"),
        "store": _file_evidence(path),
        "count": len(records),
        "records": records,
    }


def mining_session_payload() -> dict[str, Any]:
    """The durable mining lifecycle: state, cycle count and the share log."""
    path = _mining_session_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {
            "schema": "pythia.mining_session/1",
            "generated_at": now_iso(),
            "available": False,
            "reason": "no persisted mining session",
            "store": _file_evidence(path),
        }
    share_log = raw.get("share_log") if isinstance(raw.get("share_log"), list) else []
    pending = raw.get("pending") if isinstance(raw.get("pending"), dict) else None
    return {
        "schema": "pythia.mining_session/1",
        "generated_at": now_iso(),
        "available": True,
        "store": _file_evidence(path),
        "state": raw.get("state"),
        "cycles": raw.get("cycles"),
        "history": raw.get("history")[-16:] if isinstance(raw.get("history"), list) else None,
        "last_block_hash": raw.get("last_block_hash"),
        "share_count": len(share_log),
        "share_log": share_log[-64:],
        "pending": (
            {
                "job_id": pending.get("job_id"),
                "block_hash": pending.get("block_hash"),
                "parent_height": pending.get("parent_height"),
                "block_candidate": pending.get("block_candidate"),
                "outcome": pending.get("outcome"),
                "submission_id": pending.get("submission_id"),
                "sent_at": pending.get("sent_at"),
            }
            if pending
            else None
        ),
    }


def ops_telemetry_payload() -> dict[str, Any]:
    """The canonical operational-telemetry contract (spec §2).

    One document assembled from the channels that already carry truth: the
    worker's published Stratum snapshot (pool/session/job/submission state,
    measured outcomes, lifecycle flags, pool topology), the derived event
    stream, the measured-hashing counters, the supervisor's worker records,
    the persisted stores' provenance, and the guardian's public status.
    Sections with no source yet answer available=false with a reason; the
    frontend renders ``Unavailable``, never a synthesized value.
    """
    control = _control_plane()
    records = control.records()
    stratum = _stratum_status_payload(control, records)
    metrics = _read_metrics("agentic-mining")
    ready, ready_reason = _ready_to_mine_reason(records, stratum)
    security_code, security = security_status_payload()
    evidence = _metrics_json("agentic-mining", "mining_evidence")

    history_path = _telemetry_history_path()
    history_store = _file_evidence(history_path)
    causal_store = _file_evidence(_causal_log_path())
    session_store = _file_evidence(_mining_session_path())
    session = mining_session_payload()

    hashing = None
    if "hashrate_hs" in metrics:
        hashing = {
            key: metrics.get(key)
            for key in (
                "hashrate_hs",
                "hashes_total",
                "hashes_in_span",
                "span_s",
                "executions_total",
                "shares_accepted",
                "stale_candidates_dropped",
                "backend",
            )
        }
    events = telemetry_events_payload(64)

    job = stratum.get("job") if isinstance(stratum.get("job"), dict) else {}
    pool_topology = stratum.get("pool") if isinstance(stratum.get("pool"), dict) else None

    return {
        "schema": "pythia.ops_telemetry/1",
        "generated_at": now_iso(),
        "sources": {
            "stratum": "agentic-mining heartbeat key 'stratum_status'",
            "events": "agentic-mining heartbeat key 'stratum_events'",
            "hashing": "agentic-mining heartbeat counters",
            "workers": "supervisor worker records (heartbeat-verified)",
            "history": str(history_path.name),
            "causal": _causal_log_path().name,
            "session": _mining_session_path().name,
            "security": "AL HARAS guardian public_status",
        },
        "system": {
            "supervisor_started_at": control.started_at,
            "uptime_s": round(time.monotonic() - control.started_monotonic, 1),
            "ready_to_mine": ready,
            "ready_reason": ready_reason,
            "workers": {record.worker_id: record.public() for record in records},
        },
        "pool": {
            "available": stratum.get("evidence_available") is True,
            "state": stratum.get("state"),
            "primary": stratum.get("primary"),
            "lifecycle": stratum.get("lifecycle"),
            "topology": pool_topology,
            "session_id": stratum.get("session_id"),
            "protocol": stratum.get("protocol"),
            "configured": _configured_pools(),
        },
        "job": job
        | {
            "available": stratum.get("evidence_available") is True and bool(job.get("active")),
            "reason": (
                None
                if stratum.get("evidence_available") and job.get("active")
                else (
                    "no current job"
                    if stratum.get("evidence_available")
                    else "waiting for telemetry"
                )
            ),
        },
        "execution": {
            "device": {
                "bound": control.mining_device_bound(),
                "mmio_bridge_configured": bool(control.mmio_device),
                "execution_device": control.execution_device or None,
                "reason": (
                    None
                    if control.mining_device_bound()
                    else _mining_device_reason(control) or "no mining device bound"
                ),
            },
            "backend": (evidence.get("execution_backend") if isinstance(evidence, dict) else None),
            "hashing": hashing,
        },
        "shares": {
            "counters": stratum.get("counters"),
            "outcomes": stratum.get("outcomes"),
            "submission": stratum.get("submission"),
            "session": {
                "available": session["available"],
                "state": session.get("state") if session["available"] else None,
                "share_count": session.get("share_count") if session["available"] else None,
                "share_log": session.get("share_log") if session["available"] else [],
            },
        },
        "events": {
            "available": events.get("available", False),
            "reason": events.get("reason"),
            "last_seq": events.get("last_seq"),
            "totals": events.get("totals"),
            "events": events.get("events", []),
        },
        "healing": {
            "autonomous_supervisor": autonomous_supervisor.status(),
            "recovery": (evidence.get("recovery") if isinstance(evidence, dict) else None),
            # The Salamander engine's own step() result — only present when
            # the worker is actually running and reporting (§9).
            "salamander": _metrics_json("salamander", "salamander"),
            "workers": {
                record.worker_id: {
                    "state": record.state,
                    "liveness": record.liveness,
                    "readiness": record.readiness,
                }
                for record in records
            },
        },
        "security": _ops_security_section(security, security_code),
        "history": {
            "telemetry_history": history_store | {"record_tail": _jsonl_tail(history_path, 64)},
            "causal_ledger": causal_store,
            "mining_session": session_store
            | {"share_count": session.get("share_count") if session["available"] else None},
        },
    }


def _configured_pools() -> list[dict[str, Any]]:
    """The operator's configured pool roster — the declared failover order."""
    try:
        pools = runtime_config.public_view().get("pools") or []
    except Exception:
        return []
    return [p for p in pools if isinstance(p, dict)]


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


def _ops_security_section(security: dict[str, Any], security_code: HTTPStatus) -> dict[str, Any]:
    """The ops contract's guardian section.

    Beyond ``public_status`` the unprivileged observer provably sees the
    gate's evaluated answer: every privileged request is preflighted and an
    unauthenticated call is denied at the boundary. We embed exactly that
    verdict — produced by the same evaluate() path the request would hit —
    so the UI can show "gate closed: <reason>" as truth, not a guess.
    """
    if security_code != HTTPStatus.OK:
        return {"available": False, "reason": security.get("reason", "unavailable")}
    section = dict(security)
    try:
        _code, verdict = pythia_guardian_api().evaluate(
            headers={},
            body={
                "operation": "security.status",
                "resource": "security/status",
                "payload": {},
            },
        )
        section["gate"] = {
            "allowed": verdict.get("allowed"),
            "reason": verdict.get("reason"),
            "policy_version": verdict.get("policy_version"),
            "evaluated_at": verdict.get("evaluated_at"),
        }
    except Exception:
        section["gate"] = {"available": False, "reason": "evaluation_failed"}
    return section


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
    api_fabric = _REQUEST_STATS.prometheus()
    chunks = [chunk for chunk in (runtime, extra, api_fabric) if chunk]
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
        return HTTPStatus.BAD_REQUEST, {
            "failure_class": "INVALID_REQUEST",
            "error": f"unknown config sections: {', '.join(unknown)}",
        }
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
            {
                "ok": False,
                "failure_class": "NOT_CONFIGURED",
                "error": "repo_engineer_not_configured",
                "readiness": readiness,
            },
        )
    try:
        started = system_fabric.start_repo_engineer(prompt)
    except ValueError as exc:
        return HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)}
    if not started:
        return HTTPStatus.CONFLICT, {"ok": False, "error": "runner_busy"}
    return HTTPStatus.ACCEPTED, {"ok": True, "state": "running"}


def _euclid_cognition_solve(body: dict[str, Any]) -> tuple[HTTPStatus, dict[str, Any]]:
    """Execute one real EUCLID cognition episode and return its trace."""
    problem_id = body.get("problem_id")
    goal = body.get("goal")
    if not isinstance(problem_id, str) or not problem_id.strip():
        return HTTPStatus.BAD_REQUEST, {
            "ok": False, "error": "problem_id_required", "available": False,
        }
    if not isinstance(goal, str) or not goal.strip():
        return HTTPStatus.BAD_REQUEST, {
            "ok": False, "error": "goal_required", "available": False,
        }

    def _str_tuple(key: str, limit: int = 64) -> tuple[str, ...]:
        raw = body.get(key) or ()
        if not isinstance(raw, (list, tuple)):
            return ()
        return tuple(str(item)[:200] for item in raw[:limit])

    result = system_fabric.euclid_cognition_solve(
        problem_id.strip(),
        goal.strip(),
        problem_class=str(body.get("problem_class") or "repository-wiring")[:120],
        structure=_str_tuple("structure"),
        observations=_str_tuple("observations"),
        strategy=str(body.get("strategy") or "")[:60],
        initial_code=str(body.get("initial_code") or "")[:20_000],
    )
    if not result.get("available"):
        return HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, **result}
    return HTTPStatus.OK, {"ok": True, **result}


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
            "failure_class": "NOT_CONFIGURED",
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


_TENSOR_RUNTIME_GUARD = threading.Lock()
_TENSOR_RUNTIME: Any = None


def _tensor_runtime() -> Any:
    """Lazily construct the canonical TensorRuntime the API serves.

    Deferred to the first /api/v1/tensor/* request so control-plane startup
    and read-only GETs never pay the custody/backend import.
    """
    global _TENSOR_RUNTIME
    with _TENSOR_RUNTIME_GUARD:
        if _TENSOR_RUNTIME is None:
            from tensor.api import default_runtime

            _TENSOR_RUNTIME = default_runtime()
        return _TENSOR_RUNTIME


def tensor_capabilities_payload() -> dict[str, Any]:
    """GET /api/v1/tensor/capabilities — the runtime's honest catalogue."""
    return _tensor_runtime().capabilities()


def _synthesize_preflight_observation(path: str, body: dict[str, Any] | None) -> None:
    """Give tensor.execute the same synthesized observation GETs receive.

    The execute payload IS the caller's declared intent — requiring a
    separate ``observation`` map would deny every natural body with
    OBSERVATION_REQUIRED. The guardian's evidence provider still runs on
    the synthesized map. Any caller-supplied observation wins.
    """
    if path != "/api/v1/tensor/execute" or not isinstance(body, dict):
        return
    body.setdefault(
        "observation",
        {"operation": "tensor.execute", "resource": "tensor/execute"},
    )


def _tensor_execute(body: dict[str, Any]) -> tuple[HTTPStatus, dict[str, Any]]:
    """POST /api/v1/tensor/execute — canonical tensor.execute surface.

    Body shapes:
      {"operation": "add", "inputs": ["a", "b"]}
        run folded-resident over resident blocks a,b
      {"operation": "add", "operands": [[[..]], [[..]]], "dtype": "float64"}
        run the backend path over inline arrays
      {"operation": "add", "tensors": {"a": [[..]], "b": [[..]]}}
        take custody of each payload first, then run folded-resident
    """
    import numpy as np

    operation = str(body.get("operation") or "").strip()
    if not operation:
        raise ValueError("operation is required")
    dtype = str(body.get("dtype", "float64"))
    rt = _tensor_runtime()
    request_tag = f"api-{int(time.time_ns())}"

    inputs = body.get("inputs")
    tensors = body.get("tensors")
    if tensors is not None:
        if not isinstance(tensors, dict) or not tensors:
            raise ValueError("tensors must be a non-empty {name: data} map")
        names = []
        for key, data in tensors.items():
            name = f"{request_tag}:{key}"
            rt.store_tensor(
                name,
                np.asarray(data, dtype=dtype),
                depth=int(body.get("depth", 3)),
            )
            names.append(name)
        inputs = names

    if inputs is None:
        operands = body.get("operands")
        if not isinstance(operands, list) or not operands:
            raise ValueError("request needs inputs, operands, or tensors")
        inputs = operands
    if not isinstance(inputs, list) or not inputs:
        raise ValueError("inputs must be a non-empty list")

    operand_values = [
        np.asarray(o, dtype=dtype) if isinstance(o, (list, tuple)) else str(o)
        for o in inputs
    ]
    record = rt.execute(
        operation,
        operand_values,
        out=body.get("out"),
        dtype=dtype,
        backend_required=body.get("backend"),
        request_id=str(body.get("request_id") or request_tag),
    )
    payload = {"schema_version": "tensor.execute/1", **record}
    if record.get("path") != "backend" and record.get("output"):
        payload["values"] = rt.read_tensor(record["output"]).tolist()
    return HTTPStatus.OK, payload


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
            m3_ready, m3_reason = _m3_dependency_reason()
            ready = bool(identity["ok"]) and m3_ready
            reason = (
                str(identity["reason"])
                if not identity["ok"]
                else (m3_reason if not m3_ready else "ok")
            )
            self._json(
                HTTPStatus.OK if ready else HTTPStatus.SERVICE_UNAVAILABLE,
                {
                    "schema_version": _READY_SCHEMA_VERSION,
                    "ready": ready,
                    "reason": reason,
                    "components": _readiness_components(),
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
        if path == "/api/v1/telemetry/ops":
            self._json(HTTPStatus.OK, ops_telemetry_payload())
            return
        if path == "/api/v1/telemetry/history":
            params = parse_qs(parsed.query)
            self._json(
                HTTPStatus.OK,
                telemetry_history_payload(
                    params.get("n", ["256"])[0], params.get("kind", [None])[0]
                ),
            )
            return
        if path == "/api/v1/telemetry/causal":
            params = parse_qs(parsed.query)
            self._json(HTTPStatus.OK, causal_events_payload(params.get("n", ["128"])[0]))
            return
        if path == "/api/v1/telemetry/session":
            self._json(HTTPStatus.OK, mining_session_payload())
            return
        if path == "/api/v1/telemetry/stream":
            self._telemetry_stream()
            return
        if path == "/api/v1/hardware/status":
            self._json(HTTPStatus.OK, hardware_status_payload())
            return
        if path == "/api/v1/security/status":
            self._json(*security_status_payload())
            return
        if path == "/api/v1/tensor/capabilities":
            self._json(HTTPStatus.OK, tensor_capabilities_payload())
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
        "/api/v1/intelligence/cognition/solve": _euclid_cognition_solve,
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
        "/api/v1/tensor/execute": _tensor_execute,
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
            self._discard_request_body()
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
            _synthesize_preflight_observation(parsed.path, body)
            if not self._guardian_preflight(parsed.path, body):
                return
        idem = _idempotency_key(self.headers)
        if idem:
            replay = _idempotency_lookup(idem)
            if replay is not None:
                status, payload = replay
                payload["idempotent_replay"] = True
                self._json(status, payload)
                return
        try:
            status, payload = handler(body)
        except ValueError as exc:
            self._json(
                HTTPStatus.BAD_REQUEST,
                {
                    "ok": False,
                    "failure_class": "INVALID_REQUEST",
                    "error": str(exc),
                },
            )
            return
        except Exception as exc:
            self._json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {
                    "ok": False,
                    "failure_class": "INTERNAL_ERROR",
                    "error": f"{type(exc).__name__}: {exc}",
                },
            )
            return
        if idem and isinstance(payload, dict):
            _idempotency_store(idem, int(status), payload)
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
        idem = _idempotency_key(self.headers)
        if idem:
            replay = _idempotency_lookup(idem)
            if replay is not None:
                status, payload = replay
                payload["idempotent_replay"] = True
                self._json(status, payload)
                return
        status, payload = _config_put(body)
        if idem and isinstance(payload, dict):
            _idempotency_store(idem, int(status), payload)
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

    def _telemetry_stream(self) -> None:
        """Server-Sent Events of the canonical ops telemetry (§11).

        Each frame carries one ``pythia.ops_telemetry/1`` document plus the
        new Stratum events since the last published ``last_seq``, so a
        client can keep its projection current without re-fetching. The
        connection stays open for a bounded window and closes cleanly —
        EventSource reconnects automatically; staleness is surfaced by the
        UI from ``generated_at`` ages.
        """
        self.send_response(int(HTTPStatus.OK))
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Security-Policy", self._CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        last_seq = 0
        # Bounded lifetime: the client reconnects and resumes from the
        # persisted ``last_seq`` the next frame reports.
        for _tick in range(120):
            try:
                payload = ops_telemetry_payload()
                new_events = _seq_gated_events(
                    payload["events"].get("events") or [], last_seq
                )
                if new_events:
                    last_seq = int(payload["events"].get("last_seq") or last_seq)
                frame = {
                    "type": "ops",
                    "seq": last_seq,
                    "ops": payload,
                    "new_events": new_events,
                }
                self.wfile.write(
                    b"data: "
                    + json.dumps(frame, sort_keys=True, default=str).encode("utf-8")
                    + b"\n\n"
                )
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                break
            try:
                self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                break
            time.sleep(1.5)

    def _correlation_id(self) -> str:
        """Correlation envelope: every response carries X-Request-Id.

        A caller-supplied ``X-Request-Id``/``X-Correlation-Id`` is echoed when
        it is a sane token; otherwise a fresh id is minted so every response is
        correlatable in the audit log and client telemetry.
        """
        candidate = (
            self.headers.get("X-Request-Id")
            or self.headers.get("X-Correlation-Id")
            or ""
        ).strip()
        if candidate and _REQUEST_ID_RE.fullmatch(candidate):
            return candidate
        return uuid.uuid4().hex

    def _correlation_envelope(self) -> dict[str, str]:
        """Full correlation envelope (service constitution §17).

        request_id is the response's canonical id; correlation_id echoes the
        caller's X-Correlation-Id (falling back to request_id); causation_id
        echoes a caller-supplied X-Causation-Id so a request can name the
        event that caused it. Malformed inbound ids are replaced, never
        trusted.
        """
        request_id = self._correlation_id()
        correlation = (self.headers.get("X-Correlation-Id") or "").strip()
        causation = (self.headers.get("X-Causation-Id") or "").strip()
        return {
            "request_id": request_id,
            "correlation_id": correlation
            if _REQUEST_ID_RE.fullmatch(correlation)
            else request_id,
            "causation_id": causation if _REQUEST_ID_RE.fullmatch(causation) else "",
        }

    def _send(
        self,
        status: int,
        content_type: str,
        body: bytes,
        cache_control: str = "no-store",
    ) -> None:
        self.send_response(int(status))
        envelope = self._correlation_envelope()
        self.send_header("X-Request-Id", envelope["request_id"])
        self.send_header("X-Correlation-Id", envelope["correlation_id"])
        if envelope["causation_id"]:
            self.send_header("X-Causation-Id", envelope["causation_id"])
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
        # Constitution §9: every error body carries a machine-readable
        # failure_class, even forwarded guardian receipts that lack one.
        payload = failure_taxonomy.ensure_failure_class(status, payload)
        _REQUEST_STATS.record(int(status), payload)
        body = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        self._send(int(status), "application/json; charset=utf-8", body)

    def _discard_request_body(self) -> None:
        """Consume a refused request's body before answering.

        Answering with unread bytes still on the socket can surface as a
        connection abort to the client (WinError 10053) instead of the
        intended status line.
        """
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length > 0:
            self._drain(length)

    def _refuse_unauthorized(self) -> bool:
        principal, refusal = authenticate_control_principal(self.headers)
        if refusal is None:
            assert principal is not None
            self._control_principal = principal
            _audit().append(
                "control_authorized",
                path=urlparse(self.path).path,
                principal_id=principal.principal_id,
                role=principal.role,
                source=principal.source,
            )
            return False
        status, reason = refusal
        _audit().append("control_refused", path=urlparse(self.path).path, reason=reason)
        self._discard_request_body()
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


def _seq_gated_events(events: list, last_seq: int) -> list:
    """Events strictly newer than the cursor — reordered or duplicated
    deliveries (seq <= last_seq) are never re-emitted to a client that has
    already seen them."""
    return [e for e in events if int(e.get("seq") or 0) > last_seq]


_PORTS_FILE_LOCK = threading.Lock()


def _write_active_ports(update: Any) -> None:
    """Merge-update the shared port file; other writers' keys survive.

    The read-modify-write is serialized in-process; publication is tmp +
    os.replace so a reader never sees a torn write. A torn or corrupt
    file is untrusted input — the next write recovers it.
    """
    path = _active_ports_path()
    with _PORTS_FILE_LOCK:
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
            # Unique temp name per write: same-process writers must not
            # clobber each other's temp file (Windows os.replace fails on
            # an in-use tmp).
            temporary = path.with_name(
                f"{path.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp"
            )
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
