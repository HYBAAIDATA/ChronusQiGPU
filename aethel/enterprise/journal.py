"""JSONL write-ahead journal with seal and incomplete-tail recover."""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Iterator, Optional


class FileLock:
    """Cross-platform advisory file lock (msvcrt on win / fcntl on unix)."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh: Any = None
        self._thread = threading.RLock()
        self._depth = 0
        self._owner: int | None = None
        # Ensure lock file exists with one byte so msvcrt can lock a range.
        self._ensure_lockfile()

    def _ensure_lockfile(self) -> None:
        try:
            if not self.path.exists() or self.path.stat().st_size == 0:
                # Exclusive create when missing; ignore races with peers.
                flags = os.O_CREAT | os.O_RDWR
                if sys.platform == "win32":
                    flags |= getattr(os, "O_BINARY", 0)
                fd = os.open(str(self.path), flags, 0o666)
                try:
                    if os.fstat(fd).st_size == 0:
                        try:
                            os.write(fd, b"X")
                        except OSError:
                            pass
                finally:
                    os.close(fd)
        except OSError:
            # Peer may be creating/locking; acquire() will retry.
            pass

    def acquire(self) -> None:
        self._thread.acquire()
        if self._depth:
            self._depth += 1
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            deadline = time.monotonic() + 30.0
            while True:
                try:
                    self._ensure_lockfile()
                    self._fh = open(self.path, "r+b")
                    if sys.platform == "win32":
                        import msvcrt
                        self._fh.seek(0)
                        msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self._depth = 1
                    self._owner = threading.get_ident()
                    return
                except OSError as exc:
                    if self._fh is not None:
                        self._fh.close()
                        self._fh = None
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"FileLock timeout: {self.path}") from exc
                    time.sleep(0.02)
        except BaseException:
            if self._fh is not None:
                self._fh.close()
                self._fh = None
            self._thread.release()
            raise

    def release(self) -> None:
        # Only the owning thread can decrement the reentrant acquisition depth.
        if self._owner != threading.get_ident() or self._depth == 0:
            raise RuntimeError("cannot release an unacquired FileLock")
        try:
            self._depth -= 1
            if self._depth:
                return
            self._owner = None
            if self._fh is not None:
                try:
                    if sys.platform == "win32":
                        import msvcrt
                        self._fh.seek(0)
                        msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
                finally:
                    self._fh.close()
                    self._fh = None
        finally:
            self._thread.release()

    def __enter__(self) -> "FileLock":
        self.acquire()
        return self

    def __exit__(self, *args: object) -> None:
        self.release()


class JournalCorruptionError(ValueError):
    """Ambiguous/non-tail corruption: refuse recovery without rewriting evidence."""


class JournalLimitError(ValueError):
    """Journal exceeds a declared parsing or row-size budget."""


def _fsync_directory(path: Path) -> None:
    # Windows does not expose portable directory fsync through os.open.
    # This implementation does not certify Windows power-loss durability.
    if os.name != "nt":
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise JournalCorruptionError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def _reject_constant(value: str) -> None:
    raise JournalCorruptionError(f"nonfinite JSON constant: {value}")


class WriteAheadJournal:
    """Bounded JSONL WAL with single-lock, evidence-preserving tail repair.

    An intent is visible to recovery only after a matching seal. Recovery repairs
    dangling intents and syntactically incomplete final rows, never ambiguous
    schema/sequence corruption or malformed interior rows. This is a WAL-local
    guarantee, not a complete custody transaction/primary-replica commit protocol.
    """

    def __init__(
        self, path: Path | str, *, max_journal_bytes: int = 256 * 1024 * 1024,
        max_row_bytes: int = 1024 * 1024, max_rows: int = 100_000,
    ) -> None:
        for name, value in (("max_journal_bytes", max_journal_bytes),
                            ("max_row_bytes", max_row_bytes), ("max_rows", max_rows)):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        self.path = Path(path)
        self.max_journal_bytes = max_journal_bytes
        self.max_row_bytes = max_row_bytes
        self.max_rows = max_rows
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = FileLock(str(self.path) + ".lock")
        # Exclusive creation cannot truncate a concurrently created WAL.
        with self._lock:
            self._check_path()
            try:
                fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                pass
            else:
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
                _fsync_directory(self.path.parent)

    def _check_path(self) -> None:
        if self.path.is_symlink():
            raise JournalCorruptionError("journal must not be a symlink")

    @staticmethod
    def _validate(row: Any, expected_status: str | None = None) -> dict[str, Any]:
        if not isinstance(row, dict):
            raise JournalCorruptionError("journal row must be an object")
        op_id = row.get("op_id")
        if not isinstance(op_id, str) or not op_id.strip() or len(op_id) > 256:
            raise JournalCorruptionError("op_id must be a nonempty bounded string")
        if not isinstance(row.get("status"), str) or row["status"] not in {"intent", "sealed"}:
            raise JournalCorruptionError("unknown journal status")
        if expected_status is not None and row["status"] != expected_status:
            raise JournalCorruptionError("journal status does not match operation")
        if "ts" in row and (isinstance(row["ts"], bool)
                            or not isinstance(row["ts"], (int, float))
                            or not math.isfinite(row["ts"])):
            raise JournalCorruptionError("invalid journal timestamp")
        return row

    def _append(self, row: dict[str, Any]) -> None:
        self._validate(row)
        line = (json.dumps(row, sort_keys=True, separators=(",", ":"),
                           allow_nan=False) + "\n").encode("utf-8")
        if len(line) > self.max_row_bytes:
            raise JournalLimitError("journal row exceeds byte budget")
        with self._lock:
            self._check_path()
            with open(self.path, "rb") as existing:
                if os.fstat(existing.fileno()).st_size:
                    existing.seek(-1, os.SEEK_END)
                    if existing.read(1) != b"\n":
                        raise JournalCorruptionError("recover incomplete journal tail before append")
            with open(self.path, "ab") as fh:
                if fh.tell() + len(line) > self.max_journal_bytes:
                    raise JournalLimitError("journal exceeds byte budget")
                fh.write(line)
                fh.flush()
                os.fsync(fh.fileno())

    def append_intent(self, record: dict[str, Any]) -> None:
        row = dict(record)
        row.setdefault("status", "intent")
        row.setdefault("ts", time.time())
        self._validate(row, "intent")
        self._append(row)

    def seal(self, op_id: str, extra: Optional[dict[str, Any]] = None) -> None:
        if extra and {"op_id", "status", "ts"}.intersection(extra):
            raise JournalCorruptionError("seal extras cannot override reserved fields")
        row: dict[str, Any] = dict(extra or {})
        row.update({"op_id": op_id, "status": "sealed", "ts": time.time()})
        self._append(row)

    def _read_locked(self) -> bytes:
        self._check_path()
        with open(self.path, "rb") as fh:
            raw = fh.read(self.max_journal_bytes + 1)
        if len(raw) > self.max_journal_bytes:
            raise JournalLimitError("journal exceeds byte budget")
        return raw

    def _parse(self, raw: bytes) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bytes]:
        lines = raw.splitlines(keepends=True)
        if len(lines) > self.max_rows:
            raise JournalLimitError("journal exceeds row-count budget")
        pending: dict[str, dict[str, Any]] = {}
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        sealed: list[dict[str, Any]] = []
        kept: list[tuple[dict[str, Any], bytes]] = []
        for index, line in enumerate(lines):
            if len(line) > self.max_row_bytes:
                raise JournalLimitError("journal row exceeds byte budget")
            if not line.strip():
                continue
            try:
                row = json.loads(line, object_pairs_hook=_unique_object,
                                 parse_constant=_reject_constant)
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                # Only an unterminated final row can be an incomplete write.
                if index != len(lines) - 1 or line.endswith(b"\n"):
                    raise JournalCorruptionError("malformed non-tail journal row") from exc
                break
            self._validate(row)
            op_id = row["op_id"]
            if row["status"] == "intent":
                if op_id in seen:
                    raise JournalCorruptionError("duplicate transaction id")
                seen.add(op_id)
                pending[op_id] = row
            else:
                if op_id not in pending:
                    raise JournalCorruptionError("seal without a matching intent")
                base = pending.pop(op_id)
                for key in ("op", "record_id", "generation", "content_digest"):
                    if key in base and key in row and base[key] != row[key]:
                        raise JournalCorruptionError(f"seal changes intent {key}")
                sealed.append({**base, **row, "status": "sealed"})
            rows.append(row)
            kept.append((row, line.rstrip(b"\r\n") + b"\n"))
        repaired = b"".join(line for row, line in kept
                            if not (row["status"] == "intent" and row["op_id"] in pending))
        return rows, sealed, repaired

    def _preserve_and_replace(self, raw: bytes, repaired: bytes) -> None:
        digest = hashlib.sha256(raw).hexdigest()
        evidence = self.path.with_name(self.path.name + f".repair-{digest}.bin")
        try:
            fd = os.open(evidence, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            if evidence.is_symlink() or evidence.read_bytes() != raw:
                raise JournalCorruptionError("repair evidence collision")
            # A prior attempt may have failed before its evidence fsync.
            with open(evidence, "rb") as fh:
                os.fsync(fh.fileno())
        else:
            with os.fdopen(fd, "wb") as fh:
                fh.write(raw)
                fh.flush()
                os.fsync(fh.fileno())
        _fsync_directory(self.path.parent)
        fd, name = tempfile.mkstemp(prefix=self.path.name + ".repair-", dir=self.path.parent)
        tmp = Path(name)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(repaired)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.path)
            _fsync_directory(self.path.parent)
        finally:
            tmp.unlink(missing_ok=True)

    def recover(self) -> list[dict[str, Any]]:
        """Return only matched sealed operations; repair under one held lock."""
        with self._lock:
            raw = self._read_locked()
            _rows, sealed, repaired = self._parse(raw)
            if repaired != raw:
                self._preserve_and_replace(raw, repaired)
            return sealed

    def iter_rows(self) -> Iterator[dict[str, Any]]:
        # Take a consistent bounded snapshot; never rewrite during a read.
        with self._lock:
            rows, _sealed, _repaired = self._parse(self._read_locked())
        yield from rows


__all__ = ["FileLock", "WriteAheadJournal", "JournalCorruptionError", "JournalLimitError"]
