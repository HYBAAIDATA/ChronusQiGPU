# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""AL HARAS anchor ledger, schema v1 (resolves spec placeholder P10).

Schema: one JSON object per line (JSON Lines, UTF-8)::

    {"schema": "chronus.fleet.al-haras-anchor/v1", "seq": 0,
     "prev_hash": "<64 hex>", "recorded_at": "<ISO 8601 UTC>",
     "kind": "fabric_snapshot" | "receipt" | "incident" | "tier" | "scale" | "note",
     "digest": "<64 hex: SHA-256 of the anchored object>",
     "meta": {<small JSON object>}, "entry_hash": "<64 hex>"}

``entry_hash`` is SHA-256 over the canonical JSON of the entry without
``entry_hash``. ``prev_hash`` is the previous entry's ``entry_hash``, or 64
zeros for seq 0. ``seq`` counts from 0 without gaps.

Append protocol: one writer (the coordinator) verifies the whole chain when it
opens the file, then for each append holds a process lock and an exclusive
advisory file lock, writes one complete line, flushes and fsyncs before
returning the new entry. Verification recomputes every entry hash and link
from the first line.

The ledger is tamper-evident (any edit, deletion or reordering breaks the
chain) and local. It is not replicated, distributed or immutable storage;
anchoring a digest here proves only that this file recorded it in sequence.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping

if os.name == "nt":
    import msvcrt

from chronus.fleet.canonical import canonical_json, is_hex_digest, iso_utc, sha256_hex
from chronus.fleet.errors import LedgerError

LEDGER_SCHEMA = "chronus.fleet.al-haras-anchor/v1"
GENESIS_PREV = "0" * 64
KINDS = frozenset({"fabric_snapshot", "receipt", "incident", "tier", "scale", "note"})
_FIELDS = frozenset({"schema", "seq", "prev_hash", "recorded_at", "kind", "digest", "meta", "entry_hash"})

try:
    import fcntl as _fcntl
except ImportError:
    _fcntl = None


def _file_stamp(stat: os.stat_result) -> tuple[int, int, int, int, int]:
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


def _path_stamp(path: Path) -> tuple[int, int, int, int, int] | None:
    try:
        return _file_stamp(path.stat())
    except FileNotFoundError:
        return None


def entry_hash(entry: Mapping[str, Any]) -> str:
    body = {k: v for k, v in entry.items() if k != "entry_hash"}
    return sha256_hex(canonical_json(body))


@dataclass(frozen=True)
class LedgerVerification:
    valid: bool
    entries: int
    head_hash: str
    first_bad_seq: int | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "entries": self.entries,
            "head_hash": self.head_hash,
            "first_bad_seq": self.first_bad_seq,
            "reason": self.reason,
        }


def _iter_lines(path: Path) -> Iterator[tuple[int, str]]:
    with path.open("r", encoding="utf-8") as handle:
        for number, line in enumerate(handle):
            yield number, line


def verify_ledger(path: str | Path) -> LedgerVerification:
    """Recompute every hash and link; report the first entry that fails."""
    path = Path(path)
    if not path.exists():
        return LedgerVerification(True, 0, GENESIS_PREV)
    prev = GENESIS_PREV
    count = 0
    for number, line in _iter_lines(path):
        if not line.endswith("\n"):
            return LedgerVerification(False, count, prev, number, "truncated final line")
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            return LedgerVerification(False, count, prev, number, "line is not JSON")
        problem = _check_entry(entry, number, prev)
        if problem:
            return LedgerVerification(False, count, prev, number, problem)
        prev = entry["entry_hash"]
        count += 1
    return LedgerVerification(True, count, prev)


def _check_entry(entry: Any, expected_seq: int, prev: str) -> str | None:
    if not isinstance(entry, dict) or set(entry) != _FIELDS:
        return "entry fields do not match schema v1"
    if entry["schema"] != LEDGER_SCHEMA:
        return "unknown schema"
    if entry["seq"] != expected_seq:
        return f"sequence gap: expected {expected_seq}"
    if entry["prev_hash"] != prev:
        return "prev_hash does not link to the previous entry"
    if entry["kind"] not in KINDS:
        return "unknown kind"
    if not is_hex_digest(entry["digest"]):
        return "digest is not a SHA-256 hex digest"
    if not isinstance(entry["meta"], dict):
        return "meta must be an object"
    if entry_hash(entry) != entry["entry_hash"]:
        return "entry_hash does not match the entry"
    return None


class AnchorLedger:
    """Single-writer, append-only, hash-chained anchor ledger."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        before = _path_stamp(self.path)
        check = verify_ledger(self.path)
        self._stamp = _path_stamp(self.path)
        if before != self._stamp:
            raise LedgerError("ledger changed while opening; reopen and verify")
        if not check.valid:
            raise LedgerError(f"ledger {self.path} fails verification at line {check.first_bad_seq}: {check.reason}")
        self._seq = check.entries
        self._head = check.head_hash
        self._failed = False

    @property
    def head(self) -> tuple[int, str]:
        """(number of entries, hash of the last entry)."""
        return self._seq, self._head

    def append(self, kind: str, digest: str, meta: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if kind not in KINDS:
            raise LedgerError(f"unknown ledger kind {kind!r}")
        if not is_hex_digest(digest):
            raise LedgerError("anchored digest must be a SHA-256 hex digest")
        meta = dict(meta or {})
        if len(canonical_json(meta)) > 4096:
            raise LedgerError("ledger meta must fit in 4 KiB; anchor a digest instead")
        with self._lock:
            if self._failed:
                raise LedgerError("ledger append previously failed; reopen and verify before writing")
            with self.path.open("a+", encoding="utf-8") as handle:
                if _fcntl is not None:
                    _fcntl.flock(handle.fileno(), _fcntl.LOCK_EX)
                elif os.name == "nt":
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                else:
                    raise LedgerError("cross-process ledger lock unavailable")
                try:
                    current = _file_stamp(os.fstat(handle.fileno()))
                    if current != _path_stamp(self.path) or (self._stamp is None and current[2] != 0) or (self._stamp is not None and current != self._stamp):
                        raise LedgerError("ledger changed since opening; stale writer refused")
                    handle.seek(0, os.SEEK_END)
                    entry = {
                        "schema": LEDGER_SCHEMA,
                        "seq": self._seq,
                        "prev_hash": self._head,
                        "recorded_at": iso_utc(),
                        "kind": kind,
                        "digest": digest,
                        "meta": meta,
                    }
                    entry["entry_hash"] = entry_hash(entry)
                    handle.write(json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                    self._stamp = _file_stamp(os.fstat(handle.fileno()))
                except BaseException:
                    self._failed = True
                    raise
                finally:
                    if _fcntl is not None:
                        _fcntl.flock(handle.fileno(), _fcntl.LOCK_UN)
                    elif os.name == "nt":
                        handle.seek(0)
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            self._seq += 1
            self._head = entry["entry_hash"]
            return entry

    def find(self, digest: str, seq: int | None = None) -> dict[str, Any] | None:
        """The first entry anchoring digest, or None."""
        if not self.path.exists():
            return None
        for _, line in _iter_lines(self.path):
            entry = json.loads(line)
            if entry.get("digest") == digest and (seq is None or entry.get("seq") == seq):
                return entry
        return None

    def verify(self) -> LedgerVerification:
        return verify_ledger(self.path)
