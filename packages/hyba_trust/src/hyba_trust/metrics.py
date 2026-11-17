"""Operating metrics, computed from the fabric's own records (nothing estimated)."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Optional

from .fabric import TrustFabric
from .model import STATES, State


def promotion_backlog_age_p95(fabric: TrustFabric) -> Optional[int]:
    """95th percentile age in seconds of open reviews (nearest-rank); None if none open."""
    now = fabric.clock()
    ages = sorted(now - t.opened_at for t in fabric.reviews.values() if t.closed_at is None)
    if not ages:
        return None
    return ages[max(0, math.ceil(0.95 * len(ages)) - 1)]


def cascade_latency(fabric: TrustFabric) -> list[int]:
    """Seconds from start to finish of each cascade, in order."""
    return [m.finished_at - m.started_at for m in fabric.cascades]


def quarantine_leak_rate(fabric: TrustFabric) -> Optional[float]:
    """Share of citations-as-fact that cited a non-authoritative atom."""
    as_fact = [c for c in fabric.citations if c.as_fact]
    if not as_fact:
        return None
    return sum(1 for c in as_fact if not STATES[c.state].authoritative) / len(as_fact)


def demotion_recurrence(fabric: TrustFabric) -> Optional[float]:
    """Share of ever-demoted atoms that were demoted more than once."""
    counts = Counter()
    for atom in fabric.atoms.values():
        n = sum(1 for e in atom.state_history if e.to_state is State.DEMOTED)
        if n:
            counts[atom.id] = n
    if not counts:
        return None
    return sum(1 for n in counts.values() if n > 1) / len(counts)


def reviewer_overturn_rate(fabric: TrustFabric) -> dict[str, float]:
    """Per approver: share of their approvals later disputed, demoted or retracted."""
    approved: dict[str, int] = defaultdict(int)
    overturned: dict[str, int] = defaultdict(int)
    for atom in fabric.atoms.values():
        history = atom.state_history
        for i, entry in enumerate(history):
            if entry.to_state is not State.PROBATION or not entry.approvers:
                continue
            later = history[i + 1:]
            # Stop at the next approval: what happens after it is someone else's call.
            nxt = next((j for j, e in enumerate(later) if e.approvers and e.to_state is State.PROBATION), len(later))
            bad = any(e.to_state in (State.DISPUTED, State.DEMOTED, State.RETRACTED) for e in later[:nxt])
            for who in entry.approvers:
                approved[who] += 1
                overturned[who] += bad
    return {who: overturned[who] / n for who, n in approved.items()}
