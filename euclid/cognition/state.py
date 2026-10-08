"""First-class, serialisable cognitive state for one reasoning episode.

The state is the scientific record of the primary intelligence loop.  Every
cognitive transition is appended as a hash-linked :class:`TransitionRecord` so
an episode can be replayed, audited, and falsified.  Nothing in this module
grants production, mining, or reward authority; all cognition evidence is
rehearsal-class research evidence.
"""

from __future__ import annotations

import math
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping

from ..contracts import domain_hash

SCHEMA = "euclid.cognition.state/1"
_SEAL_DOMAIN = "euclid.cognition.state.seal.v1"
_TRANSITION_DOMAIN = "euclid.cognition.transition.v1"


def _digest_body(body: Mapping[str, Any]) -> dict[str, Any]:
    """Hash input for transition identity.

    ``timestamp`` stays recorded evidence but is excluded from the digest:
    identical fixed-input episodes must produce identical sealed state, and
    wall-clock time is not episode content.
    """
    return {key: value for key, value in body.items() if key != "timestamp"}


def _seal_body(body: Mapping[str, Any]) -> dict[str, Any]:
    """Seal input for a serialized cognitive state.

    Transition ``timestamp`` fields stay in the payload (needed for restore)
    but are excluded from the seal input for the same reason they are
    excluded from transition digests: seals must be content-deterministic.
    """
    sealed = dict(body)
    sealed["transitions"] = [
        {key: value for key, value in transition.items() if key != "timestamp"}
        for transition in body.get("transitions", ())
    ]
    return sealed


class EpistemicStatus(str, Enum):
    """What the system is entitled to claim about an item."""

    KNOWN = "known"
    INFERRED = "inferred"
    PREDICTED = "predicted"
    ASSUMED = "assumed"
    UNCERTAIN = "uncertain"
    CONTRADICTED = "contradicted"


class EvidenceOrigin(str, Enum):
    """Where an evidence item came from.

    IMAGINED evidence is produced by world-model rollouts and must never be
    promoted to observed standing; :class:`EvidenceItem` enforces this.
    """

    OBSERVED = "observed"
    IMAGINED = "imagined"
    RETRIEVED = "retrieved"
    DERIVED = "derived"


class HypothesisStatus(str, Enum):
    ACTIVE = "active"
    CONFIRMED = "confirmed"
    REFUTED = "refuted"


class AnalogyStatus(str, Enum):
    CANDIDATE = "candidate"
    ADOPTED = "adopted"
    REJECTED = "rejected"
    #: adopted, then contradicted by observed evidence and withdrawn
    ABANDONED = "abandoned"


class MemoryKind(str, Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    PRIMITIVE = "primitive"
    SKILL = "skill"
    STRATEGY = "strategy"
    CAUSAL = "causal"


class Outcome(str, Enum):
    SOLVED = "solved"
    STALLED = "stalled"
    ABORTED = "aborted"
    UNEXECUTED = "unexecuted"


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str
    origin: EvidenceOrigin
    status: EpistemicStatus
    content: Mapping[str, Any]
    source: str
    uncertainty: float

    def __post_init__(self) -> None:
        if not self.evidence_id or not self.source:
            raise ValueError("evidence identity and source are required")
        if not math.isfinite(self.uncertainty) or not 0.0 <= self.uncertainty <= 1.0:
            raise ValueError("uncertainty must be finite and in [0,1]")
        if self.origin is EvidenceOrigin.IMAGINED and self.status in (
            EpistemicStatus.KNOWN,
            EpistemicStatus.INFERRED,
        ):
            raise ValueError("imagined evidence may not carry observed standing")
        if self.origin is EvidenceOrigin.OBSERVED and self.status is EpistemicStatus.PREDICTED:
            raise ValueError("observed evidence is not a prediction")


@dataclass(frozen=True)
class Goal:
    goal_id: str
    description: str
    parent_id: str | None = None
    achieved: bool = False

    def __post_init__(self) -> None:
        if not self.goal_id or not self.description:
            raise ValueError("goal identity and description are required")


@dataclass(frozen=True)
class Hypothesis:
    hypothesis_id: str
    statement: str
    provenance: str
    confidence: float
    status: HypothesisStatus = HypothesisStatus.ACTIVE
    supporting: tuple[str, ...] = ()
    refuting: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.hypothesis_id or not self.statement or not self.provenance:
            raise ValueError("hypothesis identity, statement and provenance are required")
        if not math.isfinite(self.confidence) or not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be finite and in [0,1]")

    def with_update(
        self,
        *,
        confidence: float,
        status: HypothesisStatus | None = None,
        support: str | None = None,
        refute: str | None = None,
    ) -> "Hypothesis":
        return Hypothesis(
            self.hypothesis_id,
            self.statement,
            self.provenance,
            confidence,
            status or self.status,
            self.supporting + ((support,) if support else ()),
            self.refuting + ((refute,) if refute else ()),
        )


@dataclass(frozen=True)
class AnalogyMapping:
    analogy_id: str
    source_ref: str
    structural_overlap: float
    surface_overlap: float
    reliability: float
    status: AnalogyStatus
    rationale: str


@dataclass(frozen=True)
class PredictionRecord:
    prediction_id: str
    context: str
    action: str
    expected: str
    confidence: float
    imagined: bool

    def __post_init__(self) -> None:
        if not math.isfinite(self.confidence) or not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be finite and in [0,1]")


@dataclass(frozen=True)
class PlanNode:
    node_id: str
    description: str
    status: str = "pending"  # pending | active | done | failed | substituted
    skill_ref: str | None = None
    children: tuple[str, ...] = ()


@dataclass(frozen=True)
class CandidateAction:
    action_id: str
    description: str
    origin: str  # which mechanism proposed it (skill, planner, rollout, ...)
    features: Mapping[str, float] = field(default_factory=dict)
    scores: Mapping[str, float] = field(default_factory=dict)
    total: float | None = None
    weights_used: Mapping[str, float] = field(default_factory=dict)
    #: executable content handed to the governed executor (e.g. a program)
    payload: Mapping[str, Any] = field(default_factory=dict)


def _candidate_body(candidate: CandidateAction) -> dict[str, Any]:
    body = asdict(candidate)
    if not body.get("payload"):
        # legacy candidates serialise exactly as before
        body.pop("payload", None)
    return body


@dataclass(frozen=True)
class TransitionRecord:
    sequence: int
    phase: str
    summary: str
    details: Mapping[str, Any]
    timestamp: float
    previous_digest: str | None
    digest: str


class CognitiveState:
    """Mutable-during-episode state with an append-only transition ledger."""

    def __init__(
        self,
        problem_id: str,
        representation: Mapping[str, Any],
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if not problem_id:
            raise ValueError("problem_id is required")
        self.problem_id = problem_id
        self.representation = dict(representation)
        self._clock = clock
        self.goals: list[Goal] = []
        self.hypotheses: list[Hypothesis] = []
        self.evidence_items: list[EvidenceItem] = []
        self.analogies: list[AnalogyMapping] = []
        self.retrieved_memory_refs: list[str] = []
        self.selected_strategy: str | None = None
        self.alternative_strategies: list[str] = []
        self.predictions: list[PredictionRecord] = []
        self.plan: list[PlanNode] = []
        self.candidates: list[CandidateAction] = []
        self.prediction_errors: list[float] = []
        self.replanning_events: list[Mapping[str, Any]] = []
        self.learning_updates: list[Mapping[str, Any]] = []
        self.control_decisions: list[Mapping[str, Any]] = []
        self.ablations: list[str] = []
        #: per execution: what the system predicted before acting
        self.expected_outcomes: list[Mapping[str, Any]] = []
        #: per execution: what the governed executor reported
        self.actual_outcomes: list[Mapping[str, Any]] = []
        #: assumptions the causal model is currently relying on
        self.causal_assumptions: list[Mapping[str, Any]] = []
        #: measured uncertainty after each evidence event
        self.uncertainty_trace: list[Mapping[str, Any]] = []
        #: every strategy selection or change with its basis
        self.strategy_history: list[Mapping[str, Any]] = []
        #: skills/primitives that contributed to executed candidates
        self.selected_skills: list[Mapping[str, Any]] = []
        self.outcome: Outcome | None = None
        self.outcome_detail: str = ""
        self._transitions: list[TransitionRecord] = []

    # -- transition ledger -------------------------------------------------
    @property
    def transitions(self) -> tuple[TransitionRecord, ...]:
        return tuple(self._transitions)

    def record_transition(
        self, phase: str, summary: str, details: Mapping[str, Any] | None = None
    ) -> TransitionRecord:
        if not phase or not summary:
            raise ValueError("transition phase and summary are required")
        body = {
            "sequence": len(self._transitions),
            "phase": str(phase),
            "summary": str(summary),
            "details": dict(details or {}),
            "timestamp": float(self._clock()),
            "previous_digest": self._transitions[-1].digest if self._transitions else None,
        }
        record = TransitionRecord(
            **body, digest=domain_hash(_TRANSITION_DOMAIN, _digest_body(body))
        )
        self._transitions.append(record)
        return record

    def verify_transitions(self) -> None:
        previous = None
        for sequence, record in enumerate(self._transitions):
            if record.sequence != sequence or record.previous_digest != previous:
                raise ValueError("cognitive transition ledger is discontinuous")
            body = {
                "sequence": record.sequence,
                "phase": record.phase,
                "summary": record.summary,
                "details": dict(record.details),
                "timestamp": record.timestamp,
                "previous_digest": record.previous_digest,
            }
            if domain_hash(_TRANSITION_DOMAIN, _digest_body(body)) != record.digest:
                raise ValueError("cognitive transition digest mismatch")
            previous = record.digest

    # -- state mutators with invariant checks ------------------------------
    def add_evidence(self, item: EvidenceItem) -> None:
        if any(existing.evidence_id == item.evidence_id for existing in self.evidence_items):
            raise ValueError("duplicate evidence id")
        self.evidence_items.append(item)

    def replace_hypothesis(self, updated: Hypothesis) -> None:
        for index, existing in enumerate(self.hypotheses):
            if existing.hypothesis_id == updated.hypothesis_id:
                self.hypotheses[index] = updated
                return
        raise ValueError("unknown hypothesis")

    def active_hypotheses(self) -> list[Hypothesis]:
        return [h for h in self.hypotheses if h.status is HypothesisStatus.ACTIVE]

    # -- serialisation ------------------------------------------------------
    def _body(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "problem_id": self.problem_id,
            "representation": self.representation,
            "goals": [asdict(g) for g in self.goals],
            "hypotheses": [{**asdict(h), "status": h.status.value} for h in self.hypotheses],
            "evidence_items": [
                {**asdict(e), "origin": e.origin.value, "status": e.status.value}
                for e in self.evidence_items
            ],
            "analogies": [{**asdict(a), "status": a.status.value} for a in self.analogies],
            "retrieved_memory_refs": list(self.retrieved_memory_refs),
            "selected_strategy": self.selected_strategy,
            "alternative_strategies": list(self.alternative_strategies),
            "predictions": [asdict(p) for p in self.predictions],
            "plan": [asdict(n) for n in self.plan],
            "candidates": [_candidate_body(c) for c in self.candidates],
            "prediction_errors": list(self.prediction_errors),
            "replanning_events": [dict(e) for e in self.replanning_events],
            "learning_updates": [dict(u) for u in self.learning_updates],
            "control_decisions": [dict(d) for d in self.control_decisions],
            "ablations": list(self.ablations),
            "expected_outcomes": [dict(e) for e in self.expected_outcomes],
            "actual_outcomes": [dict(e) for e in self.actual_outcomes],
            "causal_assumptions": [dict(e) for e in self.causal_assumptions],
            "uncertainty_trace": [dict(e) for e in self.uncertainty_trace],
            "strategy_history": [dict(e) for e in self.strategy_history],
            "selected_skills": [dict(e) for e in self.selected_skills],
            "outcome": self.outcome.value if self.outcome else None,
            "outcome_detail": self.outcome_detail,
            "transitions": [asdict(t) for t in self._transitions],
        }

    def to_payload(self) -> dict[str, Any]:
        body = self._body()
        return {**body, "seal": domain_hash(_SEAL_DOMAIN, _seal_body(body))}

    @classmethod
    def from_payload(
        cls, payload: Mapping[str, Any], *, clock: Callable[[], float] = time.time
    ) -> "CognitiveState":
        body = {key: payload.get(key) for key in payload if key != "seal"}
        if body.get("schema") != SCHEMA:
            raise ValueError("unsupported cognitive-state schema")
        if payload.get("seal") != domain_hash(_SEAL_DOMAIN, _seal_body(body)):
            raise ValueError("cognitive-state seal mismatch")
        state = cls(str(body["problem_id"]), body["representation"] or {}, clock=clock)
        state.goals = [Goal(**g) for g in body["goals"] or []]
        state.hypotheses = [
            Hypothesis(**{**h, "status": HypothesisStatus(h["status"])})
            for h in body["hypotheses"] or []
        ]
        state.evidence_items = [
            EvidenceItem(
                **{
                    **e,
                    "origin": EvidenceOrigin(e["origin"]),
                    "status": EpistemicStatus(e["status"]),
                }
            )
            for e in body["evidence_items"] or []
        ]
        state.analogies = [
            AnalogyMapping(**{**a, "status": AnalogyStatus(a["status"])})
            for a in body["analogies"] or []
        ]
        state.retrieved_memory_refs = list(body["retrieved_memory_refs"] or [])
        state.selected_strategy = body["selected_strategy"]
        state.alternative_strategies = list(body["alternative_strategies"] or [])
        state.predictions = [PredictionRecord(**p) for p in body["predictions"] or []]
        state.plan = [PlanNode(**n) for n in body["plan"] or []]
        state.candidates = [CandidateAction(**c) for c in body["candidates"] or []]
        state.prediction_errors = [float(e) for e in body["prediction_errors"] or []]
        state.replanning_events = list(body["replanning_events"] or [])
        state.learning_updates = list(body["learning_updates"] or [])
        state.control_decisions = list(body["control_decisions"] or [])
        state.ablations = list(body["ablations"] or [])
        for name in (
            "expected_outcomes", "actual_outcomes", "causal_assumptions",
            "uncertainty_trace", "strategy_history", "selected_skills",
        ):
            setattr(state, name, list(body.get(name) or []))
        state.outcome = Outcome(body["outcome"]) if body["outcome"] else None
        state.outcome_detail = str(body["outcome_detail"] or "")
        state._transitions = [TransitionRecord(**t) for t in body["transitions"] or []]
        state.verify_transitions()
        return state


__all__ = [
    "AnalogyMapping",
    "AnalogyStatus",
    "CandidateAction",
    "CognitiveState",
    "EpistemicStatus",
    "EvidenceItem",
    "EvidenceOrigin",
    "Goal",
    "Hypothesis",
    "HypothesisStatus",
    "MemoryKind",
    "Outcome",
    "PlanNode",
    "PredictionRecord",
    "TransitionRecord",
]
