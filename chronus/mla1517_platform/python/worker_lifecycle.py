"""Durable epoch/sequence/monotonic heartbeats for supervised workers."""

from __future__ import annotations

import errno
import hashlib
import hmac
import json
import logging
import os
import secrets
import struct
import tempfile
import threading
import time
from pathlib import Path

LOG = logging.getLogger("pythia.worker_lifecycle")

MAGIC = b"PYHB"
VERSION = 1
HEARTBEAT_BODY_STRUCT = struct.Struct("<4sHQQQ")  # magic, version, epoch, seq, monotonic_ns
HEARTBEAT_STRUCT = struct.Struct("<4sHQQQ32s")  # body + supervisor HMAC


def _default_heartbeat_dir() -> str:
    if os.name == "nt":
        base = os.getenv("LOCALAPPDATA") or tempfile.gettempdir()
        return str(Path(base) / "pythia" / "hb")
    return "/run/pythia/hb"


def _heartbeat_secret() -> bytes | None:
    raw = os.getenv("PYTHIA_IDENTITY_HMAC_SECRET", "").strip()
    if not raw:
        return None
    try:
        secret = bytes.fromhex(raw)
    except ValueError:
        return None
    return secret if len(secret) == 32 else None


def _heartbeat_tag(secret: bytes, worker_id: str, body: bytes) -> bytes:
    return hmac.new(secret, worker_id.encode("utf-8") + body, hashlib.sha256).digest()


def _replace_retry(src: Path, dst: Path, attempts: int = 3) -> None:
    for attempt in range(attempts):
        try:
            src.replace(dst)
            return
        except PermissionError:
            # Windows: replace over a file a reader holds open is denied where
            # POSIX rename is unconditional; brief retry covers the transient.
            if attempt == attempts - 1:
                src.unlink(missing_ok=True)
                raise
            time.sleep(0.01)


class HeartbeatChannelBroken(RuntimeError):
    pass


def _fsync_dir(path: Path) -> None:
    if os.name == "nt":
        # POSIX-only durability idiom: os.open on a directory raises
        # PermissionError on Windows. The payload file fsync still provides
        # content durability; the directory-entry fsync runs on the Linux
        # deployment target.
        return
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class HeartbeatEmitter:
    """Write epoch + sequence + monotonic timestamp atomically."""

    def __init__(self, worker_id: str, interval: float = 1.0) -> None:
        self.worker_id = worker_id
        self.interval = interval
        self.directory = Path(os.getenv("PYTHIA_WORKER_HEARTBEAT_DIR", _default_heartbeat_dir()))
        self.path = self.directory / f"{worker_id}.bin"
        self.metrics_path = self.directory / f"{worker_id}.metrics.json"
        self.worker_epoch = secrets.randbits(64)
        self.seq = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_warning = 0.0
        self._phases: dict[str, dict[str, float]] = {}
        self._counters: dict[str, float | int | str] = {}
        self._lock = threading.Lock()
        self._secret = _heartbeat_secret()
        self._latencies: list[float] = []
        self._p95_latency: float = 0.0
        self._probe_channel()

    def report(self, **counters: float | int | str) -> None:
        """Record measured worker counters for the metrics payload.

        Values must be measured by the caller (real computed rates and
        counters) — the emitter transports them; it never derives them.
        """
        with self._lock:
            self._counters.update(counters)

    def _probe_channel(self) -> None:
        probe = self.path.with_suffix(".probe")
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            probe.write_bytes(b"probe")
            with probe.open("rb") as fh:
                if fh.read() != b"probe":
                    raise HeartbeatChannelBroken("heartbeat probe readback mismatch")
            probe.unlink(missing_ok=True)
            _fsync_dir(probe.parent)
        except OSError as exc:
            raise HeartbeatChannelBroken(f"heartbeat channel unavailable: {exc}") from exc

    def _phase(self, name: str, start: float) -> None:
        duration = time.perf_counter() - start
        item = self._phases.setdefault(
            name,
            {
                "count": 0.0,
                "sum_seconds": 0.0,
                "last_seconds": 0.0,
                "buckets": {
                    str(bound): 0 for bound in (0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, "+Inf")
                },
            },
        )
        item["count"] += 1
        item["sum_seconds"] += duration
        item["last_seconds"] = duration
        for bound in (0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0):
            if duration <= bound:
                item["buckets"][str(bound)] += 1
        item["buckets"]["+Inf"] += 1

    def _write_metrics(self, total: float) -> None:
        with self._lock:
            self._latencies.append(total)
            if len(self._latencies) > 500:
                self._latencies.pop(0)
            if len(self._latencies) >= 3:
                sorted_l = sorted(self._latencies)
                idx = int(0.95 * (len(sorted_l) - 1))
                self._p95_latency = sorted_l[idx]
            else:
                self._p95_latency = total
            self._counters["heartbeat_p95_seconds"] = round(self._p95_latency, 6)
            self._counters["heartbeat_last_seconds"] = round(total, 6)
            counters = dict(self._counters)
        payload = {
            "worker": self.worker_id,
            "write_total_seconds": total,
            "heartbeat_p95_seconds": self._p95_latency,
            "phases": self._phases,
            "counters": counters,
        }
        temporary = self.metrics_path.with_suffix(".metrics.tmp")
        temporary.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        try:
            _replace_retry(temporary, self.metrics_path)
        except PermissionError:
            # Metrics are observational, not the liveness contract: drop the
            # sample rather than kill the emitter loop on a locked destination.
            return
        if self.seq % 10 == 0 or total > 0.5:
            LOG.info(
                "[pythia-heartbeat] worker=%s seq=%d latency=%.6fs p95=%.6fs target=<1.0s",
                self.worker_id,
                self.seq,
                total,
                self._p95_latency,
            )
        if total > float(os.getenv("PYTHIA_HEARTBEAT_STALE_THRESHOLD", "5")) * float(
            os.getenv("PYTHIA_HEARTBEAT_SLOW_FRACTION", "0.5")
        ):
            now = time.monotonic()
            if now - self._last_warning >= 60.0:
                self._last_warning = now
                print(
                    f"[pythia-heartbeat] heartbeat_slow worker={self.worker_id} total_seconds={total:.6f} p95={self._p95_latency:.6f}"
                )

    def tick(self) -> None:
        total_start = time.perf_counter()
        self.seq += 1
        start = time.perf_counter()
        body = HEARTBEAT_BODY_STRUCT.pack(
            MAGIC, VERSION, self.worker_epoch, self.seq, time.monotonic_ns()
        )
        blob = body + _heartbeat_tag(self._secret, self.worker_id, body)
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.{os.getpid()}.{self.seq}.tmp")
        start = time.perf_counter()
        for attempt in range(10):
            try:
                with temporary.open("wb") as fh:
                    fh.write(blob)
                    fh.flush()
                    os.fsync(fh.fileno())
                break
            except OSError:
                if attempt == 9:
                    raise
                time.sleep(0.005)
        self._phase("write", start)
        self._phase("fsync_file", start)
        start = time.perf_counter()
        for _attempt in range(50):
            try:
                temporary.replace(self.path)
                break
            except (PermissionError, OSError):
                # Windows denies replace while a reader holds the
                # destination open; POSIX rename is atomic over open
                # files. Bounded retry between reader polls only on nt.
                if os.name != "nt":
                    raise
                time.sleep(0.005)
        else:
            # Sustained reader pressure outlasted the retry window: drop this
            # tick rather than crash the worker mid-window. Liveness retries
            # every interval; a lost tick is cheaper than a dead mining arm.
            try:
                temporary.unlink()
            except OSError:
                pass
            return
        self._phase("rename", start)
        start = time.perf_counter()
        try:
            _fsync_dir(self.path.parent)
        except OSError as exc:
            policy = os.getenv("PYTHIA_DIR_FSYNC_POLICY", "STRICT").upper()
            unsupported = {errno.EINVAL, errno.ENOTSUP, errno.EOPNOTSUPP}
            if not (policy == "LENIENT" and exc.errno in unsupported):
                raise
        self._phase("fsync_dir", start)
        total = time.perf_counter() - total_start
        self._write_metrics(total)

    def __enter__(self):
        self.tick()
        self._thread = threading.Thread(
            target=self._loop, name=f"heartbeat-{self.worker_id}", daemon=True
        )
        self._thread.start()
        return self

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                self.tick()
            except Exception as exc:
                LOG.warning("Heartbeat tick failed for %s: %s", self.worker_id, exc)

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        for path in (self.path, self.metrics_path):
            try:
                path.unlink()
            except FileNotFoundError:
                pass


class HeartbeatReader:
    def __init__(self, worker_id: str) -> None:
        self.worker_id = worker_id
        self.directory = Path(os.getenv("PYTHIA_WORKER_HEARTBEAT_DIR", _default_heartbeat_dir()))
        self.path = self.directory / f"{worker_id}.bin"
        self.last_epoch: int | None = None
        self.last_seq = 0
        self.last_seen_mono = time.monotonic_ns()
        self._secret = _heartbeat_secret()

    def poll(self) -> dict[str, int | str | None]:
        blob: bytes | None = None
        for attempt in range(3):
            try:
                blob = self.path.read_bytes()
                break
            except FileNotFoundError:
                return {"kind": "missing", "age_ns": None, "seq": None, "epoch": None}
            except PermissionError:
                # Windows: opening mid-os.replace transiently fails where POSIX
                # atomics always succeed; bounded retry then report honestly.
                if attempt == 2:
                    return {"kind": "unreadable", "age_ns": None, "seq": None, "epoch": None}
                time.sleep(0.01)
        assert blob is not None
        if len(blob) != HEARTBEAT_STRUCT.size:
            return {"kind": "malformed", "age_ns": None, "seq": None, "epoch": None}
        body = blob[: HEARTBEAT_BODY_STRUCT.size]
        tag = blob[HEARTBEAT_BODY_STRUCT.size :]
        magic, version, epoch, seq, _worker_mono = HEARTBEAT_BODY_STRUCT.unpack(body)
        if magic != MAGIC or version != VERSION:
            return {
                "kind": "malformed",
                "age_ns": None,
                "seq": seq,
                "epoch": epoch,
                "error": "header_invalid",
            }
        if self._secret is None or not hmac.compare_digest(
            tag, _heartbeat_tag(self._secret, self.worker_id, body)
        ):
            return {
                "kind": "malformed",
                "age_ns": None,
                "seq": seq,
                "epoch": epoch,
                "error": "hmac_invalid",
            }
        if self.last_epoch is None:
            self.last_epoch, self.last_seq, self.last_seen_mono = epoch, seq, time.monotonic_ns()
            return {"kind": "fresh", "age_ns": 0, "seq": seq, "epoch": epoch}
        if epoch != self.last_epoch:
            old = self.last_epoch
            self.last_epoch, self.last_seq, self.last_seen_mono = epoch, seq, time.monotonic_ns()
            return {
                "kind": "epoch_change",
                "age_ns": 0,
                "seq": seq,
                "epoch": epoch,
                "old_epoch": old,
            }
        if seq <= self.last_seq:
            if seq < self.last_seq:
                return {"kind": "regressed", "age_ns": None, "seq": seq, "epoch": epoch}
            return {
                "kind": "stale",
                "age_ns": time.monotonic_ns() - self.last_seen_mono,
                "seq": seq,
                "epoch": epoch,
            }
        self.last_seq, self.last_seen_mono = seq, time.monotonic_ns()
        return {"kind": "fresh", "age_ns": 0, "seq": seq, "epoch": epoch}


# Backward-compatible production name used by mining_runtime.py and salamander_engine.py.
WorkerHeartbeat = HeartbeatEmitter
