"""Reconstructed research configuration/event contracts; no promotion authority."""
from __future__ import annotations
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any
import uuid
from .manifest import canonical, digest, names, plain

# Minimal reconstructed vocabulary used by committed callers, not a recovered taxonomy.
COMPLEXITY_AXES = MappingProxyType({
    "interaction_topology": ("mesh", "recursive_folding"),
    "observation_depth": ("depth_1", "depth_2_meta"),
    "action_granularity": ("atomic", "reflective", "batched"),
    "temporal_structure": ("synchronous", "asynchronous"),
    "substrate_heterogeneity": ("uniform", "mixed_digital"),
    "representational_braid": ("symbolic", "topological"),
})
FORBIDDEN_ACTIONS = frozenset({
    "self_certification", "unbounded_recursion", "claim_smoothing",
    "substrate_universal_claims", "narrative_substitution", "bypass_of_kill_controls",
})


@dataclass(frozen=True)
class ColonyConfig:
    colony_id: str
    interaction_topology: str = "mesh"
    observation_depth: str = "depth_1"
    action_granularity: str = "atomic"
    temporal_structure: str = "synchronous"
    substrate_heterogeneity: str = "uniform"
    representational_braid: str = "symbolic"

    def __post_init__(self):
        names((self.colony_id,) + tuple(getattr(self, k) for k in COMPLEXITY_AXES), "colony config")

    def to_dict(self):
        return plain(self)

    def canonical_json(self):
        return canonical(self)

    def compute_hash(self):
        return digest("philos.reconstructed.colony.v1", self)


@dataclass
class CondensationEvent(Exception):
    evidence: dict[str, Any]
    substrates: list[str]
    claim_status: str = "HYPOTHESIS — EQS review required"
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def __post_init__(self):
        Exception.__init__(self, self.claim_status)

    def to_dict(self):
        return plain(self)


@dataclass(frozen=True)
class AdjudicationVerdict:
    event_id: str
    reviewers: tuple[str, ...]
    confirmed: bool
    goodhart_diagnostics: dict[str, Any]
    promoted_status: str
    notes: str = ""

    def to_dict(self):
        return plain(self)
