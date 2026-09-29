"""Algebraic query — query by mathematical property, not only by key.

The declared shift: a query stops being "find rows matching a predicate"
and becomes "find states whose PROOF-STATE has this property". Every query
here is answered from exact integer predicates over the stored 11D state.

COMPLEXITY IS REPORTED HONESTLY
-------------------------------
A direct slot lookup by a known object id is O(1). A resonance scan over
stored states is a BOUNDED SCAN, O(n) in the number of objects -- it is not
O(1) and is never described as such.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .zeckendorf_codec import is_valid_mask

__all__ = ["QueryResult", "query", "resonance_scan", "QueryUnsupported"]


class QueryUnsupported(ValueError):
    """A predicate the planner cannot evaluate. Fails at plan time."""


@dataclass(frozen=True)
class QueryResult:
    """Query outcome with the complexity actually used."""

    predicate: str
    matches: List[str]
    scanned: int
    complexity: str
    supported: bool
    reason: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "predicate": self.predicate,
            "matches": self.matches,
            "matched": len(self.matches),
            "scanned": self.scanned,
            "complexity": self.complexity,
            "supported": self.supported,
            "reason": self.reason,
        }


def resonance_scan(db: Any, d5_mask: int) -> QueryResult:
    """Find objects whose D5 Zeckendorf mask contains every bit of ``d5_mask``.

    A bounded scan over the stored objects. The complexity is reported as
    O(n) because that is what it is.
    """
    if not 0 <= d5_mask <= 0xFFFFFFFF:
        raise ValueError("d5_mask must be a uint32")
    hits = []
    scanned = 0
    for oid in db:
        scanned += 1
        obj = db.get(oid)
        if obj.state.zeckendorf_mask & d5_mask == d5_mask:
            hits.append(oid)
    return QueryResult(
        predicate=f"d5_mask & {d5_mask:#x} == {d5_mask:#x}",
        matches=hits,
        scanned=scanned,
        complexity="O(n) bounded scan",
        supported=True,
    )


def query(db: Any, predicate: str, **params: Any) -> QueryResult:
    """Dispatch a named algebraic predicate.

    An unknown predicate is refused rather than approximated, so an
    unsupported semantic can never silently return the wrong rows.
    """
    handlers = {
        "d5_resonance": resonance_scan,
        "cassini_valid": _cassini_valid,
        "zeckendorf_canonical": _zeckendorf_canonical,
    }
    handler = handlers.get(predicate)
    if handler is None:
        return QueryResult(
            predicate=predicate,
            matches=[],
            scanned=0,
            complexity="n/a",
            supported=False,
            reason=f"unsupported predicate; known: {sorted(handlers)}",
        )
    return handler(db, **params)


def _cassini_valid(db: Any) -> QueryResult:
    from .cassini import verify_state

    hits, scanned, failed = [], 0, []
    for oid in db:
        scanned += 1
        obj = db.get(oid)
        if all(p.passed for p in verify_state(obj.state.index)):
            hits.append(oid)
        else:
            failed.append(oid)
    return QueryResult(
        predicate="cassini_valid",
        matches=hits,
        scanned=scanned,
        complexity="O(n) bounded scan",
        supported=True,
        reason=None if not failed else f"failing: {failed}",
    )


def _zeckendorf_canonical(db: Any) -> QueryResult:
    hits, scanned = [], 0
    for oid in db:
        scanned += 1
        obj = db.get(oid)
        if is_valid_mask(obj.state.zeckendorf_mask):
            hits.append(oid)
    return QueryResult(
        predicate="zeckendorf_canonical",
        matches=hits,
        scanned=scanned,
        complexity="O(n) bounded scan",
        supported=True,
    )
