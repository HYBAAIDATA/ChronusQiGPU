"""Production adapters joining repository intelligence to the cognition loop.

Adapters translate the canonical cognitive envelope; they do not move domain
authority into EUCLID.  TOE owns causal/world modelling and planning, v16 owns
program search/primitives, PYTHIA owns its memory/learning stack, and governed
organs own execution.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from dataclasses import replace
from enum import Enum
from typing import Any, Mapping, Sequence

from kellogg.quantum_tensor import QuantumState

from euclid.contracts import Experience, RewardAuthority, domain_hash
from euclid.memory_database import MemoryDatabase, MemoryScope
from toe.meta_reasoning import ACT_NOW, meta_decide
from toe.planning import OperatorSpec, plan
from toe.policy import Objective
from toe.world_model import OnlineAdapter, WorldModel as TOEWorldModel

from .baselines import SignalMetaController
from .interfaces import ControlAssessment, MemoryItem, ModelHealth
from .state import CandidateAction, CognitiveState, MemoryKind, PlanNode, PredictionRecord


# Declared symmetric pseudo-count mass for the outcome state used to measure
# prediction confidence.
OUTCOME_PRIOR_MASS = 1.0

# Declared normalisation reference for measured evaluation counts in the
# candidate-cost feature.
SEARCH_COST_REFERENCE = 100.0

# Declared ignorant-prior feature vector for unproven base operators.
PRIMITIVE_PRIOR_FEATURES = {
    "correctness_estimate": 0.5,
    "cost": 0.2,
    "uncertainty": 0.5,
    "novelty": 0.2,
    "transfer_value": 0.2,
}


def _number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        digest = hashlib.sha256(str(value).encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") / float(2**64)


class TOEWorldModelAdapter:
    """Cognition WorldModel backed by TOE's revision-capable causal model."""

    def __init__(self, model: TOEWorldModel | None = None) -> None:
        if model is None:
            model = TOEWorldModel(
                nodes=(
                    "context",
                    "context_sq",
                    "action",
                    "action_sq",
                    "context_action",
                    "outcome",
                ),
                edges=(
                    ("context", "outcome"),
                    ("context_sq", "outcome"),
                    ("action", "outcome"),
                    ("action_sq", "outcome"),
                    ("context_action", "outcome"),
                ),
                actions={"act": "action"},
            )
            # Preserve the previous linear cold-start prediction exactly.
            # Non-linear features earn influence only through observed updates.
            for feature in ("context_sq", "action_sq", "context_action"):
                model.dynamics["outcome"][feature] = 0.0
        self.model = model
        self.feature_augmented = all(
            feature in self.model.nodes
            for feature in ("context_sq", "action_sq", "context_action")
        )
        self.online = OnlineAdapter(self.model)
        self._states: dict[str, dict[str, float]] = {}
        self._sequence = 0

    def _features(self, context: str, action: float) -> dict[str, float]:
        context_value = _number(context)
        values = {
            "context": context_value,
            "action": float(action),
        }
        if self.feature_augmented:
            values.update(
                {
                    "context_sq": context_value * context_value,
                    "action_sq": float(action) * float(action),
                    "context_action": context_value * float(action),
                }
            )
        return values

    def _state(self, context: str) -> dict[str, float]:
        return self._states.setdefault(
            context, {**self._features(context, 0.0), "outcome": 0.0}
        )

    def _action_features(self, context: str, action: str) -> dict[str, float]:
        values = self._features(context, _number(action))
        return {key: value for key, value in values.items() if key != "context"}

    def _prediction(self, context: str, action: str, imagined: bool) -> PredictionRecord:
        self._sequence += 1
        future = self.model.predict_transition(
            self._state(context), self._action_features(context, action)
        )
        return PredictionRecord(
            f"toe-pred-{self._sequence}",
            context,
            action,
            format(float(future["outcome"]), ".12g"),
            self._outcome_confidence(),
            imagined,
        )

    def _outcome_confidence(self) -> float:
        """Born-rule confidence over the measured outcome record.

        Prepares the outcome state  |psi> ~ sum_o sqrt(n_o)|o> + sqrt(prior)|?>
        from the model's observed transitions; confidence is the largest Born
        probability (modal-outcome mass under the declared symmetric prior).
        With no observations the honest answer is 0.0 — no evidence.
        """
        counts = Counter(
            str(record.get("outcome")) for record in self.model.outcomes
        )
        if not counts:
            return 0.0
        amplitudes = [math.sqrt(c) for c in counts.values()]
        amplitudes.append(math.sqrt(OUTCOME_PRIOR_MASS))
        state = QuantumState.from_real_vector(amplitudes)
        return float(max(state.probabilities()))

    def predict(self, context: str, action: str) -> PredictionRecord:
        return self._prediction(context, action, False)

    def rollout(self, context: str, actions: Sequence[str]) -> list[PredictionRecord]:
        return [self._prediction(context, action, True) for action in actions]

    def counterfactual(self, context: str, actions: Sequence[str]) -> list[dict[str, Any]]:
        factual = self._state(context)
        return [
            {
                "action": action,
                "future": self.model.predict_transition(
                    factual,
                    (
                        {}
                        if action == "no-intervention"
                        else self._action_features(context, action)
                    ),
                ),
                "epistemic_status": "predicted",
                "imagined": True,
            }
            for action in actions
        ]

    def update(self, context: str, action: str, observed: str) -> float:
        previous = dict(self._state(context))
        action_features = self._action_features(context, action)
        nxt = dict(previous)
        nxt.update(action_features)
        nxt["outcome"] = _number(observed)
        result = self.online.step(previous, action_features, nxt)
        self._states[context] = nxt
        return float(result["error"])

    def health(self) -> ModelHealth:
        assessment = self.model.assess()
        status = str(assessment["status"])
        mapped = (
            "healthy"
            if status == "MODEL_SUPPORTED"
            else "breakdown" if status == "MODEL_CONTRADICTED" else "degraded"
        )
        return ModelHealth(mapped, float(assessment.get("mean_abs_error", 0.0)), status)


class DurableCognitiveMemory:
    """One logical cognition memory over the canonical durable database."""

    _TIER = {
        MemoryKind.EPISODIC: "episodic",
        MemoryKind.SEMANTIC: "semantic",
        MemoryKind.PROCEDURAL: "semantic",
        MemoryKind.PRIMITIVE: "semantic",
        MemoryKind.SKILL: "semantic",
        MemoryKind.STRATEGY: "semantic",
        MemoryKind.CAUSAL: "semantic",
    }

    def __init__(self, database: MemoryDatabase, *, creator_id: str) -> None:
        self.database = database
        self.scope = MemoryScope(creator_id, "euclid-cognition", "repository")

    def retrieve(
        self,
        structural_features: frozenset[str],
        kinds: Sequence[MemoryKind] | None = None,
    ) -> list[MemoryItem]:
        allowed = set(kinds or tuple(MemoryKind))
        records = self.database.query(scope=self.scope, limit=500)
        items: list[MemoryItem] = []
        for record in records:
            raw_kind = str(record.content.get("kind", MemoryKind.EPISODIC.value))
            try:
                kind = MemoryKind(raw_kind)
            except ValueError:
                continue
            if kind not in allowed:
                continue
            features = frozenset(map(str, record.content.get("structural_features", ())))
            overlap = len(features & structural_features) / max(
                1, len(features | structural_features)
            )
            items.append(
                MemoryItem(
                    record.memory_id,
                    kind,
                    dict(record.content.get("payload", {})),
                    record.provenance,
                    features,
                    overlap,
                )
            )
        return sorted(items, key=lambda item: (-item.transfer_value, item.memory_id))

    def store(self, item: MemoryItem) -> None:
        self.database.put(
            scope=self.scope,
            tier=self._TIER[item.kind],
            content={
                "kind": item.kind.value,
                "payload": dict(item.payload),
                "structural_features": sorted(item.structural_features),
                "transfer_value": item.transfer_value,
            },
            provenance=item.provenance,
            reward_authority=RewardAuthority.NONE,
            uncertainty=max(0.0, min(1.0, 1.0 - item.transfer_value)),
            replay_id="cognitive-memory:" + item.memory_id,
            memory_id=item.memory_id,
        )

    def deprecate(self, memory_id: str, rationale: str) -> None:
        self.database.tombstone(memory_id, scope=self.scope, reason=rationale)


class TOECognitivePlanner:
    """Planner using TOE's bounded operator search and declared costs."""

    def plan(self, goal: str, state: CognitiveState) -> list[PlanNode]:
        # Declared default operator spec (policy definition of the planning
        # problem when the state carries none); levels/costs are declared, not
        # measured.
        specs = state.representation.get("operators") or [
            {"name": "inspect", "node": "progress", "levels": (0.4,), "cost": 0.2},
            {"name": "test", "node": "progress", "levels": (0.8,), "cost": 0.4},
            {"name": "verify", "node": "progress", "levels": (1.0,), "cost": 0.3},
        ]
        operators = [
            OperatorSpec(
                str(spec["name"]),
                str(spec.get("node", "progress")),
                tuple(map(float, spec.get("levels", ()))),
                tuple(map(float, spec.get("deltas", ()))),
                float(spec.get("cost", 1.0)),
            )
            for spec in specs
        ]

        def environment(interventions: Mapping[str, float]) -> dict[str, float]:
            return {"progress": max(interventions.values(), default=0.0)}

        result = plan(
            environment,
            operators,
            objective=Objective("progress"),
            depth=int(state.representation.get("plan_depth", 3)),
            budget=float(state.representation.get("budget", 2.0)),
        )
        if not result.get("available"):
            return [PlanNode("toe-unavailable", f"TOE plan unavailable: {result['reason']}")]
        return [
            PlanNode(
                f"toe-{index}",
                str(step["name"]),
                skill_ref="toe.planning",
                children=((f"toe-{index + 1}",) if index + 1 < len(result["sequence"]) else ()),
            )
            for index, step in enumerate(result["sequence"])
        ]

    def replan(
        self, goal: str, state: CognitiveState, failure: Mapping[str, Any]
    ) -> list[PlanNode]:
        state.representation["plan_depth"] = min(
            8, int(state.representation.get("plan_depth", 3)) + 1
        )
        return self.plan(goal, state)


class TOEMetaController:
    """TOE evidence/VOI routing plus the measured stage-1 error controller."""

    def __init__(self) -> None:
        self.fallback = SignalMetaController()

    def assess(self, state: CognitiveState) -> ControlAssessment:
        margin = None
        if len(state.candidates) > 1:
            totals = [c.total for c in state.candidates[:2]]
            if all(value is not None for value in totals):
                margin = float(totals[0]) - float(totals[1])
        decision = meta_decide(
            decision_margin=margin,
            evidence_count=len(state.evidence_items),
            available_operators=tuple(state.alternative_strategies)
            + ((state.selected_strategy,) if state.selected_strategy else ()),
        )
        if decision["recommendation"] != ACT_NOW:
            return ControlAssessment(
                "replan",
                str(decision["reason"]),
                {"toe_evidence_count": float(len(state.evidence_items))},
            )
        fallback = self.fallback.assess(state)
        return replace(fallback, rationale=f"TOE: {decision['reason']} | {fallback.rationale}")


class V16SkillSearchAdapter:
    """EUCLID-v16 MCTS/evolution and AST primitives as cognitive strategies."""

    def __init__(self, *, repository: Any | None = None) -> None:
        from euclid.core.primitives import ASTPrimitives
        from euclid.search.evolutionary_search import EvolutionarySearchEngine
        from euclid.search.mcts_search import MCTSSearchEngine

        self.primitives = ASTPrimitives
        self.mcts = MCTSSearchEngine(repository=repository)
        self.evolution = EvolutionarySearchEngine(repository=repository)
        self.calls: list[str] = []
        self.mathematical_enabled = True

    def available_strategies(self) -> tuple[str, ...]:
        # Order is the declared default when no per-class evidence exists:
        # primitive-compose preserves the cold-start baseline; measured
        # success must promote a search arm.
        return ("primitive-compose", "mcts-v16", "evolution-v16", "toe-plan")

    def compose(self, goal: str, state: CognitiveState) -> list[CandidateAction]:
        code = str(state.representation.get("initial_code", "def candidate(x):\n    return x\n"))
        # A problem-requested strategy is an explicit pin on which search
        # skill composes candidates; it takes precedence over the learned
        # strategy selection and must name a real portfolio entry.
        requested = state.representation.get("strategy") or state.representation.get(
            "requested_strategy"
        )
        if requested is not None and str(requested) not in self.available_strategies():
            raise ValueError(f"unknown skill-search strategy {requested!r}")
        strategy = str(requested) if requested else (
            state.selected_strategy or "primitive-compose"
        )
        if not self.mathematical_enabled and strategy in {"mcts-v16", "evolution-v16"}:
            self.calls.append("neutral-primitive-ablation")
            strategy = "primitive-compose"
        if strategy == "mcts-v16":
            self.calls.append(strategy)
            result = self.mcts.run_mcts_search(
                state.problem_id, code, max_generations=1, num_simulations_per_gen=2
            )
            return [self._candidate("mcts", result)]
        if strategy == "evolution-v16":
            self.calls.append(strategy)
            result = self.evolution.run_optimization(state.problem_id, code, max_generations=1)
            return [self._candidate("evolution", result)]
        self.calls.append("primitive-compose")
        return [
            CandidateAction(
                f"primitive:{name}",
                f"apply verified AST primitive {name}",
                origin="euclid-v16:ASTPrimitives",
                # declared ignorant-prior features (not measured): the base
                # operator vocabulary carries no per-operator evidence here
                features=dict(PRIMITIVE_PRIOR_FEATURES),
            )
            for name, _ in self.primitives.get_all_operators()
        ]

    @staticmethod
    def _candidate(kind: str, result: Mapping[str, Any]) -> CandidateAction:
        delta = float(result.get("total_delta_phi", 0.0))
        attempted = float(result.get("total_evals_attempted", 0))
        valid = float(result.get("total_evals_valid", 0))
        return CandidateAction(
            f"search:{kind}",
            f"{kind} produced measured candidate",
            origin=f"euclid-v16:{kind}",
            features={
                "correctness_estimate": 1.0 if valid else 0.0,
                # measured evaluation count, declared normalisation scale
                "cost": min(1.0, attempted / SEARCH_COST_REFERENCE),
                # measured uncertainty: fraction of attempted evaluations that
                # failed the sandbox (0.0 = every evaluation valid)
                "uncertainty": 1.0 - (valid / attempted) if attempted else 1.0,
                "novelty": max(0.0, delta),
                "transfer_value": min(1.0, max(0.0, delta)),
            },
        )


class TaskVerificationVerdict(str, Enum):
    UNAVAILABLE = "unavailable"
    VERIFIED_FAILURE = "verified_failure"
    VERIFIED_SUCCESS = "verified_success"
    UNVERIFIED = "unverified"


def verify_task_evidence(
    action: str,
    payload: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> tuple[bool, TaskVerificationVerdict]:
    if not evidence:
        return False, TaskVerificationVerdict.UNAVAILABLE

    # If focused_tests evidence is present, evaluate execution result
    if "focused_tests" in evidence:
        tests = evidence["focused_tests"]
        if isinstance(tests, dict):
            if tests.get("available") is False:
                return False, TaskVerificationVerdict.UNAVAILABLE
            if "returncode" in tests:
                rc = tests["returncode"]
                if rc == 0:
                    return True, TaskVerificationVerdict.VERIFIED_SUCCESS
                return False, TaskVerificationVerdict.VERIFIED_FAILURE

    # If import_audit evidence is present
    if "import_audit" in evidence:
        audit = evidence["import_audit"]
        action_str = str(action).lower()
        goal_str = str(payload.get("goal", "")).lower()
        is_audit_task = "audit" in action_str or "audit" in goal_str
        if is_audit_task:
            if isinstance(audit, dict):
                findings = audit.get("finding_count")
                if findings == 0:
                    return True, TaskVerificationVerdict.VERIFIED_SUCCESS
                return False, TaskVerificationVerdict.VERIFIED_FAILURE
        else:
            return False, TaskVerificationVerdict.UNVERIFIED

    return False, TaskVerificationVerdict.UNAVAILABLE


class RepositoryIntelligenceExecutor:
    """Read-only repository organ; source mutation remains outside cognition."""

    def __init__(self, engineer: Any) -> None:
        self.engineer = engineer
        self.results: list[dict[str, Any]] = []

    def execute(self, action: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        report = dict(
            self.engineer.ask(
                f"Investigate repository action {action}; inspect wiring, dependencies, "
                "relevant skills and focused evidence. Do not modify source."
            )
        )
        evidence = report.get("evidence", {})
        findings = evidence.get("import_audit", {}).get("finding_count")
        summary = json.dumps(
            {"routes": report.get("routes", ()), "finding_count": findings},
            sort_keys=True,
        )
        observation = summary
        if payload.get("kind") == "intervention":
            observation = self.intervention_observation(str(action), evidence)
        goal_met, verdict = verify_task_evidence(action, payload, evidence)
        result = {
            "observation": observation,
            "evidence_summary": summary,
            "goal_met": goal_met,
            "verification_verdict": verdict.value,
            "task_id": report.get("task_id"),
            "governed": True,
            "mutation_performed": False,
        }
        self.results.append(result)
        return result

    @staticmethod
    def intervention_observation(action: str, evidence: Mapping[str, Any]) -> str:
        """Project measured RepoEngineer evidence onto the declared explanation
        tokens so a discriminating intervention can confirm or refute the
        competing hypotheses.  Missing evidence is ``unobserved`` (which
        refutes every hypothesis and aborts fail-closed), never a guess."""
        if action == "inspect":
            findings = evidence.get("import_audit", {}).get("finding_count")
            if findings is None:
                return "unobserved"
            return "dependency-evidence" if int(findings) > 0 else "source-evidence"
        if action == "test":
            tests = evidence.get("focused_tests", {})
            return "test-evidence" if "returncode" in tests else "unobserved"
        return "unobserved"


def _last_executed_action(state: CognitiveState) -> str | None:
    """The action id that last crossed the governed execution boundary."""
    for item in reversed(state.evidence_items):
        if item.evidence_id.startswith("exec-"):
            action = item.content.get("action")
            return str(action) if action else None
    return None


class LearningServiceEpisodeAdapter:
    """Close observed cognition outcomes into the canonical LearningService."""

    def __init__(self, service: Any, memory: DurableCognitiveMemory | None = None) -> None:
        self.service = service
        self.memory = memory

    def record_episode(
        self,
        state: CognitiveState,
        *,
        success: bool,
        cycle: int,
        result: Mapping[str, Any],
        channel: str = "submission",
    ) -> str:
        # Replay identity is derived from the *recorded content* of the
        # episode, never from wall-clock transition timestamps: an identical
        # replay must collide (fail closed) while distinct episodes must not.
        # ``channel`` separates the automatic in-solve episode closure
        # (``"consolidation"``) from explicit operator submissions
        # (``"submission"``): each is a different record of the episode, so a
        # submission made after a solve is not a replay of the closure, while
        # resubmitting the same record on the same channel still fails closed.
        replay_id = domain_hash(
            "euclid.cognition.replay.v1",
            {
                "problem_id": state.problem_id,
                "cycle": int(cycle),
                "strategy": state.selected_strategy,
                "action": (state.candidates[0].action_id if state.candidates else None),
                "success": bool(success),
                "result": dict(result),
                "evidence_ids": [item.evidence_id for item in state.evidence_items],
                "channel": channel,
            },
        )
        reward_authority = RewardAuthority.NONE
        reward = None
        if result.get("reward_authority") == RewardAuthority.MEASURED_ENVIRONMENT.value:
            reward_authority = RewardAuthority.MEASURED_ENVIRONMENT
            reward = float(result["reward"])
        experience = Experience(
            experience_id="cognition-"
            + domain_hash("euclid.cognition.experience-id.v1", {"replay_id": replay_id})[:32],
            mission_id=state.problem_id,
            domain=str(state.representation.get("problem_class", "repository")),
            source="euclid.cognition",
            observation={
                "representation": state.representation,
                "evidence_ids": [item.evidence_id for item in state.evidence_items],
                "prediction_errors": list(state.prediction_errors),
            },
            action=state.candidates[0].action_id if state.candidates else "no-action",
            outcome={
                "success": success,
                "cycle": cycle,
                "result": dict(result),
                "strategy": state.selected_strategy,
            },
            reward=reward,
            reward_authority=reward_authority,
            provenance=f"cognitive-episode:{state.problem_id}",
            uncertainty=max(0.0, min(1.0, max(state.prediction_errors[-1:], default=0.0))),
            replay_id=replay_id,
            created_at=float(cycle),
        )
        digest = self.service.record(experience)
        if self.memory is not None:
            self.memory.store(
                MemoryItem(
                    "episode-" + digest[:24],
                    MemoryKind.EPISODIC,
                    {
                        "problem_id": state.problem_id,
                        "strategy": state.selected_strategy,
                        "executed_action": _last_executed_action(state),
                        "success": success,
                        "result": dict(result),
                    },
                    f"learning-service:{digest}",
                    frozenset(map(str, state.representation.get("structure", ()))),
                    1.0 if success else 0.25,
                )
            )
        state.learning_updates.append(
            {
                "kind": "canonical-learning-service",
                "digest": digest,
                "cycle": cycle,
                "success": bool(success),
                "counts_for_control": False,
            }
        )
        return digest


__all__ = [
    "DurableCognitiveMemory",
    "LearningServiceEpisodeAdapter",
    "RepositoryIntelligenceExecutor",
    "TOECognitivePlanner",
    "TOEMetaController",
    "TOEWorldModelAdapter",
    "TaskVerificationVerdict",
    "V16SkillSearchAdapter",
    "verify_task_evidence",
]
