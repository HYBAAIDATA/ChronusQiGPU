"""Retention policy for enterprise custody records.

Retention is a custody concern (how long records are kept), distinct from
quotas (how much may be admitted). The policy is pure evaluation — it never
deletes anything itself; custody applies the returned delete list through
the normal journaled delete path so removal is WAL'd, MAC'd and provenanced.

Determinism: eviction order is oldest-write-first by ``written_ts``, then
record_id — two evaluations over the same records return the same list.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class RetentionPolicy:
    """Declared retention contract (all bounds optional, None = unbounded).

    ``max_age_seconds``: records whose ``written_ts`` is older are evicted.
    ``max_records``: keep at most N records; oldest evicted first.
    """

    max_age_seconds: float | None = None
    max_records: int | None = None

    def __post_init__(self) -> None:
        if self.max_age_seconds is not None and self.max_age_seconds < 0:
            raise ValueError("max_age_seconds must be >= 0")
        if self.max_records is not None and self.max_records < 0:
            raise ValueError("max_records must be >= 0")

    @property
    def bounded(self) -> bool:
        return self.max_age_seconds is not None or self.max_records is not None

    def evaluate(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        now: float | None = None,
    ) -> dict[str, Any]:
        """Return the deterministic eviction decision.

        ``records`` yields dicts with ``record_id`` and ``written_ts``
        (epoch seconds; missing treated as 0 — oldest). Returns
        ``{"evict": [...], "kept": int, "reasons": {rid: why}}``.
        """
        now = time.time() if now is None else float(now)
        entries = [(str(r["record_id"]), float(r.get("written_ts") or 0.0)) for r in records]
        entries.sort(key=lambda e: (e[1], e[0]))  # oldest first, id tiebreak
        evict: dict[str, str] = {}
        if self.max_age_seconds is not None:
            cutoff = now - self.max_age_seconds
            for rid, ts in entries:
                if ts < cutoff:
                    evict[rid] = "age"
        kept_after_age = [e for e in entries if e[0] not in evict]
        if self.max_records is not None and (len(kept_after_age) > self.max_records):
            overflow = len(kept_after_age) - self.max_records
            for rid, _ts in kept_after_age[:overflow]:
                evict[rid] = "count"
        return {
            "evict": sorted(evict),
            "kept": len(entries) - len(evict),
            "reasons": {rid: evict[rid] for rid in sorted(evict)},
        }


__all__ = ["RetentionPolicy"]
