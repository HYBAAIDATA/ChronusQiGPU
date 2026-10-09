"""Program-transformation domain specialists for the cognitive loop.

These adapters connect the generic cognition interfaces to the real v16
machinery: AST primitives, the process sandbox, the phi/fitness metrics and
the persistent primitive repository.  A "world state" here is program
structure (AST signature, invariants, test status); an "action" is an
operator application evaluated in the real sandbox; a "world model" learns
(signature, operator) -> measured fitness-delta distributions from genuine
search outcomes.
"""
from __future__ import annotations

import ast
import hashlib
import math
from collections import Counter, defaultdict
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from ..contracts import domain_hash
from ..core.phi_metric import PhiResonanceCalculator
from ..core.primitives import ASTPrimitives
from ..transfer.persistent_repository import PersistentPrimitiveRepository
from ..validation.process_sandbox import IsolatedProcessEvaluator
from .interfaces import Intervention, ModelHealth, StrategyChoice
from .state import (
    CandidateAction,
    CognitiveState,
    EvidenceItem,
    Hypothesis,
    PredictionRecord,
)


def program_signature(code: str) -> frozenset[str]:
    """Structural problem representation: relational AST features, not names.

    Features describe shape (node-type histogram buckets, depth band,
    control-flow presence), never identifier vocabulary, so structurally
    similar programs share signatures even when their text differs entirely.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return frozenset({"parse:invalid"})
    nodes = [type(n).__name__ for n in ast.walk(tree)]
    counts = Counter(nodes)
    features = {"parse:valid"}
    total = max(len(nodes), 1)
    for node_type in ("FunctionDef", "ClassDef", "For", "While", "If", "Assign",
                      "AnnAssign", "BinOp", "ListComp", "Return", "Call", "BoolOp"):
        bucket = min(counts.get(node_type, 0) * 10 // total, 9)
        features.add(f"rel:{node_type}:bucket-{bucket}")
        if counts.get(node_type, 0):
            features.add(f"rel:has-{node_type}")

    def depth(node: ast.AST, level: int = 0) -> int:
        children = list(ast.iter_child_nodes(node))
        if not children:
            return level
        return max(depth(child, level + 1) for child in children)

    features.add(f"rel:depth:band-{min(depth(tree) // 4, 4)}")
    return frozenset(features)


def signature_class(signature: frozenset[str]) -> str:
    """Problem-class identity for the meta-learner: a hash of structure only."""
    return "sig:" + domain_hash("euclid.cognition.signature.v1", sorted(signature))[:16]


class ProgramWorldModel:
    """Learned transition model over (signature, operator) -> fitness delta.

    Buckets measured deltas so prediction is a distribution over outcomes
    with an honest confidence (n / (n + prior)); unknown transitions answer
    "unknown" at prior_confidence rather than hallucinating a value.
    Persistable via to_dict/from_dict so the model survives restart.
    """

    SCHEMA = "euclid.cognition.world-model/1"

    def __init__(self, *, prior_confidence: float = 0.2, breakdown_error: float = 0.75,
                 window: int = 16) -> None:
        self.prior_confidence = prior_confidence
        self.breakdown_error = breakdown_error
        self.window = window
        self._table: Dict[str, Counter] = defaultdict(Counter)
        self._errors: List[float] = []
        self._sequence = 0

    @staticmethod
    def _bucket(delta: float) -> str:
        if delta > 0.005:
            return "improve"
        if delta < -0.005:
            return "regress"
        return "neutral"

    @staticmethod
    def _ctx(context: Any) -> str:
        return context if isinstance(context, str) else signature_class(context)

    def _key(self, context: Any, action: str) -> str:
        return self._ctx(context) + "|" + action

    def predict(self, context: frozenset[str], action: str) -> PredictionRecord:
        self._sequence += 1
        counts = self._table.get(self._key(context, action))
        if not counts:
            return PredictionRecord(
                f"wm-pred-{self._sequence}", signature_class(context), action,
                "unknown", self.prior_confidence, imagined=False,
            )
        outcome, hits = counts.most_common(1)[0]
        return PredictionRecord(
            f"wm-pred-{self._sequence}", signature_class(context), action,
            outcome, hits / sum(counts.values()), imagined=False,
        )

    def expected_gain(self, signature: frozenset[str], action: str) -> Optional[float]:
        """Signed prior estimate for search guidance, or None if unknown.

        Returns the measured transition-balance fraction
        (improve - regress) / total for this (signature, action) pair — a real
        quantity over recorded buckets on the same scale as the surrogate's
        Born expectation.  No rescaling is applied: the old ``score * 0.05``
        shrinkage was an invented constant, not a measurement.
        """
        counts = self._table.get(self._key(signature, action))
        if not counts:
            return None
        total = sum(counts.values())
        score = (counts.get("improve", 0) - counts.get("regress", 0)) / total
        return round(score, 6)

    def rollout(self, context: frozenset[str], actions: Sequence[str]) -> list[PredictionRecord]:
        predictions = []
        for action in actions:
            predicted = self.predict(context, action)
            predictions.append(PredictionRecord(
                predicted.prediction_id + "-imagined", predicted.context, action,
                predicted.expected, predicted.confidence, imagined=True,
            ))
        return predictions

    def observe_gain(self, signature: frozenset[str], action: str, delta: float) -> float:
        """Ingest one measured transition; return absolute bucket error."""
        expected = self.predict(signature, action).expected
        observed = self._bucket(delta)
        error = 0.0 if expected == observed else 1.0
        self._table[self._key(signature, action)][observed] += 1
        self._errors.append(error)
        return error

    # interface alias used by the core loop
    def update(self, context: frozenset[str], action: str, observed: str) -> float:
        expected = self.predict(context, action).expected
        error = 0.0 if expected == observed else 1.0
        self._table[self._key(context, action)][observed] += 1
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

    def to_dict(self) -> dict[str, Any]:
        body = {
            "schema": self.SCHEMA,
            "table": {key: dict(counts) for key, counts in sorted(self._table.items())},
            "errors": self._errors[-self.window:],
            "sequence": self._sequence,
        }
        return {**body, "seal": domain_hash("euclid.cognition.world-model.seal.v1", body)}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ProgramWorldModel":
        body = {key: payload.get(key) for key in ("schema", "table", "errors", "sequence")}
        if body["schema"] != cls.SCHEMA:
            raise ValueError("unsupported world-model schema")
        if payload.get("seal") != domain_hash("euclid.cognition.world-model.seal.v1", body):
            raise ValueError("world-model seal mismatch")
        model = cls()
        model._table = defaultdict(Counter, {
            key: Counter(value) for key, value in dict(body["table"] or {}).items()
        })
        model._errors = [float(e) for e in body["errors"] or []]
        model._sequence = int(body["sequence"] or 0)
        return model


class ProgramAbducer:
    """Generates competing causal explanations for a program's fitness state.

    Each hypothesis names a mechanism ("operator X will improve measured
    fitness because structure S is present"), carries explicit assumptions,
    a predicted observation (the delta bucket of applying X), and a falsifier
    (applying X in the sandbox does not produce the predicted bucket).
    """

    def __init__(self, operators: Sequence[str] | None = None) -> None:
        self.operators = list(operators) if operators else [
            name for name, _ in ASTPrimitives.get_all_operators()
        ]

    def hypothesise(
        self, observations: Sequence[EvidenceItem], state: CognitiveState
    ) -> list[Hypothesis]:
        applicable = self._applicable(state)
        hypotheses = [
            Hypothesis(
                hypothesis_id=f"op-helps:{op}",
                statement=(
                    f"applying {op} improves measured multi-objective fitness "
                    "for this structural class"
                ),
                provenance="program-abducer:operator-mechanism",
                confidence=1.0 / (len(applicable) + 1),
            )
            for op in applicable
        ]
        # The null hypothesis competes on equal footing: no operator helps.
        hypotheses.append(Hypothesis(
            "no-improvement-available",
            "no operator in the current vocabulary improves measured fitness here",
            provenance="program-abducer:null-hypothesis",
            confidence=1.0 / (len(applicable) + 1),
        ))
        return hypotheses

    def _applicable(self, state: CognitiveState) -> list[str]:
        structure = set(state.representation.get("structure", ()))
        applicable = []
        for op in self.operators:
            if op == "ADD:AnnAssign" and "rel:has-AnnAssign" in structure:
                continue  # already annotated; mechanism implausible
            if op == "NON_LOCAL:conditional_flattening" and "rel:has-If" not in structure:
                continue
            if op == "MUTATE:list_comp" and "rel:has-For" not in structure:
                continue
            if op == "NON_LOCAL:class_decomposition" and "rel:has-FunctionDef" not in structure:
                continue
            applicable.append(op)
        return applicable[:4] or self.operators[:2]


class ProgramDeducer:
    """Derives each hypothesis's predicted observation via the world model."""

    def __init__(self, operators: Sequence[str] | None = None) -> None:
        self.operators = list(operators) if operators else [
            name for name, _ in ASTPrimitives.get_all_operators()
        ]

    def consequences(
        self, hypothesis: Hypothesis, world_model: ProgramWorldModel, context: frozenset[str]
    ) -> list[PredictionRecord]:
        if hypothesis.hypothesis_id == "no-improvement-available":
            return [
                PredictionRecord(
                    f"ded-null-{op}", signature_class(context), op, "neutral",
                    hypothesis.confidence, imagined=False,
                )
                for op in self.operators[:3]
            ]
        op = hypothesis.hypothesis_id.split(":", 1)[1]
        prediction = world_model.predict(context, op)
        # A hypothesis asserts improvement even when the model is ignorant.
        return [PredictionRecord(
            f"ded-{hypothesis.hypothesis_id}", signature_class(context), op,
            "improve" if prediction.expected == "unknown" else prediction.expected,
            max(hypothesis.confidence, prediction.confidence), imagined=False,
        )]


class DivergenceDiscriminator:
    """Picks the operator probe that maximally separates active hypotheses."""

    def discriminate(
        self,
        hypotheses: Sequence[Hypothesis],
        predictions: Mapping[str, Sequence[PredictionRecord]],
    ) -> Intervention | None:
        active = [h for h in hypotheses]
        if len(active) < 2:
            return None
        by_action: Dict[str, set] = {}
        for hypothesis in active:
            for prediction in predictions.get(hypothesis.hypothesis_id, ()):
                by_action.setdefault(prediction.action, set()).add(prediction.expected)
        best_action, best_div = None, 1
        for action in sorted(by_action):
            if len(by_action[action]) > best_div:
                best_action, best_div = action, len(by_action[action])
        if best_action is None:
            return None
        return Intervention(
            best_action, float(best_div),
            f"probe '{best_action}' separates {best_div} predicted outcome classes "
            f"across {len(active)} active hypotheses",
        )


class ProgramSkillComposer:
    """Composes candidate actions from the base operator vocabulary and the
    persistent repository (promoted primitives carry their measured record)."""

    def __init__(
        self,
        repository: PersistentPrimitiveRepository | None = None,
        *,
        correctness_prior: float = 0.5,
        base_op_cost: float = 1.0,
        prior_uncertainty: float = 0.5,
        reuse_uncertainty_decay: float = 0.1,
        reuse_uncertainty_floor: float = 0.1,
        reuse_transfer_scale: float = 0.2,
        correctness_cap: float = 0.9,
    ) -> None:
        """All coefficients are a DECLARED feature-mapping policy applied to
        measured repository statistics (cumulative_delta_phi, reuse count);
        none are presented as measured quantities."""
        self.repository = repository
        self.correctness_prior = float(correctness_prior)
        self.base_op_cost = float(base_op_cost)
        self.prior_uncertainty = float(prior_uncertainty)
        self.reuse_uncertainty_decay = float(reuse_uncertainty_decay)
        self.reuse_uncertainty_floor = float(reuse_uncertainty_floor)
        self.reuse_transfer_scale = float(reuse_transfer_scale)
        self.correctness_cap = float(correctness_cap)

    def compose(self, goal: str, state: CognitiveState) -> list[CandidateAction]:
        candidates = []
        for name, _ in ASTPrimitives.get_all_operators():
            candidates.append(CandidateAction(
                f"op:{name}", f"apply {name}", origin="primitive:base",
                features={"correctness_estimate": self.correctness_prior,
                          "cost": self.base_op_cost,
                          "uncertainty": self.prior_uncertainty,
                          "novelty": 0.0, "transfer_value": 0.0},
            ))
        if self.repository is not None:
            for name, meta in self.repository.repository.items():
                # measured repository statistics mapped through the declared
                # policy coefficients above
                gain = float(meta.get("cumulative_delta_phi", 0.0))
                reuse = len(meta.get("targets_reused_on", []))
                candidates.append(CandidateAction(
                    f"op:{name}", f"apply promoted {name}", origin="primitive:repository",
                    features={
                        "correctness_estimate": min(
                            self.correctness_cap, self.correctness_prior + gain
                        ),
                        "cost": self.base_op_cost,
                        "uncertainty": max(
                            self.reuse_uncertainty_floor,
                            self.prior_uncertainty
                            - self.reuse_uncertainty_decay * reuse,
                        ),
                        "novelty": 0.0,
                        "transfer_value": min(1.0, self.reuse_transfer_scale * reuse),
                    },
                ))
        return candidates


__all__ = [
    "DivergenceDiscriminator",
    "ProgramAbducer",
    "ProgramDeducer",
    "ProgramSkillComposer",
    "ProgramWorldModel",
    "program_signature",
    "signature_class",
]
