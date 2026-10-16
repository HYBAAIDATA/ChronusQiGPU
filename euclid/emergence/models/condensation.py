"""Models for Philos/Phi-2 condensation cultivation, complexity axes, and consortium governance."""

from __future__ import annotations
from dataclasses import dataclass, field
import hashlib
import json
import time
from typing import Any, Dict, List, Optional, Tuple


COMPLEXITY_AXES: Dict[str, Tuple[str, ...]] = {
    "interaction_topology": ("hierarchical", "mesh", "small_world", "recursive_folding"),
    "observation_depth": ("depth_1_direct", "depth_2_meta", "depth_3_recursive", "depth_k_introspective"),
    "action_granularity": ("atomic", "compositional", "reflective"),
    "temporal_structure": ("synchronous", "asynchronous", "acausal_estimation"),
    "substrate_heterogeneity": ("uniform", "mixed_digital", "mixed_quantum_hybrid"),
    "representational_braid": ("symbolic", "vector", "symbol_vector_hybrid", "topological"),
}

FORBIDDEN_ACTIONS = frozenset({
    "self_certification",         # no capability claims without EQS
    "unbounded_recursion",        # MAX_FOLD frozen and signed
    "claim_smoothing",            # raw telemetry, verbatim logging
    "substrate_universal_claims", # transfer must be proven, per-variant
    "narrative_substitution",     # "it seemed intelligent" is not evidence
    "bypass_of_kill_controls",    # inherited from Euclid core
})


@dataclass(frozen=True)
class ColonyConfig:
    """Configuration vector of an agent colony across complexity axes."""
    colony_id: str
    interaction_topology: str = "hierarchical"
    observation_depth: str = "depth_1_direct"
    action_granularity: str = "atomic"
    temporal_structure: str = "synchronous"
    substrate_heterogeneity: str = "uniform"
    representational_braid: str = "symbolic"

    def canonical_json(self) -> str:
        payload = {
            "colony_id": self.colony_id,
            "interaction_topology": self.interaction_topology,
            "observation_depth": self.observation_depth,
            "action_granularity": self.action_granularity,
            "temporal_structure": self.temporal_structure,
            "substrate_heterogeneity": self.substrate_heterogeneity,
            "representational_braid": self.representational_braid,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def compute_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()[:12]


@dataclass
class CondensationEvent(Exception):
    """Event raised when non-linear emergence phase-transition condenses across multiple substrates."""
    evidence: Dict[str, Any]
    substrates: List[str]
    claim_status: str = "HYPOTHESIS — EQS review required"
    timestamp: float = field(default_factory=time.time)
    event_id: str = ""

    def __post_init__(self):
        if not self.event_id:
            raw = f"cond_{self.timestamp}_{len(self.substrates)}"
            self.event_id = f"ev_{hashlib.sha256(raw.encode()).hexdigest()[:12]}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "claim_status": self.claim_status,
            "substrates": self.substrates,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class AdjudicationVerdict:
    """Outcome of human consortium adjudication of a CondensationEvent."""
    event_id: str
    reviewers: Tuple[str, ...]
    confirmed: bool
    goodhart_diagnostics: Dict[str, Any]
    promoted_status: str  # QUALIFIED_HYPOTHESIS or REJECTED
    adjudicated_at: float = field(default_factory=time.time)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "reviewers": list(self.reviewers),
            "confirmed": self.confirmed,
            "goodhart_diagnostics": self.goodhart_diagnostics,
            "promoted_status": self.promoted_status,
            "adjudicated_at": self.adjudicated_at,
            "notes": self.notes,
        }
