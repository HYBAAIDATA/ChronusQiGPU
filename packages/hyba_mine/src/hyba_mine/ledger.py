# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Append-only local ledger of sessions, jobs, work, shares and pool replies.

Each line is one JSON record ``{seq, ts, kind, data, prev, hash}`` where
``hash = SHA-256(canonical JSON of seq, ts, kind, data, prev)`` and ``prev`` is
the previous record's hash, so any edit, deletion or reordering breaks the
chain and ``verify()`` reports it. Writers append under an exclusive ``flock``
and never rewrite the file.

The console and ``hyba-mine status`` compute every value they show from these
records; nothing is kept in memory only.

No record may carry a pool login: callers never put one in, and as a backstop
any registered login text is replaced by ``[redacted]`` before the record is
hashed, with ``_redacted: true`` added to the record's data.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

from hyba_mine.control import utc_now
from hyba_mine.logsafe import redact_payload
from hyba_mine.paths import write_private_file

GENESIS_HASH = "0" * 64
_TAIL_CHUNK = 64 * 1024
_NO_FSYNC_KINDS = frozenset({"work"})


def _canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def record_hash(record: dict) -> str:
    body = {key: record[key] for key in ("seq", "ts", "kind", "data", "prev")}
    return hashlib.sha256(_canonical(body)).hexdigest()


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    records: int
    torn_lines: int
    last_hash: str
    error: Optional[str]

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "records": self.records,
            "torn_lines": self.torn_lines,
            "last_hash": self.last_hash,
            "error": self.error,
        }


def _final_fragment(handle) -> bytes:
    """Read back from EOF in fixed chunks, retaining only the final fragment."""
    handle.seek(0, os.SEEK_END)
    position, parts = handle.tell(), []
    while position:
        size = min(_TAIL_CHUNK, position)
        position -= size
        handle.seek(position)
        chunk = handle.read(size)
        boundary = chunk.rfind(b"\n")
        if boundary >= 0:
            parts.append(chunk[boundary+1:])
            break
        parts.append(chunk)
    return b"".join(reversed(parts))


class Ledger:
    def __init__(self, path: Path, lock_path: Optional[Path] = None) -> None:
        self.path = Path(path)
        self.lock_path = Path(lock_path) if lock_path else self.path.with_suffix(".lock")
        self._cache: Optional[tuple[int, int, str]] = None

    def _tail(self) -> tuple[int, str, bool]:
        """Return (last seq, last hash, file ends with a newline)."""
        if not self.path.exists():
            return -1, GENESIS_HASH, True
        size = self.path.stat().st_size
        if size == 0:
            return -1, GENESIS_HASH, True
        if self._cache and self._cache[0] == size:
            return self._cache[1], self._cache[2], True
        chunk = _TAIL_CHUNK
        with open(self.path, "rb") as handle:
            while True:
                start = max(0, size - chunk)
                handle.seek(start)
                data = handle.read(size - start)
                ends_clean = data.endswith(b"\n")
                lines = data.split(b"\n")
                if start > 0:
                    lines = lines[1:]
                for raw in reversed(lines):
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        record = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(record, dict) and "hash" in record and "seq" in record:
                        return int(record["seq"]), str(record["hash"]), ends_clean
                if start == 0:
                    return -1, GENESIS_HASH, ends_clean
                chunk *= 4

    @property
    def _recovery_path(self) -> Path:
        return self.path.with_suffix(self.path.suffix + ".recovery")

    def _prefix_digest(self, length: int) -> str:
        digest = hashlib.sha256()
        with open(self.path, "rb") as handle:
            remaining = length
            while remaining:
                chunk = handle.read(min(_TAIL_CHUNK, remaining))
                if not chunk:
                    raise ValueError("ledger recovery prefix is truncated")
                digest.update(chunk)
                remaining -= len(chunk)
        return digest.hexdigest()

    def _complete_recovery(self) -> None:
        """Finish a persisted recovery append; never replace existing bytes."""
        if not self._recovery_path.exists():
            return
        intent = json.loads(self._recovery_path.read_bytes())
        offset = intent["offset"]
        payload = bytes.fromhex(intent["payload_hex"])
        if type(offset) is not int or offset < 0 or self._prefix_digest(offset) != intent["prefix_sha256"]:
            raise ValueError("ledger recovery prefix differs from its intent")
        with open(self.path, "rb") as handle:
            handle.seek(offset)
            written = handle.read(len(payload) + 1)
        if not payload.startswith(written):
            raise ValueError("ledger recovery suffix differs from its intent")
        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND)
        try:
            self._cache = None
            remaining = memoryview(payload)[len(written):]
            while remaining:
                count = os.write(fd, remaining)
                if count <= 0:
                    raise OSError("ledger recovery made no progress")
                remaining = remaining[count:]
            os.fsync(fd)
        finally:
            os.close(fd)
        self._recovery_path.unlink()

    def append(self, kind: str, data: Optional[dict] = None) -> dict:
        if not isinstance(kind, str) or not kind:
            raise ValueError("ledger record kind must be a non-empty string")
        data = {} if data is None else data
        if not isinstance(data, dict):
            raise ValueError("ledger record data must be a JSON object")
        clean = redact_payload(data)
        if clean != data:
            data = {**clean, "_redacted": True}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_fd = os.open(self.lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            self._complete_recovery()
            seq, prev, ends_clean = self._tail()
            record = {"seq": seq + 1, "ts": utc_now(), "kind": kind, "data": data, "prev": prev}
            record["hash"] = record_hash(record)
            line = _canonical(record) + b"\n"
            if not ends_clean:
                with open(self.path, "rb") as tail_handle:
                    fragment = _final_fragment(tail_handle)
                try:
                    json.loads(fragment)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    recovery = {"seq": seq + 1, "ts": utc_now(), "kind": "tail_recovery",
                                "data": {"fragment_sha256": hashlib.sha256(fragment).hexdigest(),
                                         "fragment_bytes": len(fragment)}, "prev": prev}
                    recovery["hash"] = record_hash(recovery)
                    record["seq"] += 1
                    record["prev"] = recovery["hash"]
                    record["hash"] = record_hash(record)
                    line = _canonical(recovery) + b"\n" + _canonical(record) + b"\n"
                line = b"\n" + line
                # Persist intent before completing a torn line. A second crash
                # resumes exactly this append rather than creating nested fragments.
                offset = self.path.stat().st_size
                intent = {"offset": offset, "prefix_sha256": self._prefix_digest(offset),
                          "payload_hex": line.hex()}
                write_private_file(self._recovery_path, _canonical(intent))
                directory_fd = os.open(self.path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
                self._complete_recovery()
                self._cache = (self.path.stat().st_size, record["seq"], record["hash"])
                return record
            fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            try:
                self._cache = None
                remaining = memoryview(line)
                while remaining:
                    count = os.write(fd, remaining)
                    if count <= 0:
                        raise OSError("ledger append made no progress")
                    remaining = remaining[count:]
                if kind not in _NO_FSYNC_KINDS:
                    os.fsync(fd)
            finally:
                os.close(fd)
            self._cache = (self.path.stat().st_size, record["seq"], record["hash"])
            return record
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)

    def records(self) -> Iterator[dict]:
        if not self.path.exists():
            return
        with open(self.path, "rb") as handle:
            for raw in handle:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    record = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if isinstance(record, dict) and "kind" in record:
                    yield record

    def verify(self) -> VerifyResult:
        count = 0
        torn = 0
        prev = GENESIS_HASH
        expected_seq = 0
        if not self.path.exists():
            return VerifyResult(True, 0, 0, prev, None)
        pending_fragment = None
        with open(self.path, "rb") as handle:
            for number, raw in enumerate(handle, start=1):
                terminated = raw.endswith(b"\n")
                original = raw.rstrip(b"\n")
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    record = json.loads(raw)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    if pending_fragment is not None:
                        return VerifyResult(False, count, torn, prev, f"line {number}: malformed complete record")
                    if not terminated:
                        return VerifyResult(True, count, torn + 1, prev, None)
                    pending_fragment = original
                    continue
                if pending_fragment is not None:
                    expected_recovery = {"fragment_sha256": hashlib.sha256(pending_fragment).hexdigest(),
                                         "fragment_bytes": len(pending_fragment)}
                    if not isinstance(record, dict) or record.get("kind") != "tail_recovery" or record.get("data") != expected_recovery:
                        return VerifyResult(False, count, torn, prev, f"line {number}: missing valid tail recovery")
                    pending_fragment = None
                    torn += 1
                if not isinstance(record, dict) or not {"seq", "ts", "kind", "data", "prev", "hash"} <= set(record):
                    return VerifyResult(False, count, torn, prev, f"line {number}: not a ledger record")
                if record["seq"] != expected_seq:
                    return VerifyResult(False, count, torn, prev, f"line {number}: sequence {record['seq']} where {expected_seq} was expected")
                if record["prev"] != prev:
                    return VerifyResult(False, count, torn, prev, f"line {number}: chain broken (prev does not match)")
                if record_hash(record) != record["hash"]:
                    return VerifyResult(False, count, torn, prev, f"line {number}: record hash does not match its content")
                prev = record["hash"]
                expected_seq += 1
                count += 1
        if pending_fragment is not None:
            return VerifyResult(False, count, torn, prev, "malformed complete final record")
        return VerifyResult(True, count, torn, prev, None)
