"""Deterministic reference specialists for the cognition loop.

These implementations exist so the primary intelligence loop is executable
and falsifiable end-to-end today, and so learned or mathematical specialists
can be benchmarked against honest baselines rather than against nothing.
They make no claim of frontier capability; every threshold is an explicit
constructor parameter, not a mystery constant.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import replace
from typing import Any, Callable, Mapping, Sequence

from ..contracts import domain_hash
from ..governance import Delegator
from .interfaces import (
    ControlAssessment,
    Intervention,
    MemoryItem,
    ModelHealth,
    StrategyChoice,
)
from .state import (
    AnalogyMapping,
    AnalogyStatus,
    CandidateAction,
    CognitiveState,
    EvidenceItem,
    Hypothesis,
    HypothesisStatus,
    MemoryKind,
    PlanNode,
    PredictionRecord,
)


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


class TableWorldModel:
    """Count-based discrete transition model with calibrated-ish uncertainty.

    Unknown transitions predict the literal token ``"unknown"`` at
    ``prior_confidence``; observed transitions predict their modal outcome.
    ``health()`` reports ``breakdown`` when recent mean error reaches
    ``breakdown_error`` — model failure is a measurable signal, not a vibe.
    """

    def __init__(
        self,
        *,
        prior_confidence: float = 0.2,
        breakdown_error: float = 0.75,
        window: int = 8,
    ) -> None:
        if not 0.0 <= prior_confidence <= 1.0:
            raise ValueError("prior_confidence must be in [0,1]")
        if not 0.0 < breakdown_error <= 1.0:
            raise ValueError("breakdown_error must be in (0,1]")
        self.prior_confidence = prior_confidence
        self.breakdown_error = breakdown_error
        self.window = window
        self._table: dict[tuple[str, str], Counter[str]] = {}
        self._errors: list[float] = []
        self._sequence = 0

    def _next_id(self, prefix: str) -> str:
        self._sequence += 1
        return f"{prefix}-{self._sequence}"

    def predict(self, context: str, action: str) -> PredictionRecord:
        counts = self._table.get((context, action))
        if not counts:
            return PredictionRecord(
                self._next_id("pred"), context, action, "unknown",
                self.prior_confidence, imagined=False,
            )
        outcome, hits = counts.most_common(1)[0]
        return PredictionRecord(
            self._next_id("pred"), context, action, outcome,
            hits / sum(counts.values()), imagined=False,
        )

    def rollout(self, context: str, actions: Sequence[str]) -> list[PredictionRecord]:
        # Rollouts are imagination, not observation: imagined=True always.
        return [replace(self.predict(context, a), imagined=True) for a in actions]

    def update(self, context: str, action: str, observed: str) -> float:
        expected = self.predict(context, action).expected
        error = 0.0 if expected == observed else 1.0
        self._table.setdefault((context, action), Counter())[observed] += 1
        self._errors.append(error)
        return error

    def health(self) -> ModelHealth:
        recent = self._errors[-self.window:]
        mean_error = sum(recent) / len(recent) if recent else 0.0
        if mean_error >= self.breakdown_error:
            return ModelHealth("breakdown", mean_error, "recent mean error above bound")
        if mean_error > 0.0:
            return ModelHealth("degraded", mean_error, "nonzero recent prediction error")
        return ModelHealth("healthy", mean_error)


class InMemoryMemorySystem:
    """Seven-kind memory with provenance and deprecation without deletion."""

    def __init__(self) -> None:
        self._items: dict[str, MemoryItem] = {}
        self._deprecations: dict[str, str] = {}

    def retrieve(
        self, structural_features: frozenset[str], kinds: Sequence[MemoryKind] | None = None
    ) -> list[MemoryItem]:
        allowed = set(kinds) if kinds else set(MemoryKind)
        items = [
            item for item in self._items.values()
            if item.kind in allowed and not item.deprecated
        ]
        return sorted(
            items,
            key=lambda item: (
                _jaccard(structural_features, item.structural_features),
                item.transfer_value,
                item.memory_id,
            ),
            reverse=True,
        )

    def store(self, item: MemoryItem) -> None:
        self._items[item.memory_id] = item

    def deprecate(self, memory_id: str, rationale: str) -> None:
        if memory_id not in self._items:
            raise ValueError("unknown memory")
        item = self._items[memory_id]
        self._items[memory_id] = replace(item, deprecated=True)
        self._deprecations[memory_id] = rationale  # historical record retained

    @property
    def deprecations(self) -> Mapping[str, str]:
        return dict(self._deprecations)


class StructuralAnalogyEngine:
    """Relational-structure analogy with superficial-similarity rejection.

    A mapping is a candidate only when structural overlap clears
    ``min_overlap``.  High surface overlap with low structural overlap is an
    explicit *rejection* class — the misleading-analogy case the charter
    demands we detect.
    """

    def __init__(self, *, min_overlap: float = 0.5) -> None:
        if not 0.0 < min_overlap <= 1.0:
            raise ValueError("min_overlap must be in (0,1]")
        self.min_overlap = min_overlap

    def find(
        self,
        structural_features: frozenset[str],
        memories: Sequence[MemoryItem],
        surface_features: frozenset[str] = frozenset(),
    ) -> list[AnalogyMapping]:
        mappings: list[AnalogyMapping] = []
        for item in memories:
            structural = _jaccard(structural_features, item.structural_features)
            memory_surface = frozenset(str(s) for s in item.payload.get("surface", ()))
            surface = _jaccard(surface_features, memory_surface)
            if structural >= self.min_overlap:
                status, rationale = (
                    AnalogyStatus.CANDIDATE,
                    f"structural overlap {structural:.3f} clears {self.min_overlap}",
                )
            elif surface > 0.0:
                status, rationale = (
                    AnalogyStatus.REJECTED,
                    f"superficial similarity rejected: surface {surface:.3f} "
                    f"but structural {structural:.3f}",
                )
            else:
                status, rationale = (
                    AnalogyStatus.REJECTED,
                    f"insufficient structural overlap {structural:.3f}",
                )
            mappings.append(AnalogyMapping(
                f"analogy-{domain_hash('euclid.analogy.ref.v1', item.memory_id)[:12]}",
                item.memory_id, structural, surface, structural, status, rationale,
            ))
        return mappings


class RuleAbducer:
    """Generates competing hypotheses from a declared explanation space.

    ``explanations`` maps hypothesis id -> action -> expected observation.
    The abducer never collapses to one explanation on its own; competition is
    resolved only by discriminating evidence in the core loop.
    """

    def __init__(self, explanations: Mapping[str, Mapping[str, str]]) -> None:
        if len(explanations) < 2:
            raise ValueError("abduction requires at least two competing explanations")
        self.explanations = {key: dict(value) for key, value in explanations.items()}

    def hypothesise(
        self, observations: Sequence[EvidenceItem], state: CognitiveState
    ) -> list[Hypothesis]:
        return [
            Hypothesis(
                hypothesis_id=key,
                statement=f"explanation:{key}",
                provenance="rule-abducer:declared-explanation-space",
                confidence=1.0 / len(self.explanations),
            )
            for key in sorted(self.explanations)
        ]


class ConsequenceDeducer:
    """Derives per-hypothesis predicted consequences from the explanation map."""

    def __init__(self, explanations: Mapping[str, Mapping[str, str]]) -> None:
        self.explanations = {key: dict(value) for key, value in explanations.items()}

    def consequences(
        self, hypothesis: Hypothesis, world_model: TableWorldModel, context: str
    ) -> list[PredictionRecord]:
        table = self.explanations.get(hypothesis.hypothesis_id, {})
        return [
            PredictionRecord(
                f"ded-{hypothesis.hypothesis_id}-{action}", context, action,
                expected, hypothesis.confidence, imagined=False,
            )
            for action, expected in sorted(table.items())
        ]


class DivergenceDiscriminator:
    """Selects the intervention on which hypotheses most disagree."""

    def discriminate(
        self,
        hypotheses: Sequence[Hypothesis],
        predictions: Mapping[str, Sequence[PredictionRecord]],
    ) -> Intervention | None:
        active = [h for h in hypotheses if h.status is HypothesisStatus.ACTIVE]
        if len(active) < 2:
            return None
        actions: dict[str, set[str]] = {}
        for hypothesis in active:
            for prediction in predictions.get(hypothesis.hypothesis_id, ()):
                actions.setdefault(prediction.action, set()).add(prediction.expected)
        best_action, best_divergence = None, 1
        for action in sorted(actions):
            divergence = len(actions[action])
            if divergence > best_divergence:
                best_action, best_divergence = action, divergence
        if best_action is None:
            return None
        return Intervention(
            best_action, float(best_divergence),
            f"action '{best_action}' separates {best_divergence} predicted outcomes "
            f"across {len(active)} active hypotheses",
        )


class HierarchicalPlanner:
    """Three-level reference planner: decompose -> act -> verify, with repair."""

    def plan(self, goal: str, state: CognitiveState) -> list[PlanNode]:
        return [
            PlanNode("p0", f"decompose: {goal}", children=("p1", "p2")),
            PlanNode("p1", f"act: {goal}"),
            PlanNode("p2", f"verify: {goal}"),
        ]

    def replan(
        self, goal: str, state: CognitiveState, failure: Mapping[str, Any]
    ) -> list[PlanNode]:
        cycle = int(failure.get("cycle", 0))
        repaired = [
            replace(node, status="failed") if node.status == "pending" else node
            for node in state.plan
        ]
        repaired.append(PlanNode(f"pR{cycle}", f"repair-and-act: {goal}"))
        return repaired


class BanditMetaLearner:
    """Per-problem-class strategy statistics with a negative-transfer guard.

    Strategies never transfer preference across problem classes: an unseen
    class falls back to the declared default order and says so.
    """

    def __init__(self, *, min_trials: int = 1) -> None:
        if min_trials < 1:
            raise ValueError("min_trials must be >= 1")
        self.min_trials = min_trials
        self._stats: dict[tuple[str, str], list[int]] = {}

    def select_strategy(
        self, problem_class: str, available: Sequence[str]
    ) -> StrategyChoice:
        if not available:
            raise ValueError("at least one strategy must be available")
        scored = []
        for strategy in available:
            stats = self._stats.get((problem_class, strategy))
            if stats and stats[1] >= self.min_trials:
                scored.append((stats[0] / stats[1], strategy))
        if not scored:
            return StrategyChoice(
                available[0], tuple(available[1:]),
                f"no per-class evidence for '{problem_class}'; default order retained "
                "(negative-transfer guard)",
            )
        scored.sort(reverse=True)
        chosen = scored[0][1]
        mean = scored[0][0]
        return StrategyChoice(
            chosen,
            tuple(s for s in available if s != chosen),
            f"per-class success rate {mean:.3f} over "
            f"{self._stats[(problem_class, chosen)][1]} trials",
        )

    def update(
        self, problem_class: str, strategy_id: str, success: bool, detail: str = ""
    ) -> None:
        stats = self._stats.setdefault((problem_class, strategy_id), [0, 0])
        stats[0] += 1 if success else 0
        stats[1] += 1

    def to_dict(self) -> dict[str, Any]:
        body = {
            "schema": "euclid.cognition.strategy-stats/1",
            "min_trials": self.min_trials,
            "stats": [
                {"problem_class": klass, "strategy_id": strategy,
                 "successes": value[0], "trials": value[1]}
                for (klass, strategy), value in sorted(self._stats.items())
            ],
        }
        return {**body, "seal": domain_hash("euclid.cognition.strategy-stats.seal.v1", body)}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "BanditMetaLearner":
        body = {"schema": payload.get("schema"), "min_trials": payload.get("min_trials"),
                "stats": payload.get("stats")}
        if body["schema"] != "euclid.cognition.strategy-stats/1":
            raise ValueError("unsupported strategy-stats schema")
        if payload.get("seal") != domain_hash(
            "euclid.cognition.strategy-stats.seal.v1", body
        ):
            raise ValueError("strategy-stats seal mismatch")
        learner = cls(min_trials=int(body["min_trials"] or 1))
        for row in body["stats"] or []:
            learner._stats[(str(row["problem_class"]), str(row["strategy_id"]))] = [
                int(row["successes"]), int(row["trials"])
            ]
        return learner


class SignalMetaController:
    """Evidence-driven metacognition over measurable episode signals.

    Every decision cites the signals that caused it; thresholds are injected,
    documented parameters, not hidden constants.
    """

    def __init__(self, *, error_replan_threshold: float = 0.5, stall_after: int = 3) -> None:
        if not 0.0 < error_replan_threshold <= 1.0:
            raise ValueError("error_replan_threshold must be in (0,1]")
        if stall_after < 1:
            raise ValueError("stall_after must be >= 1")
        self.error_replan_threshold = error_replan_threshold
        self.stall_after = stall_after

    def assess(self, state: CognitiveState) -> ControlAssessment:
        latest_error = state.prediction_errors[-1] if state.prediction_errors else 0.0
        consecutive_failures = 0
        for update in reversed(state.learning_updates):
            counts = update.get(
                "counts_for_control", update.get("kind") == "strategy"
            )
            if not counts:
                continue
            if update.get("success"):
                break
            consecutive_failures += 1
        signals = {
            "latest_prediction_error": latest_error,
            "consecutive_failures": float(consecutive_failures),
            "active_hypotheses": float(len(state.active_hypotheses())),
            "replans_so_far": float(len(state.replanning_events)),
        }
        if latest_error >= self.error_replan_threshold:
            return ControlAssessment(
                "replan",
                f"prediction error {latest_error:.3f} reached replan threshold "
                f"{self.error_replan_threshold}",
                signals,
            )
        if consecutive_failures >= self.stall_after:
            return ControlAssessment(
                "halt_stalled",
                f"{consecutive_failures} consecutive failed cycles reached "
                f"stall bound {self.stall_after}",
                signals,
            )
        return ControlAssessment("continue", "signals within operating bounds", signals)


class WeightedObjective:
    """Auditable multi-objective candidate ranking.

    The exact weight vector is recorded on every scored candidate, so
    adaptive weighting is inspectable and no objective can silently dominate:
    construction rejects non-finite or all-zero weights.
    """

    REQUIRED_FEATURES = ("correctness_estimate", "cost", "uncertainty")

    def __init__(self, weights: Mapping[str, float]) -> None:
        if not weights:
            raise ValueError("at least one objective weight is required")
        if any(not isinstance(v, (int, float)) or v != v or abs(v) == float("inf")
               for v in weights.values()):
            raise ValueError("weights must be finite")
        if sum(weights.values()) <= 0:
            raise ValueError("weights must not sum to zero or negative")
        self.weights = {str(k): float(v) for k, v in weights.items()}

    def evaluate(
        self, candidates: Sequence[CandidateAction], context: Mapping[str, Any]
    ) -> list[CandidateAction]:
        scored = []
        for candidate in candidates:
            components = {
                name: weight * float(candidate.features.get(name, 0.0))
                for name, weight in self.weights.items()
            }
            scored.append(replace(
                candidate, scores=components, total=sum(components.values()),
                weights_used=dict(self.weights),
            ))
        return sorted(scored, key=lambda c: (-(c.total or 0.0), c.action_id))


class StaticSkillComposer:
    """Reference composer: returns a declared candidate menu per episode.

    Skill provenance is explicit (``origin`` on each candidate) so composed
    behaviour can be attributed and later compared against learned composers.
    """

    def __init__(self, menu: Sequence[CandidateAction]) -> None:
        if not menu:
            raise ValueError("a skill menu is required")
        self.menu = list(menu)

    def compose(self, goal: str, state: CognitiveState) -> list[CandidateAction]:
        return list(self.menu)


class CallbackExecutor:
    """Minimal governed executor around a host callback (fail-closed shape)."""

    def __init__(self, handler: Callable[[str, Mapping[str, Any]], Mapping[str, Any]]) -> None:
        self._handler = handler

    def execute(self, action: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        result = self._handler(action, dict(payload))
        if not isinstance(result, Mapping):
            raise TypeError("executor result must be a mapping")
        return dict(result)


class DelegatorExecutor:
    """Adapter that routes execution through the governed Delegator gates."""

    def __init__(
        self,
        delegator: Delegator,
        organ_id: str,
        capability: str,
        *,
        confident: bool = True,
        safe: bool = True,
    ) -> None:
        self.delegator = delegator
        self.organ_id = organ_id
        self.capability = capability
        self.confident = confident
        self.safe = safe

    def execute(self, action: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return dict(self.delegator.dispatch(
            self.organ_id, self.capability,
            {"action": action, "payload": dict(payload)},
            confident=self.confident, safe=self.safe,
        ))


__all__ = [
    "BanditMetaLearner",
    "CallbackExecutor",
    "ConsequenceDeducer",
    "DelegatorExecutor",
    "DivergenceDiscriminator",
    "HierarchicalPlanner",
    "InMemoryMemorySystem",
    "RuleAbducer",
    "SignalMetaController",
    "StaticSkillComposer",
    "StructuralAnalogyEngine",
    "TableWorldModel",
    "WeightedObjective",
]
