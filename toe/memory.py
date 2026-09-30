"""Memory as intelligence — elevation §§19-22.

§19 taxonomy: one store, five namespaces (``observation``, ``episodic``,
``causal``, ``strategy``, ``world_model``, ``procedural``) — logical
views over a single record list backed by the receipt ledger, NOT five
databases. The intelligence question is answered explicitly: a record
carries ``causal_tags`` declaring WHY it may matter later; recall is
content-addressed on those tags, not recency.

§20 long-horizon: ``recall`` retrieves by causal relevance over any gap;
``recent_window_baseline`` is the honest strawman-free comparator (same
records, recency window only) that forgets the decisive event.

§21 consolidation: ``consolidate`` finds episodes sharing a signature
and emits a derived ``invariant`` record whose ``source_receipts`` link
back to every supporting episode — evidence is preserved, not
summarised away.

§22 forgetting/invalidation: records carry a ``regime``; ``invalidate``
marks derived knowledge ``stale`` when its regime changes — history is
kept verbatim and stale rules stop applying but are never rewritten.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

from .receipts import ReceiptLedger

MEMORY_VERSION = "toe.memory/v1"

NAMESPACES = (
    "observation",
    "episodic",
    "causal",
    "strategy",
    "world_model",
    "procedural",
)


def _sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str).encode()
    ).hexdigest()


class MemoryStore:
    """One record list; namespaces are views. Receipts give provenance."""

    def __init__(self, ledger: Optional[ReceiptLedger] = None) -> None:
        self.ledger = ledger or ReceiptLedger(run_id="memory")
        self._records: List[Dict[str, Any]] = []

    # -- write -------------------------------------------------------

    def remember(
        self,
        namespace: str,
        content: Any,
        *,
        causal_tags: Sequence[str] = (),
        regime: Optional[str] = None,
        t: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Store a record. ``causal_tags`` is the declared reason this
        information may change future reasoning — the §19 criterion."""
        if namespace not in NAMESPACES:
            raise ValueError(f"unknown memory namespace {namespace!r}")
        receipt = self.ledger.issue(
            "memory.write",
            inputs={"namespace": namespace, "t": t},
            config={"regime": regime},
            output=content,
        )
        rec = {
            "id": _sha({"n": namespace, "c": content, "i": len(self._records)}),
            "namespace": namespace,
            "content": content,
            "causal_tags": sorted(set(causal_tags)),
            "regime": regime,
            "t": t if t is not None else len(self._records),
            "receipt_sha256": receipt.receipt_sha256,
            "status": "active",
            "source_receipts": [],
            "ts": time.time(),
        }
        self._records.append(rec)
        return rec

    # -- read --------------------------------------------------------

    def recall(
        self,
        *,
        causal_tags: Sequence[str] = (),
        namespace: Optional[str] = None,
        include_stale: bool = False,
    ) -> List[Dict[str, Any]]:
        """Content-addressed recall — retrieves by declared causal
        relevance over arbitrary time gaps (the §20 mechanism)."""
        want = set(causal_tags)
        return [
            r
            for r in self._records
            if (namespace is None or r["namespace"] == namespace)
            and (include_stale or r["status"] == "active")
            and (not want or want & set(r["causal_tags"]))
        ]

    def recent_window_baseline(
        self, window: int, *, causal_tags: Sequence[str] = ()
    ) -> List[Dict[str, Any]]:
        """Recency-only comparator for §20: same records, last ``window``
        by insertion order. Forgets anything older regardless of causal
        relevance — the baseline intelligent memory must beat."""
        want = set(causal_tags)
        tail = self._records[-window:] if window else []
        return [
            r
            for r in tail
            if r["status"] == "active" and (not want or want & set(r["causal_tags"]))
        ]

    # -- §21 consolidation ------------------------------------------

    def consolidate(
        self,
        signature: Callable[[Mapping[str, Any]], Any],
        *,
        min_support: int = 2,
        regime: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Episodes → shared structure → compact reusable knowledge.

        Groups episodic records by ``signature(content)``; each group
        with ≥ ``min_support`` members yields a ``causal``-namespace
        invariant whose ``source_receipts`` list every supporting
        episode's receipt — a learned rule linked to its evidence.
        """
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for r in self._records:
            if r["namespace"] != "episodic" or r["status"] != "active":
                continue
            if regime is not None and r["regime"] != regime:
                continue
            key = _sha(signature(r["content"]))
            groups.setdefault(key, []).append(r)
        invariants = []
        for members in groups.values():
            if len(members) < min_support:
                continue
            inv = signature(members[0]["content"])
            tags = sorted(
                set().union(*(m["causal_tags"] for m in members))
            )
            rec = self.remember(
                "causal",
                {"invariant": inv, "support": len(members)},
                causal_tags=tags,
                regime=members[0]["regime"],
            )
            rec["kind"] = "invariant"
            rec["source_receipts"] = [
                m["receipt_sha256"] for m in members
            ]
            invariants.append(rec)
        return invariants

    # -- §22 invalidation -------------------------------------------

    def invalidate(self, old_regime: str, new_regime: str) -> Dict[str, Any]:
        """Regime change → stale derived knowledge stops applying.

        Records authored under ``old_regime`` keep their bytes and
        receipts (history preserved); ``causal``/``strategy`` records —
        derived knowledge — flip to ``status: stale`` so ``recall``
        excludes them. Raw observations stay active: the past happened.
        """
        DERIVED = {"causal", "strategy", "world_model", "procedural"}
        n = 0
        for r in self._records:
            if (
                r["regime"] == old_regime
                and r["namespace"] in DERIVED
                and r["status"] == "active"
            ):
                r["status"] = "stale"
                r["invalidated_by"] = new_regime
                n += 1
        self.ledger.issue(
            "memory.regime_change",
            inputs={"old": old_regime, "new": new_regime},
            config={},
            output={"staled_records": n},
        )
        return {
            "staled_records": n,
            "preserved_records": len(self._records),
            "note": "history preserved; stale rules stop applying via recall",
        }

    def export(self) -> List[Dict[str, Any]]:
        return list(self._records)


__all__ = ["MEMORY_VERSION", "NAMESPACES", "MemoryStore"]
