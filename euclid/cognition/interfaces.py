"""Explicit typed contracts between the cognitive core and its specialists.

:class:`~euclid.cognition.core.GeneralIntelligenceCore` owns no specialist
implementation; it orchestrates these interfaces and records every exchange.
A specialist may be a learned component, a symbolic engine, or a deterministic
baseline — the core cannot tell and must not care.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable

from .state import (
    AnalogyMapping,
    CandidateAction,
    CognitiveState,
    EvidenceItem,
    Hypothesis,
    MemoryKind,
    PlanNode,
    PredictionRecord,
)


@dataclass(frozen=True)
class MemoryItem:
    memory_id: str
    kind: MemoryKind
    payload: Mapping[str, Any]
    provenance: str
    structural_features: frozenset[str] = frozenset()
    transfer_value: float = 0.0
    deprecated: bool = False

    def __post_init__(self) -> None:
        if not self.memory_id or not self.provenance:
            raise ValueError("memory identity and provenance are required")


@dataclass(frozen=True)
class Intervention:
    action: str
    expected_divergence: float
    rationale: str


@dataclass(frozen=True)
class StrategyChoice:
    strategy_id: str
    alternatives: tuple[str, ...]
    basis: str  # why this strategy was selected (must cite evidence or prior)


@dataclass(frozen=True)
class ControlAssessment:
    """Metacognitive verdict over the current episode."""

    action: str  # continue | change_strategy | change_representation |
    # seek_evidence | new_hypothesis | adjust_plan_depth | reuse_skill |
    # synthesise_skill | abandon_transfer | replan | halt_stalled
    rationale: str
    signals: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelHealth:
    status: str  # healthy | degraded | breakdown
    mean_error: float
    detail: str = ""


@runtime_checkable
class WorldModel(Protocol):
    """Active reasoning substrate; rollout output is always imagined."""

    def predict(self, context: str, action: str) -> PredictionRecord: ...

    def rollout(self, context: str, actions: Sequence[str]) -> list[PredictionRecord]: ...

    def update(self, context: str, action: str, observed: str) -> float:
        """Ingest one observed transition; return absolute prediction error."""
        ...

    def health(self) -> ModelHealth: ...


@runtime_checkable
class MemorySystem(Protocol):
    def retrieve(
        self, structural_features: frozenset[str], kinds: Sequence[MemoryKind] | None = None
    ) -> list[MemoryItem]: ...

    def store(self, item: MemoryItem) -> None: ...

    def deprecate(self, memory_id: str, rationale: str) -> None: ...


@runtime_checkable
class AnalogyEngine(Protocol):
    def find(
        self,
        structural_features: frozenset[str],
        memories: Sequence[MemoryItem],
        surface_features: frozenset[str] = frozenset(),
    ) -> list[AnalogyMapping]: ...


@runtime_checkable
class Abducer(Protocol):
    def hypothesise(
        self, observations: Sequence[EvidenceItem], state: CognitiveState
    ) -> list[Hypothesis]:
        """Return competing explanations; must not collapse to one prematurely."""
        ...


@runtime_checkable
class Deducer(Protocol):
    def consequences(
        self, hypothesis: Hypothesis, world_model: WorldModel, context: str
    ) -> list[PredictionRecord]: ...


@runtime_checkable
class CausalDiscriminator(Protocol):
    def discriminate(
        self,
        hypotheses: Sequence[Hypothesis],
        predictions: Mapping[str, Sequence[PredictionRecord]],
    ) -> Intervention | None:
        """Choose an intervention that maximally separates the hypotheses."""
        ...


@runtime_checkable
class MetaLearner(Protocol):
    def select_strategy(
        self, problem_class: str, available: Sequence[str]
    ) -> StrategyChoice: ...

    def update(
        self, problem_class: str, strategy_id: str, success: bool, detail: str = ""
    ) -> None: ...


@runtime_checkable
class MetaController(Protocol):
    def assess(self, state: CognitiveState) -> ControlAssessment: ...


@runtime_checkable
class Planner(Protocol):
    def plan(self, goal: str, state: CognitiveState) -> list[PlanNode]: ...

    def replan(self, goal: str, state: CognitiveState, failure: Mapping[str, Any]) -> list[PlanNode]: ...


@runtime_checkable
class SkillComposer(Protocol):
    def compose(self, goal: str, state: CognitiveState) -> list[CandidateAction]: ...


@runtime_checkable
class ObjectiveFunction(Protocol):
    def evaluate(
        self, candidates: Sequence[CandidateAction], context: Mapping[str, Any]
    ) -> list[CandidateAction]:
        """Score and rank; the weights used must be recorded on each candidate."""
        ...


@runtime_checkable
class Executor(Protocol):
    """Governed execution boundary; the only path from cognition to world."""

    def execute(self, action: str, payload: Mapping[str, Any]) -> Mapping[str, Any]: ...


__all__ = [
    "Abducer",
    "AnalogyEngine",
    "CausalDiscriminator",
    "ControlAssessment",
    "Deducer",
    "Executor",
    "Intervention",
    "MemoryItem",
    "MemorySystem",
    "MetaController",
    "MetaLearner",
    "ModelHealth",
    "ObjectiveFunction",
    "Planner",
    "SkillComposer",
    "StrategyChoice",
    "WorldModel",
]
