"""P0 canonical search-identity postcondition, not a new planning authority.

Call only from an independently classified canonical execution path. Missing
fallback provenance must never be used to establish canonical classification.
Device/route fallback can retain Hendrix; nonce-order substitution cannot.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .search_plan import ExecutionRecord, SearchPlan

HENDRIX = "hendrix_coprime_stride"


def canonical_nonce_order(order: str) -> str:
    if order != HENDRIX:
        raise ValueError(
            "canonical PYTHIA execution requires the Hendrix nonce order"
        )
    return order


def require_canonical_execution(
    plan: SearchPlan, record: ExecutionRecord
) -> None:
    """Check execution provenance before a candidate leaves the router.

    A refused/invalidated zero-work record does not invent executed provenance.
    All records reporting positive completed work must bind the complete chain.
    This check neither validates proof nor permits submission.
    """
    expected = canonical_nonce_order(plan.nonce_order)
    if record.completed_work_items == 0:
        return
    if record.planned_nonce_order != expected:
        raise ValueError(
            "canonical execution planned-order provenance mismatch"
        )
    if record.requested_nonce_order != expected:
        raise ValueError(
            "canonical execution requested-order provenance mismatch"
        )
    if record.executed_nonce_order != expected:
        raise ValueError(
            "canonical execution executed-order provenance "
            "missing or mismatched"
        )
    if record.nonce_order_fallback_reason is not None:
        raise ValueError(
            "canonical execution cannot carry nonce-order fallback provenance"
        )
