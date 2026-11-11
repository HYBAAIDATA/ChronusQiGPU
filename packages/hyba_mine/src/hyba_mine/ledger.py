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
from hyba_mine.logsafe import SECRETS

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

    def append(self, kind: str, data: Optional[dict] = None) -> dict:
        if not isinstance(kind, str) or not kind:
            raise ValueError("ledger record kind must be a non-empty string")
        data = {} if data is None else data
        if not isinstance(data, dict):
            raise ValueError("ledger record data must be a JSON object")
        encoded = json.dumps(data, sort_keys=True, ensure_ascii=False)
        if SECRETS.contains(encoded):
            data = json.loads(SECRETS.redact(encoded))
            data["_redacted"] = True
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_fd = os.open(self.lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            seq, prev, ends_clean = self._tail()
            record = {"seq": seq + 1, "ts": utc_now(), "kind": kind, "data": data, "prev": prev}
            record["hash"] = record_hash(record)
            line = _canonical(record) + b"\n"
            if not ends_clean:
                line = b"\n" + line
            fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            try:
                os.write(fd, line)
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
        with open(self.path, "rb") as handle:
            for number, raw in enumerate(handle, start=1):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    record = json.loads(raw)
                except json.JSONDecodeError:
                    torn += 1
                    continue
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
        return VerifyResult(True, count, torn, prev, None)
