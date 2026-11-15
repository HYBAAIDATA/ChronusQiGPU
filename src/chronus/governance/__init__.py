"""Governance - Tier 8: Axiom enforcement for the Chronus elevation.

Enforces the eight Universal Principle Map axioms on every elevation
operation:

    A1_REPRESENTATION_TRUTH     - every capacity report names physical units +
                                    ladder index + envelope
    A2_EVIDENCE_SEPARATION      - Measured is not design envelope or speculation
    A3_VALIDITY_AUTHORITY       - SHA256d oracle unchanged; routing never
                                    overrides proof of work
    A4_FINITE_RESOURCE_ACCOUNTING - effective capacity is a maths-bounded
                                    Lucas ratio
    A5_IMMUTABLE_REFERENCE_CONSTANTS - Lucas rungs frozen; overrides create
                                    labelled simulation contexts
    A6_DETERMINISTIC_PROVENANCE - per-device evidence digest chains input/
                                    config/execution
    A7_COMPLETE_FALLBACK        - CPU emulator remains; no adapter hides
                                    failures via silent fallback
    A8_MEASUREMENT_BEFORE_PROMOTION - capacity increases only after
                                    conformance tests pass
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from chronus.core.enums import Axiom

__all__ = [
    "ElevationAction",
    "AxiomViolation",
    "enforce_axiom",
    "elevation_preflight",
]


# ---------------------------------------------------------------------------
# Tier 8.1 - Elevation action model (section 5)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ElevationAction:
    """An action that must pass all axioms in the pre-flight."""

    action_id: str
    name: str
    context: Dict[str, Any]


# ---------------------------------------------------------------------------
# Tier 8.2 - Axiom enforcement (section 5)
# ---------------------------------------------------------------------------


def enforce_axiom(axiom: Axiom, context: Dict[str, Any]) -> bool:
    """Enforce a single axiom against the given context.

    Returns True if the axiom holds, False otherwise.
    """
    if axiom == Axiom.A1_REPRESENTATION_TRUTH:
        # Every capacity report names physical units + ladder index + envelope
        report = context.get("capacity_report")
        if report is None:
            return False
        for field in ("physical_units", "ladder_index", "effective"):
            if not hasattr(report, field):
                return False
        return True

    if axiom == Axiom.A2_EVIDENCE_SEPARATION:
        # Measured is not design envelope or speculative projection
        claimed_label = context.get("claimed_label")
        actual_class = context.get("actual_evidence_class")
        return claimed_label == actual_class

    if axiom == Axiom.A3_VALIDITY_AUTHORITY:
        # SHA256d oracle unchanged; routing never overrides proof of work
        return not context.get("routing_overrides_proof_of_work", False)

    if axiom == Axiom.A4_FINITE_RESOURCE_ACCOUNTING:
        # Effective capacity is a maths-bounded Lucas ratio
        effective = context.get("effective")
        if effective is None:
            return False
        from chronus.core.constants import LUCAS_LADDER_RUNGS

        return effective <= LUCAS_LADDER_RUNGS[-1]

    if axiom == Axiom.A5_IMMUTABLE_REFERENCE_CONSTANTS:
        # Lucas rungs frozen; overrides create labelled simulation contexts
        from chronus.core.constants import LUCAS_LADDER_RUNGS

        return LUCAS_LADDER_RUNGS == tuple(sorted(LUCAS_LADDER_RUNGS))

    if axiom == Axiom.A6_DETERMINISTIC_PROVENANCE:
        # Per-device evidence digest chains input/config/execution
        ctx = context.get("context")
        if ctx is None:
            return False
        from hashlib import sha256

        payload = (
            f"{ctx.get('input')}{ctx.get('config')}{ctx.get('execution')}"
        ).encode("utf-8")
        expected = sha256(payload).hexdigest()
        return expected == context.get("digest")

    if axiom == Axiom.A7_COMPLETE_FALLBACK:
        # CPU emulator remains; no adapter hides failures via silent fallback
        return (
            context.get("fallback_is_logged", False)
            and context.get("cpu_emulator_available", False)
            and not context.get("silent_success_detected", False)
        )

    if axiom == Axiom.A8_MEASUREMENT_BEFORE_PROMOTION:
        # Capacity increases only after conformance tests pass
        promotion = context.get("promotion")
        if promotion is None:
            return False
        return (
            promotion.get("conformance_passed", False)
            and promotion.get("evidence_recorded", False)
        )

    return False


# ---------------------------------------------------------------------------
# Tier 8.3 - Pre-flight check (section 5)
# ---------------------------------------------------------------------------


def elevation_preflight(action: ElevationAction) -> bool:
    """Run all axioms as a pre-flight on every elevation operation.

    Raises AxiomViolation if any axiom fails.
    """
    for axiom in Axiom:
        if not enforce_axiom(axiom, action.context):
            raise AxiomViolation(axiom, action.action_id)
    return True


class AxiomViolation(RuntimeError):
    """An elevation action failed an axiom pre-flight check."""

    def __init__(self, axiom: Axiom, action_id: str) -> None:
        self.axiom = axiom
        self.action_id = action_id
        super().__init__(f"Axiom {axiom} violated by action {action_id}")
