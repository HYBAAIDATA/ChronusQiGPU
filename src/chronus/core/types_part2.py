"""Tier 0.5, 0.6, 0.7, 0.8 — consortium projections, Lucas constants, axioms."""

from __future__ import annotations

from .enums import CapacityLabel, EvidenceClass, TrustClass


@__import__("dataclasses").dataclass(frozen=True)
class ConsortiumProjection:
    """A labelled roadmap target with its honest counterpart.

    Every projection must name a label and an evidence class so that Axiom 1
    (representation truth) and Axiom 2 (evidence separation) are type-enforced.
    """

    aspect: str
    projection_value: str
    honest_mapping: str
    label: CapacityLabel
    evidence_class: EvidenceClass

    def is_label(self, label: CapacityLabel) -> bool:
        return self.label == label

    def is_evidence_class(self, evidence: EvidenceClass) -> bool:
        return self.evidence_class == evidence


# ---------------------------------------------------------------------------
# Tier 0.6 — Lucas ladder constants (Axiom 4 & 5: immutable)
# ---------------------------------------------------------------------------

# Frozen Lucas/Pisot ladder rungs (Axiom 4).  Any effective-capacity value is
# clamped to the frozen rungs; an override creates a labelled simulation
# context and never mutates the frozen ladder.
LUCAS_LADDER_RUNGS: tuple[int, ...] = (2, 3, 4, 7, 11, 18, 29, 47, 76, 123, 199)

# Immutable reference constants  (Axiom 5)
SPMD_DEFAULT_LANES: int = 32
SPMD_ROADMAP_MAX_LANES: int = 64
CU_POOL_CURRENT_SMS: int = 8
CU_POOL_ROADMAP_MID_SMS: int = 20
CU_POOL_ROADMAP_MAX_SMS: int = 64
