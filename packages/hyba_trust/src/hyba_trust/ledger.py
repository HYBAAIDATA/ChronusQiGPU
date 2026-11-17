"""Append-only, hash-chained promotion ledger.

Every entry commits to the previous entry's hash, so editing or dropping a past
entry is detected by ``verify``. This is tamper evidence within one process's
record, not a signature: anyone able to rewrite the whole list can rewrite the
chain.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterator

GENESIS = "0" * 64


def _digest(prev: str, body: dict[str, Any]) -> str:
    payload = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256((prev + payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class LedgerEntry:
    seq: int
    prev: str
    hash: str
    body: dict[str, Any]


class PromotionLedger:
    def __init__(self) -> None:
        self._entries: list[LedgerEntry] = []

    def append(self, kind: str, **fields: Any) -> LedgerEntry:
        prev = self._entries[-1].hash if self._entries else GENESIS
        body = {"kind": kind, **fields}
        entry = LedgerEntry(len(self._entries), prev, _digest(prev, body), body)
        self._entries.append(entry)
        return entry

    def __iter__(self) -> Iterator[LedgerEntry]:
        return iter(tuple(self._entries))

    def __len__(self) -> int:
        return len(self._entries)

    def of_kind(self, kind: str) -> list[LedgerEntry]:
        return [e for e in self._entries if e.body["kind"] == kind]

    def verify(self) -> list[str]:
        """Return a description of every break in the chain (empty if intact)."""
        problems = []
        prev = GENESIS
        for i, entry in enumerate(self._entries):
            if entry.seq != i:
                problems.append(f"entry {i}: sequence {entry.seq}")
            if entry.prev != prev:
                problems.append(f"entry {i}: does not chain to entry {i - 1}")
            if entry.hash != _digest(entry.prev, entry.body):
                problems.append(f"entry {i}: body does not match its hash")
            prev = entry.hash
        return problems
