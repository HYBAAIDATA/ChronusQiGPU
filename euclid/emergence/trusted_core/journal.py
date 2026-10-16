"""Immutable append-only ledger for trusted-core qualification audit trail."""

from __future__ import annotations
import hashlib
import json
import time
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple


@dataclass(frozen=True)
class JournalEntry:
    """Tamper-evident block in the trusted core qualification journal."""
    entry_index: int
    timestamp: float
    action: str  # QUALIFY, REJECT, SUSPEND, CONDENSATION_EVENT, etc.
    candidate_id: str
    details: Dict[str, Any]
    previous_hash: str
    entry_hash: str

    def compute_expected_hash(self) -> str:
        payload = {
            "entry_index": self.entry_index,
            "timestamp": self.timestamp,
            "action": self.action,
            "candidate_id": self.candidate_id,
            "details": self.details,
            "previous_hash": self.previous_hash,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def verify_integrity(self) -> bool:
        import hmac
        return hmac.compare_digest(self.compute_expected_hash(), self.entry_hash)


class ImmutableEmergenceJournal:
    """Trusted-core audit ledger."""

    GENESIS_HASH = "0" * 64

    def __init__(self) -> None:
        self._entries: List[JournalEntry] = []

    def append(self, action: str, candidate_id: str, details: Dict[str, Any]) -> JournalEntry:
        prev_hash = self._entries[-1].entry_hash if self._entries else self.GENESIS_HASH
        idx = len(self._entries)
        now = time.time()

        payload = {
            "entry_index": idx,
            "timestamp": now,
            "action": action,
            "candidate_id": candidate_id,
            "details": details,
            "previous_hash": prev_hash,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        entry_hash = hashlib.sha256(encoded).hexdigest()

        entry = JournalEntry(
            entry_index=idx,
            timestamp=now,
            action=action,
            candidate_id=candidate_id,
            details=details,
            previous_hash=prev_hash,
            entry_hash=entry_hash,
        )
        self._entries.append(entry)
        return entry

    def log(self, stats: Dict[str, Any], signed: bool = True) -> JournalEntry:
        """Alias for verbatim stats logging."""
        cand_id = stats.get("event_id", stats.get("run_index", "stats_event"))
        return self.append("STATS_LOG", str(cand_id), stats)

    def verify_chain(self) -> Tuple[bool, Optional[str]]:
        if not self._entries:
            return True, None

        for i, entry in enumerate(self._entries):
            if i == 0 and entry.previous_hash != self.GENESIS_HASH:
                return False, "Genesis block previous_hash mismatch"
            if i > 0 and entry.previous_hash != self._entries[i - 1].entry_hash:
                return False, f"Broken chain at index {i}"
            if not entry.verify_integrity():
                return False, f"Tampered entry detected at index {i}"

        return True, None

    def get_entries(self) -> List[JournalEntry]:
        return list(self._entries)
