"""GeneralIntelligenceCore: orchestration of the primary intelligence loop.

The core is deliberately *not* a god object.  It owns no specialist
implementation; it drives injected :mod:`euclid.cognition.interfaces`
implementations through a fixed, inspectable cycle and records every
transition into both the :class:`CognitiveState` ledger and the shared
:class:`~euclid.evidence.EvidenceChain`.

Terminal states are explicit (``solved`` / ``stalled`` / ``aborted`` /
``unexecuted``); there is no opaque "intelligence succeeded" state.

Execution is fail-closed: without an injected :class:`Executor` the loop
plans and evaluates but never acts, and says so in the outcome.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, replace
from typing import Any, Callable, Mapping, Sequence

from ..evidence import EvidenceChain
from .interfaces import (
    Abducer,
    AnalogyEngine,
    CausalDiscriminator,
    Deducer,
    Executor,
    MemorySystem,
    MetaController,
    MetaLearner,
    ObjectiveFunction,
    Planner,
    SkillComposer,
    WorldModel,
)
from .state import (
    AnalogyStatus,
    CandidateAction,
    CognitiveState,
    EpistemicStatus,
    EvidenceItem,
    EvidenceOrigin,
    Goal,
    HypothesisStatus,
    MemoryKind,
    Outcome,
)

ALL_MEMORY_KINDS = tuple(MemoryKind)
EVIDENCE_PREFIX = "cognition-"


@dataclass(frozen=True)
class AblationConfig:
    """Surgical removal of mechanisms for emergence/falsification studies.

    Every ablation is recorded on the state and in the evidence chain so an
    ablated run can never masquerade as a full-system run.
    """

    world_model: bool = True
    analogy: bool = True
    causal_reasoning: bool = True
    meta_learning: bool = True
    skill_composition: bool = True
    replanning: bool = True
    representation_restructuring: bool = True
    mathematical_structure: bool = True


class GeneralIntelligenceCore:
    def __init__(
        self,
        *,
        world_model: WorldModel,
        memory: MemorySystem,
        analogy: AnalogyEngine,
        abducer: Abducer,
        deducer: Deducer,
        discriminator: CausalDiscriminator,
        metacontroller: MetaController,
        metalearner: MetaLearner,
        planner: Planner,
        skills: SkillComposer,
        objective: ObjectiveFunction,
        executor: Executor | None = None,
        evidence: EvidenceChain | None = None,
        clock: Callable[[], float] = time.time,
        max_cycles: int = 8,
        ablations: AblationConfig | None = None,
        analogy_adopt_threshold: float = 0.5,
        episode_learner: Any | None = None,
        representation_controller: Any | None = None,
        objective_controller: Any | None = None,
    ) -> None:
        if max_cycles < 1:
            raise ValueError("max_cycles must be >= 1")
        if not 0.0 <= analogy_adopt_threshold <= 1.0:
            raise ValueError("analogy_adopt_threshold must be in [0,1]")
        self.world_model = world_model
        self.memory = memory
        self.analogy = analogy
        self.abducer = abducer
        self.deducer = deducer
        self.discriminator = discriminator
        self.metacontroller = metacontroller
        self.metalearner = metalearner
        self.planner = planner
        self.skills = skills
        self.objective = objective
        self.executor = executor
        self.evidence = evidence or EvidenceChain()
        self.clock = clock
        self.max_cycles = max_cycles
        self.ablations = ablations or AblationConfig()
        self.analogy_adopt_threshold = analogy_adopt_threshold
        # Optional production wiring (EuclidRuntime._compose_cognition).  Each
        # component is exercised only through measured, recorded signals; when
        # absent the loop behaves exactly as before.
        self.episode_learner = episode_learner
        self.representation_controller = representation_controller
        self.objective_controller = objective_controller

    # -- instrumentation ----------------------------------------------------
    def _transition(
        self, state: CognitiveState, phase: str, summary: str, details: Mapping[str, Any]
    ) -> None:
        record = state.record_transition(phase, summary, details)
        self.evidence.append(
            EVIDENCE_PREFIX + phase,
            {
                "problem_id": state.problem_id,
                "sequence": record.sequence,
                "summary": record.summary,
                "details": dict(details),
            },
        )

    def _ablated(self, state: CognitiveState, mechanism: str) -> None:
        state.ablations.append(mechanism)
        self._transition(
            state, "ablated", f"{mechanism} disabled for this episode", {"mechanism": mechanism}
        )

    # -- the loop -------------------------------------------------------------
    def solve(
        self,
        problem: Mapping[str, Any],
        *,
        goal: str | None = None,
        problem_class: str | None = None,
    ) -> CognitiveState:
        problem_id = str(problem.get("problem_id") or "").strip()
        if not problem_id:
            raise ValueError("problem requires a problem_id")
        goal_text = str(goal or problem.get("goal") or "").strip()
        if not goal_text:
            raise ValueError("a goal is required")
        structure = frozenset(str(s) for s in problem.get("structure", ()))
        observations = tuple(problem.get("observations", ()))
        problem_class = str(problem_class or problem.get("problem_class") or "unclassified")

        representation: dict[str, Any] = {
            "structure": sorted(structure),
            "problem_class": problem_class,
        }
        for key in (
            "initial_code", "operators", "plan_depth", "budget",
            "representation_kind", "state_vector", "surface", "observations",
            "context_key", "strategy",
        ):
            if key in problem:
                representation[key] = problem[key]
        state = CognitiveState(problem_id, representation, clock=self.clock)
        state.goals.append(Goal("g0", goal_text))

        # 1. REPRESENT -----------------------------------------------------
        representation_details: dict[str, Any] = {
            "structure": sorted(structure),
            "observation_count": len(observations),
        }
        if self.representation_controller is not None:
            if self.ablations.representation_restructuring:
                trial = self._select_representation(problem, structure)
                representation_details["representation_trial"] = {
                    "kind": trial.kind,
                    "accepted": trial.accepted,
                    "baseline_utility": trial.baseline_utility,
                    "candidate_utility": trial.candidate_utility,
                    "cost": trial.cost,
                    "rationale": trial.rationale,
                }
                if trial.accepted:
                    state.representation["representation_kind"] = trial.kind
                    state.representation["active_representation"] = trial.kind
                    state.representation["representation_overlay"] = dict(trial.payload)
                    # The overlay is provenance; canonical top-level fields are
                    # the executable representation consumed by planners/skills.
                    state.representation.update(dict(trial.payload))
            else:
                self._ablated(state, "representation_restructuring")
        self._transition(
            state,
            "represent",
            "problem representation formed",
            representation_details,
        )

        # 2. RETRIEVE --------------------------------------------------------
        memories = self.memory.retrieve(structure, ALL_MEMORY_KINDS)
        state.retrieved_memory_refs.extend(m.memory_id for m in memories)
        self._transition(
            state,
            "retrieve",
            "memory retrieved by structural relevance",
            {"retrieved": [m.memory_id for m in memories]},
        )

        # 3. ANALOGY ----------------------------------------------------------
        if self.ablations.analogy:
            surface = frozenset(str(s) for s in problem.get("surface", ()))
            analogies = self.analogy.find(structure, memories, surface)
            state.analogies.extend(analogies)
            adopted = [a for a in analogies if a.structural_overlap >= self.analogy_adopt_threshold]
            state.analogies[:] = [
                (
                    a
                    if a not in adopted
                    else type(a)(
                        a.analogy_id,
                        a.source_ref,
                        a.structural_overlap,
                        a.surface_overlap,
                        a.reliability,
                        AnalogyStatus.ADOPTED,
                        a.rationale + " | adopted: structural overlap above threshold",
                    )
                )
                for a in state.analogies
            ]
            self._transition(
                state,
                "analogy",
                "structural analogies evaluated",
                {
                    "candidates": [a.analogy_id for a in state.analogies],
                    "adopted": [
                        a.analogy_id for a in state.analogies if a.status is AnalogyStatus.ADOPTED
                    ],
                    "rejected": [
                        a.analogy_id for a in state.analogies if a.status is AnalogyStatus.REJECTED
                    ],
                },
            )
        else:
            self._ablated(state, "analogy")

        # seed observed evidence
        for index, observation in enumerate(observations):
            state.add_evidence(
                EvidenceItem(
                    f"obs-{index}",
                    EvidenceOrigin.OBSERVED,
                    EpistemicStatus.KNOWN,
                    {"observation": str(observation)},
                    source="problem-statement",
                    uncertainty=0.0,
                )
            )

        context = str(problem.get("context_key") or problem_id)
        solved = False
        executed_once = False
        for cycle in range(self.max_cycles):
            self._transition(state, "cycle", f"reasoning cycle {cycle} opened", {"cycle": cycle})

            # 4. ABDUCE -----------------------------------------------------
            hypotheses = self.abducer.hypothesise(state.evidence_items, state)
            if len(hypotheses) < 2:
                self._transition(
                    state,
                    "abduce",
                    "abducer returned a single hypothesis; uncertainty retained",
                    {
                        "hypotheses": [h.hypothesis_id for h in hypotheses],
                        "warning": "no competition",
                    },
                )
            else:
                self._transition(
                    state,
                    "abduce",
                    "competing hypotheses generated",
                    {"hypotheses": [h.hypothesis_id for h in hypotheses]},
                )
            for hypothesis in hypotheses:
                if all(h.hypothesis_id != hypothesis.hypothesis_id for h in state.hypotheses):
                    state.hypotheses.append(hypothesis)

            # 5. DEDUCE ------------------------------------------------------
            predictions_by_hypothesis: dict[str, Sequence] = {}
            if self.ablations.world_model:
                for hypothesis in state.active_hypotheses():
                    predictions = self.deducer.consequences(hypothesis, self.world_model, context)
                    predictions_by_hypothesis[hypothesis.hypothesis_id] = predictions
                    state.predictions.extend(predictions)
                self._transition(
                    state,
                    "deduce",
                    "consequences derived per hypothesis",
                    {
                        key: [p.prediction_id for p in value]
                        for key, value in predictions_by_hypothesis.items()
                    },
                )
            else:
                self._ablated(state, "world_model:deduction")

            # 6. CAUSAL DISCRIMINATION ---------------------------------------
            if self.ablations.causal_reasoning and predictions_by_hypothesis:
                intervention = self.discriminator.discriminate(
                    state.active_hypotheses(), predictions_by_hypothesis
                )
                if intervention is None:
                    self._transition(
                        state,
                        "discriminate",
                        "no discriminating intervention available; alternatives retained",
                        {},
                    )
                else:
                    self._transition(
                        state,
                        "discriminate",
                        "discriminating intervention selected",
                        {
                            "action": intervention.action,
                            "expected_divergence": intervention.expected_divergence,
                            "rationale": intervention.rationale,
                        },
                    )
                    if self.executor is not None:
                        observed = self.executor.execute(
                            intervention.action, {"kind": "intervention", "cycle": cycle}
                        )
                        executed_once = True
                        self._compare_hypotheses(
                            state, intervention.action, observed, predictions_by_hypothesis
                        )
            elif not self.ablations.causal_reasoning:
                self._ablated(state, "causal_reasoning")

            # 7. STRATEGY SELECTION --------------------------------------------
            available_strategies = tuple(
                getattr(
                    self.skills,
                    "available_strategies",
                    lambda: (
                        "analogy-causal-plan",
                        "abduce-intervene-deduce",
                        "rollout-search-execute",
                    ),
                )()
            )
            if self.ablations.meta_learning:
                choice = self.metalearner.select_strategy(problem_class, available_strategies)
                state.selected_strategy = choice.strategy_id
                state.alternative_strategies = list(choice.alternatives)
                self._transition(
                    state,
                    "strategy",
                    "reasoning strategy selected",
                    {
                        "selected": choice.strategy_id,
                        "alternatives": list(choice.alternatives),
                        "basis": choice.basis,
                    },
                )
            else:
                state.selected_strategy = available_strategies[0]
                state.alternative_strategies = list(available_strategies[1:])
                self._ablated(state, "meta_learning")

            # 8. PLAN ------------------------------------------------------------
            planning_goal = goal_text
            active_objectives = list(state.representation.get("active_objectives", ()))
            if active_objectives:
                ordered = sorted(
                    active_objectives,
                    key=lambda item: (
                        -float(item.get("weight", 0.0)),
                        str(item.get("objective_id", "")),
                    ),
                )
                planning_goal = (
                    goal_text
                    + " | intermediate objectives: "
                    + "; ".join(str(item.get("description", "")) for item in ordered)
                )
                self._transition(
                    state,
                    "objective-applied",
                    "active intermediate objectives supplied to decision mechanisms",
                    {
                        "cycle": cycle,
                        "objective_ids": [item.get("objective_id") for item in ordered],
                        "planning_goal": planning_goal,
                    },
                )
            state.plan = self.planner.plan(planning_goal, state)
            self._transition(
                state,
                "plan",
                "hierarchical plan formed",
                {
                    "nodes": [n.node_id for n in state.plan],
                    "objective_ids": [item.get("objective_id") for item in active_objectives],
                },
            )

            # 9. COMPOSE ----------------------------------------------------------
            if self.ablations.skill_composition:
                if hasattr(self.skills, "mathematical_enabled"):
                    self.skills.mathematical_enabled = (
                        self.ablations.mathematical_structure
                    )
                if not self.ablations.mathematical_structure:
                    self._ablated(state, "mathematical_structure")
                state.candidates = self.skills.compose(planning_goal, state)
            else:
                state.candidates = []
                self._ablated(state, "skill_composition")
            self._transition(
                state,
                "compose",
                "candidate actions composed",
                {"candidates": [c.action_id for c in state.candidates]},
            )
            if not state.candidates:
                # planning fallback: plan nodes are themselves candidate actions
                state.candidates = [
                    CandidateAction(
                        f"plan-{n.node_id}",
                        n.description,
                        origin="planner",
                        features={
                            "correctness_estimate": 0.5,
                            "cost": 0.5,
                            "uncertainty": 0.5,
                            "novelty": 0.0,
                            "transfer_value": 0.0,
                        },
                    )
                    for n in state.plan
                ]

            # 9b. MEMORY INFLUENCE ------------------------------------------------
            # Structurally relevant episodic memory biases candidate scoring.
            # This is the only downstream channel the retrieve phase feeds: a
            # removed record must change the ranking under identical inputs,
            # and an irrelevant record (zero structural overlap) never does.
            memory_bias = self._memory_biases(memories, structure)
            if memory_bias:
                state.candidates = [
                    (
                        replace(
                            candidate,
                            features={
                                **dict(candidate.features),
                                "correctness_estimate": min(
                                    1.0,
                                    float(candidate.features.get("correctness_estimate", 0.0))
                                    + memory_bias[candidate.action_id],
                                ),
                            },
                        )
                        if candidate.action_id in memory_bias
                        else candidate
                    )
                    for candidate in state.candidates
                ]
                self._transition(
                    state,
                    "memory-influence",
                    "retrieved episodic memory biased candidate scoring",
                    {"biases": dict(sorted(memory_bias.items()))},
                )

            # 10. IMAGINE ------------------------------------------------------------
            imagined = 0
            if self.ablations.world_model:
                for candidate in state.candidates:
                    rollout = self.world_model.rollout(context, [candidate.action_id])
                    state.predictions.extend(rollout)
                    imagined += len(rollout)
                self._transition(
                    state,
                    "imagine",
                    "imagined rollouts generated (never observed evidence)",
                    {"rollout_predictions": imagined},
                )
            else:
                self._ablated(state, "world_model:rollout")

            # 11. RANK ---------------------------------------------------------------
            ranked = self.objective.evaluate(
                state.candidates,
                {
                    "cycle": cycle,
                    "objectives": list(state.representation.get("active_objectives", ())),
                },
            )
            state.candidates = ranked
            self._transition(
                state,
                "rank",
                "candidates ranked by multi-objective evidence",
                {
                    "ranking": [c.action_id for c in ranked],
                    "weights": dict(ranked[0].weights_used) if ranked else {},
                },
            )
            if not ranked:
                self._transition(state, "rank", "no actionable candidates; cycle ends", {})
                continue

            # 12. EXECUTE (governed, fail-closed) --------------------------------------
            best = ranked[0]
            if self.executor is None:
                state.outcome = Outcome.UNEXECUTED
                state.outcome_detail = "no executor injected; plan produced but never acted on"
                self._transition(state, "execute", "execution refused: no governed boundary", {})
                break
            expected = (
                self.world_model.predict(context, best.action_id)
                if self.ablations.world_model
                else None
            )
            result = dict(self.executor.execute(best.action_id, {"kind": "plan", "cycle": cycle}))
            executed_once = True
            state.add_evidence(
                EvidenceItem(
                    f"exec-{cycle}",
                    EvidenceOrigin.OBSERVED,
                    EpistemicStatus.KNOWN,
                    {"action": best.action_id, "result": result},
                    source="governed-executor",
                    uncertainty=0.0,
                )
            )
            self._transition(
                state,
                "execute",
                "candidate executed through governed boundary",
                {"action": best.action_id, "result": result},
            )

            # 13. COMPARE / WORLD-MODEL UPDATE ------------------------------------------
            if self.ablations.world_model and expected is not None:
                observed_token = str(result.get("observation", ""))
                error = self.world_model.update(context, best.action_id, observed_token)
                state.prediction_errors.append(error)
                self._transition(
                    state,
                    "compare",
                    "observed outcome compared with prediction",
                    {
                        "expected": expected.expected,
                        "observed": observed_token,
                        "prediction_error": error,
                        "model_health": self.world_model.health().status,
                    },
                )

            # 14. METACONTROL ------------------------------------------------------------
            assessment = self.metacontroller.assess(state)
            state.control_decisions.append(
                {
                    "cycle": cycle,
                    "action": assessment.action,
                    "rationale": assessment.rationale,
                    "signals": dict(assessment.signals),
                }
            )
            self._transition(
                state,
                "metacontrol",
                f"control decision: {assessment.action}",
                {
                    "action": assessment.action,
                    "rationale": assessment.rationale,
                    "signals": dict(assessment.signals),
                },
            )
            if self.objective_controller is not None:
                latest_error = state.prediction_errors[-1] if state.prediction_errors else 0.0
                objectives = self.objective_controller.derive(
                    goal_text,
                    uncertainty=min(1.0, max(0.0, float(latest_error))),
                    contradictions=sum(
                        1 for h in state.hypotheses if h.status is HypothesisStatus.REFUTED
                    ),
                    missing_evidence=0 if state.retrieved_memory_refs else 1,
                    prediction_error=float(latest_error),
                )
                objective_rows = [
                    {
                        "objective_id": o.objective_id,
                        "description": o.description,
                        "metric": o.metric,
                        "target": o.target,
                        "weight": o.weight,
                        "status": o.status,
                    }
                    for o in objectives
                ]
                state.representation["active_objectives"] = objective_rows
                self._transition(
                    state,
                    "objectives",
                    "intermediate objectives derived and retained for the next decision",
                    {"cycle": cycle, "objectives": objective_rows},
                )
            if assessment.action == "replan":
                if self.ablations.replanning:
                    state.plan = self.planner.replan(
                        goal_text, state, {"cycle": cycle, "signals": dict(assessment.signals)}
                    )
                    state.replanning_events.append(
                        {"cycle": cycle, "rationale": assessment.rationale}
                    )
                    self._transition(
                        state,
                        "replan",
                        "plan revised after control decision",
                        {"nodes": [n.node_id for n in state.plan]},
                    )
                else:
                    self._ablated(state, "replanning")
            # 15. OUTCOME / LEARNING -----------------------------------------------
            cycle_success = bool(result.get("goal_met"))
            self._learn(
                state,
                problem_class,
                success=cycle_success,
                cycle=cycle,
                result=result,
                executed_action=best.action_id,
            )
            if cycle_success:
                solved = True
                break
            if assessment.action == "halt_stalled":
                break

        if solved:
            state.outcome = Outcome.SOLVED
            state.outcome_detail = "goal verified by governed execution feedback"
        elif state.outcome is None:
            state.outcome = Outcome.STALLED if executed_once else Outcome.UNEXECUTED
            state.outcome_detail = (
                "cycle budget exhausted" if executed_once else "no governed execution occurred"
            )
        self._transition(
            state,
            "terminate",
            f"episode closed: {state.outcome.value}",
            {"outcome": state.outcome.value, "detail": state.outcome_detail},
        )
        state.verify_transitions()
        return state

    # -- helpers ----------------------------------------------------------------
    def _compare_hypotheses(
        self,
        state: CognitiveState,
        action: str,
        observed: Mapping[str, Any],
        predictions: Mapping[str, Sequence],
    ) -> None:
        observed_token = str(observed.get("observation", ""))
        confirmed, refuted = [], []
        for hypothesis in state.active_hypotheses():
            expected = next(
                (p for p in predictions.get(hypothesis.hypothesis_id, ()) if p.action == action),
                None,
            )
            if expected is None:
                continue
            if expected.expected == observed_token:
                updated = hypothesis.with_update(
                    confidence=min(1.0, hypothesis.confidence + 0.25),
                    status=HypothesisStatus.CONFIRMED,
                    support=f"intervention:{action}",
                )
                confirmed.append(hypothesis.hypothesis_id)
            else:
                updated = hypothesis.with_update(
                    confidence=max(0.0, hypothesis.confidence - 0.5),
                    status=HypothesisStatus.REFUTED,
                    refute=f"intervention:{action}",
                )
                refuted.append(hypothesis.hypothesis_id)
            state.replace_hypothesis(updated)
        self._transition(
            state,
            "hypothesis-update",
            "hypotheses updated by intervention evidence",
            {
                "confirmed": confirmed,
                "refuted": refuted,
                "remaining_active": [h.hypothesis_id for h in state.active_hypotheses()],
            },
        )

    def _select_representation(self, problem: Mapping[str, Any], structure: frozenset) -> Any:
        """Measured representation selection: utility is the candidate's
        structural coverage of THIS problem (fraction of declared structure
        recoverable from the candidate payload, plus any extracted edge or
        symbol sets); cost is a declared per-evaluation proxy scaled by
        payload size.  No external capability claim is made."""
        import json as _json

        declared = problem.get("representation_evidence") or {}

        def evaluate(kind: str, payload: Mapping[str, Any]) -> tuple[float, float]:
            entry = declared.get(kind)
            if isinstance(entry, Mapping) and "utility" in entry:
                # The problem declares measured evidence for this kind;
                # trust it over the structural proxy (both are bounded
                # per-evaluation values, not capability claims).
                return float(entry["utility"]), float(entry.get("cost", 0.0))
            encoded = _json.dumps(payload, sort_keys=True, default=str)
            covered = sum(1 for item in structure if str(item) in encoded)
            utility = covered / max(1, len(structure))
            for key in ("edges", "symbols", "unit_direction"):
                if payload.get(key):
                    utility += 0.1
            utility = min(1.0, utility)
            cost = 0.05 + min(0.2, len(encoded) / 100_000.0)
            return utility, cost

        return self.representation_controller.select(problem, evaluate)

    def _memory_biases(self, memories: Sequence[Any], structure: frozenset) -> dict[str, float]:
        """Map candidate action ids to a scoring boost earned by retrieved
        episodic memory.  A record qualifies only when it overlaps the
        current problem structure (irrelevant memory cannot manufacture
        influence) and records a successful outcome with the action it
        executed.  Boost magnitude scales with overlap and transfer value."""
        biases: dict[str, float] = {}
        for item in memories:
            if item.deprecated or item.kind is not MemoryKind.EPISODIC:
                continue
            features = item.structural_features
            overlap = len(features & structure) / max(1, len(features))
            if overlap <= 0.0:
                continue
            payload = item.payload or {}
            succeeded = (
                payload.get("success") is True
                or str(payload.get("prior_outcome") or payload.get("outcome") or "").lower()
                == "solved"
            )
            if not succeeded:
                continue
            executed = payload.get("executed_action") or payload.get("executed_arm")
            if not isinstance(executed, str) or not executed:
                continue
            action_ids = {executed}
            if ":" not in executed:
                action_ids.add(f"strategy:{executed}")
            boost = min(0.4, 0.1 + 0.3 * overlap + 0.2 * float(item.transfer_value or 0.0))
            for action_id in action_ids:
                biases[action_id] = max(biases.get(action_id, 0.0), boost)
        return biases

    def _learn(
        self,
        state: CognitiveState,
        problem_class: str,
        *,
        success: bool,
        cycle: int,
        result: Mapping[str, Any] | None = None,
        executed_action: str | None = None,
    ) -> None:
        if self.episode_learner is not None:
            # Close the observed outcome into the canonical LearningService;
            # replay protection there fails closed on duplicates.  A duplicate
            # rejection is recorded evidence, not a reason to kill the episode.
            try:
                self.episode_learner.record_episode(
                    state,
                    success=success,
                    cycle=cycle,
                    result=dict(result or {}),
                    channel="consolidation",
                )
            except ValueError as exc:
                state.learning_updates.append(
                    {
                        "kind": "canonical-learning-service-rejected",
                        "reason": str(exc),
                        "cycle": cycle,
                        "counts_for_control": False,
                    }
                )
        if self.ablations.meta_learning and state.selected_strategy:
            self.metalearner.update(
                problem_class, state.selected_strategy, success, detail=f"cycle={cycle}"
            )
            state.learning_updates.append(
                {
                    "kind": "strategy",
                    "strategy": state.selected_strategy,
                    "problem_class": problem_class,
                    "success": success,
                    "cycle": cycle,
                }
            )
            # Bank the outcome under the executed arm's own key as well: the
            # strategy portfolio is scored from stats[(class, arm)], so a
            # measured result that never lands there can never move the
            # candidates that produced it (adversarial review finding).
            if isinstance(executed_action, str) and executed_action.startswith("strategy:"):
                arm = executed_action.split(":", 1)[1]
                self.metalearner.update(
                    problem_class, arm, success, detail=f"executed-arm cycle={cycle}"
                )
                state.learning_updates.append(
                    {
                        "kind": "executed-arm",
                        "strategy": arm,
                        "problem_class": problem_class,
                        "success": success,
                        "cycle": cycle,
                    }
                )
        self._transition(
            state,
            "learn",
            "episode outcome fed back to learning",
            {
                "success": success,
                "problem_class": problem_class,
                "strategy": state.selected_strategy,
            },
        )


__all__ = ["AblationConfig", "GeneralIntelligenceCore"]
