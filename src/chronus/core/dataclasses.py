"""Dataclasses for the Chronus elevation roadmap (Tier 0).

Every dataclass here is frozen where the pseudocode implies immutability
and machine-checkable labels for capacity claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .enums import (
    AdapterBackend,
    AdapterRole,
    AdapterStatus,
    CapacityLabel,
    EvidenceClass,
    MemoryTier,
    TrustClass,
)


@dataclass(frozen=True)
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


@dataclass(frozen=True)
class CapabilityManifest:
    """The complete capability declaration for one adapter (§2.4)."""

    adapter_id: str
    product: str
    backend: AdapterBackend
    status: AdapterStatus
    role: AdapterRole
    core_count: int
    memory_bytes: int
    memory_tier: MemoryTier
    bandwidth_mbps: float
    spmd_lanes: int
    trust_class: TrustClass
    evidence_class: EvidenceClass
    projection: Optional[ConsortiumProjection] = None
    owner: Optional[str] = None

    def is_functional(self) -> bool:
        return self.status == AdapterStatus.FUNCTIONAL

    def is_typed_unavailable(self) -> bool:
        return self.status == AdapterStatus.TYPED_UNAVAILABLE


@dataclass(frozen=True)
class EffectiveCapacity:
    """A capacity figure with its physical units, ladder index, and label."""

    physical_units: int
    ladder_index: int
    effective: float
    label: CapacityLabel
    source: str = "unknown"

    def within_frozen_ladder(self) -> bool:
        from .constants import LUCAS_LADDER_RUNGS

        return self.ladder_index <= LUCAS_LADDER_RUNGS[-1]

    def is_effective_capacity(self) -> bool:
        return self.label == CapacityLabel.EFFECTIVE_CAPACITY


@dataclass(frozen=True)
class MemoryTierSpec:
    """A formal tier declaration (§2.5)."""

    tier: MemoryTier
    capacity: int
    bandwidth: float
    label: CapacityLabel
    evidence: EvidenceClass
    owner: str


@dataclass(frozen=True)
class EvidenceRecord:
    """A single verifiable evidence entry (Axiom 6: deterministic provenance)."""

    layer: str
    item_id: str
    input_digest: str
    config_digest: str
    output_digest: str
    trust_class: TrustClass
    signature: Optional[str] = None
    timestamp: Optional[str] = None

    def digest_chain(self) -> str:
        from hashlib import sha256

        return sha256(
            f"{self.input_digest}{self.config_digest}{self.output_digest}".encode(
                "utf-8"
            ),
        ).hexdigest()


@dataclass(frozen=True)
class ElevationAction:
    """An action that must pass all axioms in the pre-flight (Tier 8)."""

    action_id: str
    name: str
    context: Dict[str, Any]
