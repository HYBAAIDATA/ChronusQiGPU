"""HYBA / AL HARAS security layer - tamper-evident audit chain.

CLAIM LANE: IMPLEMENTED. Hash chain + Merkle root over SHA-256.
This is tamper-EVIDENT (detects mutation), not tamper-PROOF (does not prevent it).

Provenance: `security_core.py` was assessed KEEP - real (Merkle recompute on
verify, property tests) in the AL HARAS package audit, 20 Jul 2026.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Final

GENESIS: Final[str] = "0" * 64
CLAIM_LANE: Final[str] = "IMPLEMENTED"


class AuditChainError(Exception):
    """Raised on malformed audit chain operations."""


def _canonical(payload: Any) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")


def _sha256(*parts: bytes) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part)
    return digest.hexdigest()


def _entry_hash(index: int, payload: Any, prev_hash: str) -> str:
    body = _canonical({"index": index, "payload": payload})
    return _sha256(prev_hash.encode("utf-8"), b"|", body)


def _merkle_parent(left: str, right: str) -> str:
    return _sha256(b"node|", left.encode("utf-8"), b"|", right.encode("utf-8"))


class AuditChain:
    """Append-only hash chain with a Merkle root and inclusion proofs."""

    def __init__(self) -> None:
        self._entries: list[dict[str, Any]] = []

    # ---- state -----------------------------------------------------------
    @property
    def entries(self) -> list[dict[str, Any]]:
        """Frozen copies - callers cannot mutate chain state through this."""
        return [dict(entry) for entry in self._entries]

    def __len__(self) -> int:
        return len(self._entries)

    @property
    def last_hash(self) -> str:
        return self._entries[-1]["entry_hash"] if self._entries else GENESIS

    # ---- write -----------------------------------------------------------
    def append(self, payload: Any) -> dict[str, Any]:
        index = len(self._entries)
        prev_hash = self.last_hash
        entry = {
            "index": index,
            "payload": payload,
            "prev_hash": prev_hash,
            "entry_hash": _entry_hash(index, payload, prev_hash),
        }
        self._entries.append(entry)
        return dict(entry)

    # ---- verify ----------------------------------------------------------
    def verify(self) -> bool:
        """Recompute the whole chain. False on any splice, flip, or desync."""
        expected_prev = GENESIS
        for position, entry in enumerate(self._entries):
            if entry.get("index") != position:
                return False
            if entry.get("prev_hash") != expected_prev:
                return False
            recomputed = _entry_hash(position, entry.get("payload"), expected_prev)
            if recomputed != entry.get("entry_hash"):
                return False
            expected_prev = entry["entry_hash"]
        return True

    # ---- merkle ----------------------------------------------------------
    def leaves(self) -> list[str]:
        return [entry["entry_hash"] for entry in self._entries]

    def merkle_root(self) -> str:
        level = self.leaves()
        if not level:
            return GENESIS
        while len(level) > 1:
            if len(level) % 2 == 1:
                level = level + [level[-1]]
            level = [
                _merkle_parent(level[i], level[i + 1]) for i in range(0, len(level), 2)
            ]
        return level[0]

    def proof(self, index: int) -> list[dict[str, str]]:
        """Inclusion proof for the entry at `index`."""
        if not 0 <= index < len(self._entries):
            raise AuditChainError(f"index {index} out of range")
        level = self.leaves()
        position = index
        path: list[dict[str, str]] = []
        while len(level) > 1:
            if len(level) % 2 == 1:
                level = level + [level[-1]]
            sibling = position ^ 1
            path.append(
                {
                    "side": "left" if sibling < position else "right",
                    "hash": level[sibling],
                }
            )
            level = [
                _merkle_parent(level[i], level[i + 1]) for i in range(0, len(level), 2)
            ]
            position //= 2
        return path

    @staticmethod
    def verify_proof(leaf: str, path: list[dict[str, str]], root: str) -> bool:
        current = leaf
        for step in path:
            if step.get("side") == "left":
                current = _merkle_parent(step["hash"], current)
            else:
                current = _merkle_parent(current, step["hash"])
        return current == root

    def describe(self) -> dict[str, Any]:
        return {
            "entries": len(self._entries),
            "merkle_root": self.merkle_root(),
            "last_hash": self.last_hash,
            "intact": self.verify(),
            "claim_lane": CLAIM_LANE,
            "tamper_evident": True,
            "tamper_proof": False,
        }
