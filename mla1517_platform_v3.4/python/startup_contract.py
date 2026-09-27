"""Fail-closed startup contracts shared by the main control service."""
from __future__ import annotations

try:
    import fcntl
except ImportError:  # Windows hosts have no fcntl; msvcrt covers them.
    fcntl = None
import hashlib
import hmac
import json
import os
import secrets
import time
import socket
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_BOOT_SECRET = b""
_SUPERVISOR_EPOCH = ""


def rotate_supervisor_secret() -> tuple[str, str]:
    global _BOOT_SECRET, _SUPERVISOR_EPOCH
    _SUPERVISOR_EPOCH = secrets.token_hex(8)
    _BOOT_SECRET = os.urandom(32)
    os.environ["PYTHIA_IDENTITY_HMAC_SECRET"] = _BOOT_SECRET.hex()
    os.environ["PYTHIA_SUPERVISOR_EPOCH"] = _SUPERVISOR_EPOCH
    return _SUPERVISOR_EPOCH, _BOOT_SECRET.hex()


def identity_hmac_status() -> tuple[bool, str]:
    if not _BOOT_SECRET:
        return False, "identity_hmac_missing"
    if len(_BOOT_SECRET) != 32:
        return False, "identity_hmac_malformed"
    return True, "ok"


rotate_supervisor_secret()

STATES = {
    "disabled", "armed_no_device", "starting", "ready", "running",
    "restarting", "stopping", "stopped", "failed",
}
TRANSITIONS = {
    "disabled": {"armed_no_device", "stopped"},
    "armed_no_device": {"starting", "disabled"},
    "starting": {"ready", "failed", "stopping"},
    "ready": {"running", "stopping"},
    "running": {"restarting", "stopping", "failed"},
    "restarting": {"starting", "failed"},
    "stopping": {"stopped"},
    "stopped": {"starting", "disabled"},
    "failed": {"starting", "disabled"},
}


class StateViolation(RuntimeError):
    pass


class ConfigConflict(ValueError):
    pass


class StartupConfigError(ValueError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def redact_user(value: str) -> str:
    return (value[:2] + "***") if len(value) > 2 else "***"


def _endpoint(value: str, field: str) -> tuple[str, int]:
    raw = value.strip()
    if "://" in raw:
        raw = raw.split("://", 1)[1]
    host, sep, port = raw.rpartition(":")
    if not sep or not host or not port.isdigit():
        raise StartupConfigError(f"{field} must be HOST:PORT")
    port_i = int(port)
    if not 1 <= port_i <= 65535:
        raise StartupConfigError(f"{field} port outside 1..65535")
    return host.casefold(), port_i


@dataclass(frozen=True)
class StratumIdentity:
    user: str
    host: str
    port: int
    password_sha256: str
    profile: str

    def public(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "host": self.host,
            "port": self.port,
            "user_redacted": redact_user(self.user),
            "password_committed": True,
            "identity_commit": self.commit(),
        }

    def commit(self) -> str:
        # HMAC with a per-container secret prevents offline rainbow-table
        # recovery from the public commitment. The secret never enters audit
        # output or the status payload.
        body = f"mla1517.stratum.identity.v1|{self.profile}|{self.host}|{self.port}|{self.user}|{self.password_sha256}"
        return hmac.new(_BOOT_SECRET, body.encode(), hashlib.sha256).hexdigest()


def _conflict(field: str, canonical: str, alias: str) -> None:
    raise ConfigConflict(
        f"{field} conflicts with canonical MLA1517 value "
        f"(canonical={canonical[:2]}***, alias={alias[:2]}***)"
    )


def resolve_stratum_identity() -> StratumIdentity:
    """Resolve once at boot; aliases may confirm but never override canonical."""
    user = os.getenv("MLA1517_STRATUM_USER", "").strip()
    password = os.getenv("MLA1517_STRATUM_PASSWORD", "")
    profile = os.getenv("PYTHIA_POOL_PROFILE", os.getenv("MLA1517_POOL_PROFILE", "braiins")).strip().lower()
    if profile not in {"braiins", "viabtc"}:
        raise StartupConfigError("PYTHIA_POOL_PROFILE must be braiins or viabtc")
    if not user:
        raise StartupConfigError("MLA1517_STRATUM_USER is required")
    if not password:
        raise StartupConfigError("MLA1517_STRATUM_PASSWORD is required")
    alias_policy = os.getenv("PYTHIA_ALIAS_POLICY", "compat").strip().lower()
    if alias_policy not in {"compat", "strict", "ignore"}:
        raise StartupConfigError("PYTHIA_ALIAS_POLICY must be compat, strict, or ignore")
    alias_user = os.getenv("PYTHIA_STRATUM_WORKER", "").strip()
    alias_password = os.getenv("PYTHIA_STRATUM_PASSWORD", "")
    if alias_policy != "ignore":
        if alias_policy == "strict" and not alias_user:
            raise ConfigConflict("PYTHIA_STRATUM_WORKER is required by strict alias policy")
        if alias_user and alias_user != user:
            _conflict("worker", user, alias_user)
        if alias_policy == "strict" and not alias_password:
            raise ConfigConflict("PYTHIA_STRATUM_PASSWORD is required by strict alias policy")
        if alias_password and alias_password != password:
            raise ConfigConflict("password aliases conflict with canonical MLA1517 value")
    canonical_endpoint = os.getenv("MLA1517_STRATUM_ENDPOINT", "").strip()
    if not canonical_endpoint:
        canonical_endpoint = os.getenv(
            "MLA1517_BRAIINS_ENDPOINT" if profile == "braiins" else "MLA1517_VIABTC_ENDPOINT", ""
        ).strip()
    alias_endpoint = os.getenv("PYTHIA_STRATUM_ENDPOINT", "").strip()
    if not canonical_endpoint:
        raise StartupConfigError("canonical MLA1517 Stratum endpoint is required")
    if alias_policy != "ignore" and alias_endpoint:
        if _endpoint(alias_endpoint, "PYTHIA_STRATUM_ENDPOINT") != _endpoint(canonical_endpoint, "MLA1517_STRATUM_ENDPOINT"):
            raise ConfigConflict("endpoint aliases conflict with canonical MLA1517 value")
    if alias_policy == "strict" and not alias_endpoint:
        raise ConfigConflict("PYTHIA_STRATUM_ENDPOINT is required by strict alias policy")
    host, port = _endpoint(canonical_endpoint, "MLA1517_STRATUM_ENDPOINT")
    return StratumIdentity(user, host, port, hashlib.sha256(password.encode()).hexdigest(), profile)


FS_POLICY = {
    "ext4": {"dir_fsync": "SUPPORTED", "rename_atomic": True, "policy": "STRICT"},
    "xfs": {"dir_fsync": "SUPPORTED", "rename_atomic": True, "policy": "STRICT"},
    "overlayfs": {"dir_fsync": "MAYBE", "rename_atomic": True, "policy": "LENIENT"},
    "tmpfs": {"dir_fsync": "NOOP", "rename_atomic": True, "policy": "LENIENT"},
    "nfs": {"dir_fsync": "MAYBE", "rename_atomic": False, "policy": "LENIENT_WITH_WARN"},
    "efs": {"dir_fsync": "MAYBE", "rename_atomic": True, "policy": "LENIENT"},
}


def detect_filesystem(path: str | os.PathLike[str]) -> str:
    try:
        import subprocess
        return subprocess.check_output(["stat", "-f", "-c", "%T", str(path)], text=True, timeout=2).strip()
    except Exception:
        return "unknown"


def fs_selfcheck(path: str | os.PathLike[str], audit: "AppendOnlyAudit") -> dict[str, Any]:
    fstype = detect_filesystem(path)
    recommendation = FS_POLICY.get(fstype, {"policy": "UNKNOWN", "dir_fsync": "UNKNOWN", "rename_atomic": None})
    configured = os.getenv("PYTHIA_DIR_FSYNC_POLICY", "LENIENT").upper()
    result = {"path": str(path), "fstype": fstype, "configured": configured, **recommendation}
    audit.append("fs_selfcheck", **result)
    if recommendation["policy"] not in {"UNKNOWN", configured, "LENIENT_WITH_WARN" if configured == "LENIENT" else configured}:
        print(f"[pythia-control] fs_policy_mismatch fstype={fstype} configured={configured} recommended={recommendation['policy']}")
    return result


class RuntimeMetrics:
    def __init__(self) -> None:
        self.counters: dict[str, float] = {}
        self.gauges: dict[str, float] = {}

    def inc(self, name: str, value: float = 1.0) -> None:
        self.counters[name] = self.counters.get(name, 0.0) + value

    def set(self, name: str, value: float) -> None:
        self.gauges[name] = value

    def prometheus(self) -> str:
        lines = []
        for name, value in sorted(self.counters.items()):
            lines.append(f"{name} {value}")
        for name, value in sorted(self.gauges.items()):
            lines.append(f"{name} {value}")
        return "\n".join(lines) + ("\n" if lines else "")


METRICS = RuntimeMetrics()


class AppendOnlyAudit:
    def __init__(self, path: str | os.PathLike[str] | None = None) -> None:
        self.path = Path(path or os.getenv("PYTHIA_BOOT_AUDIT", "/app/data/BOOT_AUDIT.log"))
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: str, **payload: Any) -> None:
        record = {"at": now_iso(), "event": event, **payload}
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        METRICS.inc("pythia_boot_audit_lines_total")
        METRICS.set("pythia_boot_audit_last_write_timestamp_seconds", time.time())

    def tail(self, n: int = 50) -> list[dict[str, Any]]:
        """Return the last ``n`` audit records, oldest-first.

        The audit file is append-only JSONL; history is read from disk so a
        restarted UI still sees the full operator trail.
        """
        if n <= 0:
            return []
        try:
            lines = self.path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return []
        records: list[dict[str, Any]] = []
        for line in lines[-n:]:
            try:
                parsed = json.loads(line)
            except ValueError:
                continue
            if isinstance(parsed, dict):
                records.append(parsed)
        return records


@dataclass
class WorkerRecord:
    worker_id: str
    script: str
    state: str
    since: str = field(default_factory=now_iso)
    attempts_total: int = 0
    attempts_window: int = 0
    last_heartbeat: str | None = None
    liveness: bool = False
    readiness: bool = False
    hashrate: float = 0.0
    shares_accepted: int = 0
    last_error: dict[str, str] | None = None

    def public(self) -> dict[str, Any]:
        return {"state": self.state, "since": self.since, "attempts_total": self.attempts_total,
                "attempts_window": self.attempts_window, "last_heartbeat": self.last_heartbeat,
                "liveness": self.liveness, "readiness": self.readiness,
                "effectiveness": {"hashrate": self.hashrate, "shares_accepted": self.shares_accepted},
                "last_error": self.last_error}

    def transition(self, to: str, audit: AppendOnlyAudit, reason: str) -> None:
        if to not in STATES or to not in TRANSITIONS[self.state]:
            raise StateViolation(f"{self.worker_id}: {self.state} -> {to} is illegal")
        old = self.state
        self.state = to
        self.since = now_iso()
        audit.append("worker_transition", worker=self.worker_id, from_state=old, to_state=to, reason=reason)


class BootLock:
    def __init__(self, path: str | os.PathLike[str] | None = None) -> None:
        self.path = Path(path or os.getenv("PYTHIA_BOOT_LOCK", "/app/data/pythia-main.lock"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = None

    def acquire(self) -> bool:
        self._fh = self.path.open("a+")
        try:
            if fcntl is not None:
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            else:
                import msvcrt

                self._fh.seek(0)
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
            self._fh.write(f"pid={os.getpid()} host={socket.gethostname()}\n")
            self._fh.flush()
            return True
        except OSError:
            self._fh.close()
            self._fh = None
            return False

    def release(self) -> None:
        if self._fh is not None:
            if fcntl is not None:
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
            else:
                import msvcrt

                self._fh.seek(0)
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
            self._fh.close()
            self._fh = None
