"""Tamper-evident, data-minimising AL HARAS decision ledger."""

from __future__ import annotations

import copy
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import threading
import time
from typing import Any, Iterable, Mapping

try:
    import fcntl
except ImportError:  # pragma: no cover - Linux containers are the production target.
    fcntl = None


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


class AuditIntegrityError(RuntimeError):
    """Existing durable audit state is malformed or hash-chain invalid."""


_TAIL_READ_BYTES = 64 * 1024


class HashChainAudit:
    """Append-only decision records.

    Records contain identifiers, hashes, and policy outcomes; client payloads are
    never persisted. Local JSONL is a container spool, not a WORM claim.

    Appends verify the durable tail only: the whole chain is verified once at
    construction, then each append links to the file's actual last record while
    holding the exclusive lock. This keeps append cost independent of ledger
    length and prevents interleaved writers from forking the chain.
    """

    def __init__(self, path: Path | None = None, *, quarantine: bool = False) -> None:
        self.path = path
        self._quarantine = quarantine
        self._quarantine_stamp: str | None = None
        self._records: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        if path is not None:
            if fcntl is None:
                raise RuntimeError("persistent AL HARAS audit requires POSIX file locking")
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.chmod(path.parent, 0o700)
            except OSError:
                pass
            with self._file_lock():
                self._records = self._load_or_quarantine_unlocked()

    def _load_or_quarantine_unlocked(self) -> list[dict[str, Any]]:
        """Verify the whole durable chain at startup; on corruption either
        fail closed or quarantine the damaged spool and resume on a fresh
        chain whose first event records the recovery."""
        try:
            records = self._read_records_unlocked()
        except AuditIntegrityError:
            if not self._quarantine:
                raise
            self._quarantine_file_unlocked()
            records = []
        if not self.verify(records):
            if not self._quarantine:
                raise AuditIntegrityError("existing AL HARAS audit chain is corrupt")
            self._quarantine_file_unlocked()
            records = []
        if self._quarantine_stamp is not None:
            self._append_unlocked(
                {
                    "schema_version": "al-haras.audit-recovery.v1",
                    "event": "audit_quarantined",
                    "quarantined_to": self._quarantine_stamp,
                },
                records,
            )
        return records

    def _quarantine_file_unlocked(self) -> None:
        if self.path is None or not self.path.exists():
            self._quarantine_stamp = "empty"
            return
        stamp = f"{self.path.name}.corrupt-{int(time.time())}"
        target = self.path.with_name(stamp)
        os.replace(self.path, target)
        self._quarantine_stamp = target.name

    @property
    def records(self) -> tuple[dict[str, Any], ...]:
        if self.path is None:
            with self._lock:
                return tuple(copy.deepcopy(self._records))
        with self._file_lock():
            records = self._read_records_unlocked()
            if not self.verify(records):
                raise AuditIntegrityError("existing AL HARAS audit chain is corrupt")
            self._records = records
            return tuple(copy.deepcopy(records))

    @contextmanager
    def _file_lock(self):
        if self.path is None:
            yield
            return
        lock_path = self.path.with_name(f"{self.path.name}.lock")
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _read_records_unlocked(self) -> list[dict[str, Any]]:
        if self.path is None or not self.path.exists():
            return []
        records: list[dict[str, Any]] = []
        try:
            with self.path.open("r", encoding="utf-8") as source:
                for line_number, line in enumerate(source, 1):
                    if not line.strip():
                        continue
                    value = json.loads(line)
                    if not isinstance(value, dict):
                        raise AuditIntegrityError(f"audit line {line_number} is not an object")
                    records.append(value)
        except (OSError, json.JSONDecodeError) as exc:
            raise AuditIntegrityError("existing AL HARAS audit is unreadable") from exc
        return records

    def _read_tail_unlocked(self) -> dict[str, Any] | None:
        """Return the durable tail record, verifying its internal hash.

        Only the last line is parsed, so append cost stays O(1) in ledger
        length. A record whose ``record_hash`` does not match its own body is
        corruption; a trailing partial line (torn write) is detected as a
        JSON error and also fails closed.
        """
        if self.path is None or not self.path.exists():
            return None
        size = self.path.stat().st_size
        if size == 0:
            return None
        try:
            with self.path.open("rb") as source:
                source.seek(-min(size, _TAIL_READ_BYTES), os.SEEK_END)
                tail = source.read()
            line = tail.rsplit(b"\n", 1)[-2] if tail.endswith(b"\n") else tail.split(b"\n")[-1]
            if not line.strip():
                return None
            record = json.loads(line.decode("utf-8"))
        except (OSError, IndexError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AuditIntegrityError("durable audit tail is unreadable") from exc
        if not isinstance(record, dict):
            raise AuditIntegrityError("durable audit tail is not an object")
        body = {
            "event": record.get("event"),
            "previous_hash": record.get("previous_hash"),
        }
        if record.get("record_hash") != digest(body):
            raise AuditIntegrityError("durable audit tail record is corrupt")
        return record

    def append(self, event: Mapping[str, Any]) -> dict[str, Any]:
        if self.path is None:
            with self._lock:
                return self._append_unlocked(event, self._records)
        with self._file_lock():
            tail = self._read_tail_unlocked()
            previous = tail["record_hash"] if tail is not None else "GENESIS"
            record = self._append_record_unlocked(event, previous)
            self._records = [tail, record] if tail is not None else [record]
            return copy.deepcopy(record)

    def _append_unlocked(
        self,
        event: Mapping[str, Any],
        records: list[dict[str, Any]],
    ) -> dict[str, Any]:
        previous_hash = records[-1]["record_hash"] if records else "GENESIS"
        record = self._append_record_unlocked(event, previous_hash)
        records.append(record)
        return record

    def _append_record_unlocked(
        self,
        event: Mapping[str, Any],
        previous_hash: str,
    ) -> dict[str, Any]:
        body = {"event": dict(event), "previous_hash": previous_hash}
        record = {**body, "record_hash": digest(body)}
        if self.path is not None:
            raw = canonical_json(record) + b"\n"
            fd = os.open(
                self.path,
                os.O_APPEND | os.O_CREAT | os.O_WRONLY,
                0o600,
            )
            try:
                remaining = memoryview(raw)
                while remaining:
                    written = os.write(fd, remaining)
                    if written <= 0:
                        raise OSError("audit append made no progress")
                    remaining = remaining[written:]
                os.fsync(fd)
            finally:
                os.close(fd)
        return copy.deepcopy(record)

    @staticmethod
    def verify(records: Iterable[Mapping[str, Any]]) -> bool:
        previous_hash = "GENESIS"
        for source in records:
            record = dict(source)
            body = {
                "event": record.get("event"),
                "previous_hash": record.get("previous_hash"),
            }
            if body["previous_hash"] != previous_hash:
                return False
            if record.get("record_hash") != digest(body):
                return False
            previous_hash = str(record["record_hash"])
        return True
