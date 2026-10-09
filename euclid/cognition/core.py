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

import inspect
import time
from dataclasses import asdict, dataclass, replace
from typing import Any, Callable, Mapping, Sequence

from ..evidence import EvidenceChain
from .credit import assign_discounted_credit
from .interfaces import (
    Abducer,
    AnalogyEngine,
    CausalDiscriminator,
    ControlAssessment,
    Deducer,
    Executor,
    MemorySystem,
    MetaController,
    MetaLearner,
    ObjectiveFunction,
    Planner,
    SkillComposer,
    StrategyChoice,
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

# Declared ignorant-prior feature vector for planner-fallback candidates.
# These are policy priors — explicitly NOT measured quantities.
UNMEASURED_PRIOR_FEATURES = {
    "correctness_estimate": 0.5,
    "cost": 0.5,
    "uncertainty": 0.5,
    "novelty": 0.0,
    "transfer_value": 0.0,
}


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
    #: learned macros/skills (distinct from base skill composition)
    learned_primitives: bool = True


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
        episode_learner: Any | None = None,
        representation_controller: Any | None = None,
        objective_controller: Any | None = None,
        evidence: EvidenceChain | None = None,
        clock: Callable[[], float] = time.time,
        max_cycles: int = 8,
        ablations: AblationConfig | None = None,
        analogy_adopt_threshold: float = 0.5,
        strategy_first: bool = False,
        max_probes_per_cycle: int = 1,
        hypothesis_evidence_strength: float = 4.0,  # declared Born-mass prior strength
        memory_bias_base: float = 0.1,
        memory_bias_overlap: float = 0.3,
        memory_bias_transfer: float = 0.2,
        memory_bias_cap: float = 0.4,
        payload_cost_coefficient: float = 0.05,
    ) -> None:
        if max_cycles < 1:
            raise ValueError("max_cycles must be >= 1")
        if max_probes_per_cycle < 1:
            raise ValueError("max_probes_per_cycle must be >= 1")
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
        self.episode_learner = episode_learner
        self.representation_controller = representation_controller
        self.objective_controller = objective_controller
        self.evidence = evidence or EvidenceChain()
        self.clock = clock
        self.max_cycles = max_cycles
        self.ablations = ablations or AblationConfig()
        self.analogy_adopt_threshold = analogy_adopt_threshold
        #: choose how to think before gathering evidence (strategy governs probing)
        self.strategy_first = bool(strategy_first)
        self.max_probes_per_cycle = int(max_probes_per_cycle)
        # declared evidence/policy constants (constructor-visible, never
        # presented as measured quantities)
        self.hypothesis_evidence_strength = float(hypothesis_evidence_strength)
        self.memory_bias_base = float(memory_bias_base)
        self.memory_bias_overlap = float(memory_bias_overlap)
        self.memory_bias_transfer = float(memory_bias_transfer)
        self.memory_bias_cap = float(memory_bias_cap)
        self.payload_cost_coefficient = float(payload_cost_coefficient)
        self._executed = False
        self._probe_index = 0

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

    def _executable_strategies(self) -> tuple[str, ...]:
        """Strategies this episode's skill composer can actually execute.

        The composer is the authority on its own portfolio: ``V16SkillSearchAdapter``
        really runs MCTS/evolution behind ``mcts-v16`` / ``evolution-v16``, while a
        declared-skill composer has no such routes.  Asking the composer keeps
        strategy selection honest — the loop can never advertise a strategy it
        would silently ignore at composition time.
        """
        declared = getattr(self.skills, "available_strategies", None)
        if callable(declared):
            try:
                strategies = tuple(str(s) for s in declared())
            except Exception as exc:  # noqa: BLE001 - degrade, never fabricate
                self._unavailable_strategy_reason = (
                    f"{type(exc).__name__}: {exc}"
                )
                return ()
            if strategies:
                return strategies
        return ()

    # -- the loop -------------------------------------------------------------
    def solve(
        self,
        problem: Mapping[str, Any],
        *,
        goal: str | None = None,
        problem_class: str | None = None,
    ) -> CognitiveState:
        if not isinstance(problem, Mapping):
            to_mapping = getattr(problem, "to_mapping", None)
            if not callable(to_mapping):
                raise TypeError("problem must be a mapping or expose to_mapping()")
            problem = to_mapping()
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
            "context_key", "strategy", "declared_objectives", "measured_reward",
            "reward_authority", "constraints", "problem_digest", "task_spec",
        ):
            if key in problem:
                representation[key] = problem[key]
        state = CognitiveState(problem_id, representation, clock=self.clock)
        state.goals.append(Goal("g0", goal_text))
        # The active mechanism set is part of the scientific record and is
        # readable by specialists that internally depend on other mechanisms.
        state.representation["ablation_config"] = asdict(self.ablations)
        self._executed = False

        # 1. REPRESENT -----------------------------------------------------
        self._represent(state, problem, structure)
        representation_kind = str(state.representation.get("representation_kind", "literal"))
        # Retrieval keys follow the adopted representation's overlay, so a
        # restructured problem genuinely sees different prior experience.
        retrieval_structure = frozenset(
            str(token) for token in state.representation.get(
                "retrieval_structure", sorted(structure)
            )
        )
        if retrieval_structure != structure:
            structure = retrieval_structure

        # 2. RETRIEVE --------------------------------------------------------
        memories = self.memory.retrieve(structure, ALL_MEMORY_KINDS)
        state.retrieved_memory_refs.extend(m.memory_id for m in memories)
        self._transition(
            state, "retrieve", "experience retrieved by causal relevance",
            {"structure": sorted(structure),
             "representation_kind": representation_kind,
             "retrieved": [m.memory_id for m in memories]},
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
        trajectory: list[dict[str, Any]] = []
        excluded_strategies: set[str] = set()
        executed_ids: set[str] = set()
        frozen_candidates: list[CandidateAction] | None = None
        failed_execution = False
        self._probe_index = 0
        for cycle in range(self.max_cycles):
            self._transition(state, "cycle", f"reasoning cycle {cycle} opened", {"cycle": cycle})
            # Without replanning, a failed plan may not be revised: the episode
            # can only fall back to alternatives it had already prepared.
            plan_frozen = (
                not self.ablations.replanning
                and failed_execution
                and frozen_candidates is not None
            )

            if self.strategy_first and state.selected_strategy is None:
                self._select_strategy(
                    state, problem, problem_id, problem_class, cycle, excluded_strategies
                )

            if plan_frozen:
                state.candidates = [
                    c for c in frozen_candidates or () if c.action_id not in executed_ids
                ]
                self._transition(
                    state,
                    "replan-ablated",
                    "replanning disabled: falling back to previously prepared candidates",
                    {"cycle": cycle, "remaining": [c.action_id for c in state.candidates]},
                )
                if not state.candidates:
                    break
                ranked = list(state.candidates)
            else:
                # 4-5. ABDUCE / DEDUCE ------------------------------------------
                predictions_by_hypothesis = self._abduce_and_deduce(state, context)

                # 6. CAUSAL DISCRIMINATION / EVIDENCE GATHERING ----------------
                if self.ablations.causal_reasoning and predictions_by_hypothesis:
                    self._gather_evidence(state, cycle, context, predictions_by_hypothesis)
                elif not self.ablations.causal_reasoning:
                    self._ablated(state, "causal_reasoning")

                if state.hypotheses and all(
                    hypothesis.status is HypothesisStatus.REFUTED
                    for hypothesis in state.hypotheses
                ):
                    state.outcome = Outcome.ABORTED
                    state.outcome_detail = (
                        "all competing hypotheses were refuted by observed intervention evidence"
                    )
                    self._transition(
                        state,
                        "hypothesis-exhausted",
                        "all hypotheses refuted; downstream planning refused",
                        {
                            "cycle": cycle,
                            "refuted": [
                                hypothesis.hypothesis_id for hypothesis in state.hypotheses
                            ],
                        },
                    )
                    break

                # 7. STRATEGY SELECTION -----------------------------------------
                if not self.strategy_first:
                    self._select_strategy(
                        state, problem, problem_id, problem_class, cycle, excluded_strategies
                    )

                # 8. PLAN ---------------------------------------------------------
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
                self._evaluate_plan_counterfactual(
                    state, context, stage=f"cycle-{cycle}:initial"
                )

                # 8b. RESTRUCTURE the search representation (measured) --------
                if self.ablations.representation_restructuring:
                    self._restructure(state)

                # 9. COMPOSE ------------------------------------------------------
                if not self.ablations.mathematical_structure:
                    # Remove the mathematical prior at its source: the composer
                    # itself must stop routing to phi-parameterised search, not
                    # merely be told to ignore the result afterwards.
                    if hasattr(self.skills, "mathematical_enabled"):
                        self.skills.mathematical_enabled = False
                    self._ablated(state, "mathematical_structure")
                if not self.ablations.learned_primitives:
                    self._ablated(state, "learned_primitives")
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

                # 9b. MEMORY INFLUENCE --------------------------------------------
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

                # 10. IMAGINE -------------------------------------------------------
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

                # 11. RANK ------------------------------------------------------------
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
            state.expected_outcomes.append(
                {
                    "cycle": cycle,
                    "action": best.action_id,
                    "predicted": expected.expected if expected is not None else None,
                    "confidence": expected.confidence if expected is not None else None,
                    "success_probability": best.features.get("correctness_estimate"),
                    "epistemic_status": "predicted",
                }
            )
            result = dict(
                self.executor.execute(
                    best.action_id, {"kind": "plan", "cycle": cycle, **dict(best.payload)}
                )
            )
            self._executed = True
            executed_ids.add(best.action_id)
            if not self.ablations.replanning and frozen_candidates is None:
                frozen_candidates = list(ranked)
            state.actual_outcomes.append(
                {
                    "cycle": cycle,
                    "action": best.action_id,
                    "goal_met": bool(result.get("goal_met")),
                    "observation": str(result.get("observation", ""))[:256],
                    "epistemic_status": "observed",
                }
            )
            skills_used = list(dict(best.payload).get("skills", ()))
            if skills_used:
                state.selected_skills.append(
                    {"cycle": cycle, "action": best.action_id, "skills": skills_used}
                )
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
            trajectory.append(
                {
                    "cycle": cycle,
                    "action": best.action_id,
                    "strategy": state.selected_strategy,
                    "goal_met": bool(result.get("goal_met")),
                }
            )

            # 13. COMPARE / WORLD-MODEL UPDATE ------------------------------------------
            if self.ablations.world_model and expected is not None:
                observe = getattr(self.world_model, "observe_result", None)
                observed_token = str(result.get("observation", ""))
                if callable(observe):
                    error = float(observe(context, best.action_id, result))
                else:
                    error = self.world_model.update(context, best.action_id, observed_token)
                state.prediction_errors.append(error)
                self._record_uncertainty(state, f"execution:{cycle}")
                self._refresh_analogies(state)
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
            assessment = self._objective_bias(state, self.metacontroller.assess(state))
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
            self._apply_control(
                state, assessment, cycle, goal_text, context,
                problem, problem_id, problem_class, excluded_strategies,
            )
            # 15. OUTCOME / LEARNING -----------------------------------------------
            cycle_success = bool(result.get("goal_met"))
            failed_execution = not cycle_success
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
            state.outcome = Outcome.STALLED if self._executed else Outcome.UNEXECUTED
            state.outcome_detail = (
                "cycle budget exhausted" if self._executed else "no governed execution occurred"
            )
        self._assign_long_horizon_credit(
            state,
            problem_class,
            trajectory,
            solved=bool(state.outcome is Outcome.SOLVED),
        )
        self._consolidate(state)
        self._transition(
            state,
            "terminate",
            f"episode closed: {state.outcome.value}",
            {"outcome": state.outcome.value, "detail": state.outcome_detail},
        )
        state.verify_transitions()
        return state

    # -- loop stages --------------------------------------------------------------
    def _abduce_and_deduce(
        self, state: CognitiveState, context: str
    ) -> dict[str, Sequence]:
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
            existing = next(
                (h for h in state.hypotheses if h.hypothesis_id == hypothesis.hypothesis_id),
                None,
            )
            if existing is None:
                state.hypotheses.append(hypothesis)
            elif (
                existing.status is HypothesisStatus.ACTIVE
                and existing.confidence != hypothesis.confidence
            ):
                # an abducer that tracks a posterior refreshes confidence;
                # status changes stay with the evidence update.
                state.replace_hypothesis(replace(existing, confidence=hypothesis.confidence))

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
        return predictions_by_hypothesis

    def _gather_evidence(
        self,
        state: CognitiveState,
        cycle: int,
        context: str,
        predictions: Mapping[str, Sequence],
    ) -> None:
        """Discriminating interventions until the evidence policy says act.

        A metacontroller without ``pre_action`` gets exactly one discrimination
        per cycle (the original loop).  With one, each probe must be justified
        by a recorded evidence decision, bounded by ``max_probes_per_cycle``.
        """
        pre_action = getattr(self.metacontroller, "pre_action", None)
        if not callable(pre_action):
            self._discriminate_once(state, cycle, predictions)
            return
        for _ in range(self.max_probes_per_cycle):
            decision = pre_action(state)
            self._transition(
                state,
                "evidence-decision",
                f"evidence policy: {decision.action}",
                {
                    "cycle": cycle,
                    "action": decision.action,
                    "rationale": decision.rationale,
                    "signals": dict(decision.signals),
                },
            )
            if decision.action != "seek_evidence":
                break
            if not self._discriminate_once(state, cycle, predictions):
                break
            predictions = self._abduce_and_deduce(state, context)
            if not predictions:
                break

    def _discriminate_once(
        self, state: CognitiveState, cycle: int, predictions: Mapping[str, Sequence]
    ) -> bool:
        intervention = self.discriminator.discriminate(state.active_hypotheses(), predictions)
        if intervention is None:
            self._transition(
                state,
                "discriminate",
                "no discriminating intervention available; alternatives retained",
                {},
            )
            return False
        self._transition(
            state,
            "discriminate",
            "discriminating intervention selected",
            {
                "action": intervention.action,
                "expected_divergence": intervention.expected_divergence,
                "rationale": intervention.rationale,
                **({"payload": dict(intervention.payload)} if intervention.payload else {}),
            },
        )
        if self.executor is None:
            return False
        observed = self.executor.execute(
            intervention.action,
            {"kind": "intervention", "cycle": cycle, **dict(intervention.payload)},
        )
        self._executed = True
        self._compare_hypotheses(state, intervention, observed, predictions)
        return not observed.get("budget_exhausted")

    def _select_strategy(
        self,
        state: CognitiveState,
        problem: Mapping[str, Any],
        problem_id: str,
        problem_class: str,
        cycle: int,
        excluded: set[str],
    ) -> None:
        # The portfolio is whatever the skill composer can really execute.
        # A hardcoded tuple would silently starve the composed strategies
        # (v16 MCTS/evolution), which is exactly how they became
        # unreachable from the loop while still passing their own tests.
        available_strategies = tuple(self._executable_strategies())
        if not available_strategies:
            # A composer that declares no portfolio can still be driven by
            # the loop's own reasoning strategies.
            available_strategies = (
                "analogy-causal-plan", "abduce-intervene-deduce",
                "rollout-search-execute",
            )
        remaining = tuple(s for s in available_strategies if s not in excluded)
        if remaining:
            available_strategies = remaining
        if self.ablations.meta_learning:
            requested = str(problem.get("strategy") or "").strip()
            if requested:
                if requested not in available_strategies:
                    # Fail closed: a declared strategy the composer cannot
                    # execute is an unavailable result, never a silent
                    # substitution that would fabricate a different plan.
                    raise ValueError(
                        f"declared strategy {requested!r} is not executable; "
                        f"available: {sorted(available_strategies)}"
                    )
                choice = StrategyChoice(
                    requested, tuple(s for s in available_strategies
                                     if s != requested),
                    f"declared by problem {problem_id}",
                )
            else:
                choice = self.metalearner.select_strategy(
                    problem_class, available_strategies
                )
            state.selected_strategy = choice.strategy_id
            state.alternative_strategies = list(choice.alternatives)
            state.strategy_history.append(
                {
                    "cycle": cycle,
                    "selected": choice.strategy_id,
                    "basis": choice.basis,
                    "excluded": sorted(excluded),
                }
            )
            self._transition(
                state, "strategy", "reasoning strategy selected",
                {"selected": choice.strategy_id,
                 "alternatives": list(choice.alternatives),
                 "basis": choice.basis,
                 "available": list(available_strategies)},
            )
        else:
            state.selected_strategy = available_strategies[0]
            state.alternative_strategies = list(available_strategies[1:])
            state.strategy_history.append(
                {"cycle": cycle, "selected": available_strategies[0],
                 "basis": "meta-learning ablated: declared default order"}
            )
            self._ablated(state, "meta_learning")

    def _restructure(self, state: CognitiveState, *, exclude: Sequence[str] = ()) -> None:
        restructure = getattr(self.representation_controller, "restructure", None)
        if self.representation_controller is None or not callable(restructure):
            return
        try:
            report = dict(restructure(state, exclude=tuple(exclude)))
        except Exception as exc:  # noqa: BLE001 - representation is advisory
            self._transition(
                state, "restructure", "representation restructuring unavailable",
                {"error": f"{type(exc).__name__}: {exc}"},
            )
            return
        state.representation["planning_representation"] = report.get("selected")
        self._transition(
            state, "restructure",
            f"search representation: {report.get('selected')}",
            report,
        )

    def _record_uncertainty(self, state: CognitiveState, event: str) -> None:
        summary = getattr(self.world_model, "uncertainty_summary", None)
        if callable(summary):
            state.uncertainty_trace.append({"event": event, **dict(summary())})
        assumptions = getattr(self.world_model, "assumptions", None)
        if callable(assumptions):
            state.causal_assumptions = [dict(row) for row in assumptions()]

    def _apply_control(
        self,
        state: CognitiveState,
        assessment: ControlAssessment,
        cycle: int,
        goal_text: str,
        context: str,
        problem: Mapping[str, Any],
        problem_id: str,
        problem_class: str,
        excluded: set[str],
    ) -> None:
        """Carry out a metacognitive decision through the owning specialist."""
        action = assessment.action
        if action == "replan":
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
                self._evaluate_plan_counterfactual(
                    state, context, stage=f"cycle-{cycle}:replan"
                )
            else:
                self._ablated(state, "replanning")
        elif action == "change_strategy":
            if not self.ablations.meta_learning:
                self._ablated(state, "meta_learning:change_strategy")
            else:
                if state.selected_strategy:
                    excluded.add(state.selected_strategy)
                self._select_strategy(state, problem, problem_id, problem_class, cycle, excluded)
        elif action == "change_representation":
            if self.ablations.representation_restructuring:
                current = state.representation.get("planning_representation")
                self._restructure(state, exclude=(current,) if current else ())
            else:
                self._ablated(state, "representation_restructuring:change")
        elif action == "abandon_transfer":
            abandon = getattr(self.analogy, "abandon", None)
            if self.ablations.analogy and callable(abandon):
                withdrawn = set(abandon(state))
                state.analogies[:] = [
                    (
                        replace(
                            a, status=AnalogyStatus.ABANDONED,
                            rationale=a.rationale + " | abandoned: contradicted by evidence",
                        )
                        if a.analogy_id in withdrawn
                        else a
                    )
                    for a in state.analogies
                ]
                self._transition(
                    state, "abandon-transfer", "transferred structure withdrawn",
                    {"abandoned": sorted(withdrawn), "rationale": assessment.rationale},
                )
        elif action == "repair_model":
            repair = getattr(self.world_model, "repair", None)
            if self.ablations.world_model and callable(repair):
                report = dict(repair(state))
                self._record_uncertainty(state, f"model-repair:{cycle}")
                self._transition(state, "model-repair", "world model selectively rebuilt", report)
        elif action == "adjust_plan_depth":
            scale = float(state.representation.get("planning_budget_scale", 1.0))
            state.representation["planning_budget_scale"] = min(8.0, scale * 2.0)
            self._transition(
                state, "adjust-plan-depth", "planning budget scaled",
                {"planning_budget_scale": state.representation["planning_budget_scale"],
                 "rationale": assessment.rationale},
            )

    def _consolidate(self, state: CognitiveState) -> None:
        consolidate = getattr(self.episode_learner, "consolidate", None)
        if not callable(consolidate):
            return
        try:
            report = dict(consolidate(state))
        except Exception as exc:  # noqa: BLE001 - learning failure is evidence
            self._transition(
                state, "consolidate", "knowledge consolidation failed",
                {"error": f"{type(exc).__name__}: {exc}"},
            )
            return
        self._transition(
            state, "consolidate", "knowledge abstracted and transfer recorded", report
        )

    def _evaluate_plan_counterfactual(
        self,
        state: CognitiveState,
        context: str,
        *,
        stage: str,
    ) -> None:
        """Score the current plan against an explicit no-intervention baseline.

        Counterfactual rows remain predicted evidence. They may trigger a
        replan through the meta-controller, but can never be promoted to an
        observed outcome or execution proof.
        """
        counterfactual = getattr(self.world_model, "counterfactual", None)
        if not callable(counterfactual) or not state.plan:
            return
        actions = [str(node.description) for node in state.plan if node.description]
        if not actions:
            return
        try:
            rows = list(counterfactual(context, ("no-intervention", *actions)))
            baseline_row = next(
                row for row in rows if str(row.get("action")) == "no-intervention"
            )
            baseline = float(dict(baseline_row.get("future") or {}).get("outcome", 0.0))
            scored = []
            for row in rows:
                action = str(row.get("action"))
                if action == "no-intervention":
                    continue
                outcome = float(dict(row.get("future") or {}).get("outcome", 0.0))
                scored.append(
                    {
                        "action": action,
                        "predicted_outcome": outcome,
                        "delta_vs_baseline": outcome - baseline,
                        "epistemic_status": "predicted",
                    }
                )
        except Exception as exc:  # noqa: BLE001 - counterfactual is advisory
            self._transition(
                state,
                "counterfactual-plan",
                "counterfactual plan evaluation unavailable",
                {"stage": stage, "error": f"{type(exc).__name__}: {exc}"},
            )
            return
        best_delta = max(
            (float(row["delta_vs_baseline"]) for row in scored), default=0.0
        )
        report = {
            "stage": stage,
            "baseline_action": "no-intervention",
            "baseline_outcome": baseline,
            "alternatives": scored,
            "best_delta": best_delta,
            "epistemic_status": "predicted",
        }
        state.representation["counterfactual_plan_evaluation"] = report
        self._transition(
            state,
            "counterfactual-plan",
            "plan scored against no-intervention counterfactual baseline",
            report,
        )

    def _assign_long_horizon_credit(
        self,
        state: CognitiveState,
        problem_class: str,
        trajectory: Sequence[Mapping[str, Any]],
        *,
        solved: bool,
    ) -> None:
        if not trajectory:
            return
        declared_reward = state.representation.get("measured_reward")
        authority = str(state.representation.get("reward_authority") or "none")
        if declared_reward is not None and authority != "none":
            terminal_value = float(declared_reward)
            source = f"authoritative-terminal-reward:{authority}"
        else:
            terminal_value = 1.0 if solved else 0.0
            source = "observed-terminal-goal-outcome"
        assignments = assign_discounted_credit(
            [str(row.get("action") or "") for row in trajectory],
            terminal_value,
            gamma=0.9,
            source=source,
        )
        update_credit = getattr(self.metalearner, "update_credit", None)
        rows = []
        for assignment, event in zip(assignments, trajectory):
            strategy = str(event.get("strategy") or "")
            if callable(update_credit) and strategy:
                update_credit(
                    problem_class,
                    strategy,
                    assignment.credit,
                    detail=f"long-horizon step={assignment.step}",
                )
            row = {
                "kind": "long-horizon-credit",
                "step": assignment.step,
                "action": assignment.action,
                "strategy": strategy or None,
                "credit": assignment.credit,
                "discount": assignment.discount,
                "source": assignment.source,
                "counts_for_control": callable(update_credit) and bool(strategy),
            }
            state.learning_updates.append(row)
            rows.append(row)
        self._transition(
            state,
            "credit",
            "terminal outcome assigned across executed trajectory",
            {"gamma": 0.9, "assignments": rows, "source": source},
        )

    def _objective_bias(
        self, state: CognitiveState, assessment: ControlAssessment
    ) -> ControlAssessment:
        """Let measured epistemic state override an 'act now' verdict.

        Intermediate objectives are derived from quantities the episode has
        actually measured — prediction confidence (uncertainty), refuted
        hypotheses (contradictions), predictions that never produced an observed
        error (evidence gaps), and prediction error.  When the dominant
        objective is epistemic and the metacontroller would otherwise act, the
        loop is told to gather evidence instead: spending a cycle on evidence is
        only worth it when the measurement says the model is unsupported.

        With no controller, or when the objective is the terminal goal itself,
        the metacontroller's verdict passes through untouched.
        """
        if self.objective_controller is None:
            return assessment
        predictions = state.predictions
        uncertainty = (
            sum(max(0.0, 1.0 - float(p.confidence)) for p in predictions) / len(predictions)
            if predictions
            else 0.0
        )
        contradictions = sum(
            1 for h in state.hypotheses
            if str(getattr(h.status, "value", h.status)) == "REFUTED"
        )
        evidence_gap = max(0, len(predictions) - len(state.prediction_errors))
        prediction_error = (
            sum(abs(float(e)) for e in state.prediction_errors) / len(state.prediction_errors)
            if state.prediction_errors
            else 0.0
        )
        try:
            objectives = self.objective_controller.derive(
                state.goals[-1].description if state.goals else "",
                uncertainty=uncertainty,
                contradictions=contradictions,
                missing_evidence=evidence_gap,
                prediction_error=prediction_error,
            )
        except Exception as exc:  # noqa: BLE001 - objectives are advisory
            self._transition(
                state, "objective", "objective derivation failed; verdict unchanged",
                {"error": f"{type(exc).__name__}: {exc}"},
            )
            return assessment
        if not objectives:
            return assessment
        dominant = max(objectives, key=lambda o: float(o.weight))
        epistemic = dominant.metric in {
            "uncertainty", "contradictions", "evidence_gap", "prediction_error",
        }
        self._transition(
            state, "objective", "intermediate objectives derived from measured signals",
            {"uncertainty": uncertainty, "contradictions": contradictions,
             "evidence_gap": evidence_gap, "prediction_error": prediction_error,
             "dominant": dominant.metric, "objectives": [o.objective_id for o in objectives]},
        )
        if not epistemic or assessment.action != "continue":
            return assessment
        return ControlAssessment(
            "seek_evidence",
            f"dominant intermediate objective {dominant.metric!r} "
            f"(weight {float(dominant.weight):.3f}) outranks acting now | "
            f"{assessment.rationale}",
            dict(assessment.signals),
        )

    # -- helpers ----------------------------------------------------------------
    @staticmethod
    def _retrieval_tokens(structure: frozenset[str], payload: Mapping[str, Any]) -> frozenset[str]:
        """Retrieval keys a representation would index by.

        Only declared relations and edges become keys; opaque payload internals
        (source text, numeric vectors) must never enter the retrieval
        vocabulary, or retrieval would silently degrade to surface matching.
        """
        tokens = {str(s) for s in structure}
        for key in ("relations", "edges"):
            for item in payload.get(key, ()) or ():
                if isinstance(item, (list, tuple)):
                    tokens.update(str(part) for part in item)
                else:
                    tokens.add(str(item))
        return frozenset(tokens)

    def _represent_from_evidence(
        self,
        state: CognitiveState,
        structure: frozenset[str],
        observations: tuple[Any, ...],
        evidence: Mapping[str, Any],
    ) -> None:
        """Adopt a representation using caller-supplied measured evidence.

        The measurement decides; complexity never earns credit on its own.  A
        representation is adopted only when its measured net utility strictly
        beats the literal baseline, so a representation that measures no better
        is rejected even though it was offered.
        """
        measured: dict[str, tuple[float, float]] = {}
        for kind, row in evidence.items():
            if not isinstance(row, Mapping):
                continue
            try:
                measured[str(kind)] = (
                    float(row["utility"]), float(row["cost"]),
                )
            except (KeyError, TypeError, ValueError):
                continue

        controller = self.representation_controller
        baseline_kind = str(state.representation.get("representation_kind", "literal"))

        def evaluator(kind: str, _payload: Mapping[str, Any]) -> tuple[float, float]:
            return measured.get(kind, (0.0, 1.0))

        try:
            trial = controller.select(
                {"representation_kind": baseline_kind, "structure": sorted(structure),
                 "observations": list(observations)},
                evaluator,
            )
        except Exception as exc:  # noqa: BLE001 - representation is advisory
            self._transition(
                state, "represent", "declared representation evidence unusable",
                {"error": f"{type(exc).__name__}: {exc}",
                 "representation_kind": "literal"},
            )
            return

        chosen = str(trial.kind)
        payload = trial.payload if trial.accepted else {}
        state.representation["representation_kind"] = chosen
        state.representation["active_representation"] = chosen
        state.representation["representation_adopted"] = bool(trial.accepted)
        state.representation["representation_trial"] = trial.rationale
        if trial.accepted and trial.payload:
            # The overlay is provenance; canonical top-level fields are the
            # executable representation consumed by planners/skills.
            state.representation["representation_overlay"] = dict(trial.payload)
            state.representation.update(dict(trial.payload))
        if chosen != "literal":
            state.representation["retrieval_structure"] = sorted(
                self._retrieval_tokens(structure, payload)
            )
        self._transition(
            state, "represent",
            "representation selected from declared measured evidence",
            {"structure": sorted(structure),
             "observation_count": len(observations),
             "representation_kind": chosen,
             "adopted": bool(trial.accepted),
             "baseline_utility": trial.baseline_utility,
             "candidate_utility": trial.candidate_utility,
             "cost": trial.cost,
             "rationale": trial.rationale,
             "representation_trial": {
                 "kind": chosen,
                 "accepted": bool(trial.accepted),
                 "baseline_utility": trial.baseline_utility,
                 "candidate_utility": trial.candidate_utility,
                 "cost": trial.cost,
                 "rationale": trial.rationale,
             }},
        )

    def _represent(
        self,
        state: CognitiveState,
        problem: Mapping[str, Any],
        structure: frozenset[str],
    ) -> None:
        """Choose a representation by measured net retrieval utility.

        Without a controller the literal representation is used, exactly as
        before.  With one, each candidate is scored by how much prior
        experience it actually retrieves minus its construction cost, and it is
        adopted only when that net utility beats the baseline.  The adopted
        representation's retrieval keys then drive stage 2, so this genuinely
        changes which memories the episode sees.
        """
        observations = tuple(problem.get("observations", ()))
        state.representation.setdefault("representation_kind", "literal")
        state.representation.setdefault("retrieval_structure", sorted(structure))

        if not self.ablations.representation_restructuring:
            self.representation_controller = None
            self._ablated(state, "representation_restructuring")

        # Measured evidence supplied with the problem outranks the loop's
        # retrieval proxy: when the caller measured real utility/cost per
        # representation, that measurement is the evidence, not our guess.
        declared_evidence = problem.get("representation_evidence")
        if (
            self.representation_controller is not None
            and isinstance(declared_evidence, Mapping)
            and declared_evidence
        ):
            self._represent_from_evidence(
                state, structure, observations, declared_evidence
            )
            return
        if self.representation_controller is None:
            self._transition(
                state, "represent", "literal problem representation retained",
                {"structure": sorted(structure),
                 "observation_count": len(observations),
                 "representation_kind": "literal"},
            )
            return

        def evaluator(kind: str, payload: Mapping[str, Any]) -> tuple[float, float]:
            tokens = (
                structure if kind == "literal"
                else self._retrieval_tokens(structure, payload)
            )
            utility = float(len(self.memory.retrieve(tokens, ALL_MEMORY_KINDS)))
            return utility, self.payload_cost_coefficient * float(len(payload))

        try:
            trial = self.representation_controller.select(problem, evaluator)
        except Exception as exc:  # noqa: BLE001 - representation is advisory
            self._transition(
                state, "represent", "representation search failed; baseline retained",
                {"error": f"{type(exc).__name__}: {exc}",
                 "representation_kind": "literal"},
            )
            return

        chosen = str(trial.kind)
        state.representation["representation_kind"] = chosen
        state.representation["active_representation"] = chosen
        state.representation["representation_trial"] = trial.rationale
        state.representation["representation_adopted"] = bool(trial.accepted)
        if trial.accepted and trial.payload:
            # The overlay is provenance; canonical top-level fields are the
            # executable representation consumed by planners/skills.
            state.representation["representation_overlay"] = dict(trial.payload)
            state.representation.update(dict(trial.payload))
        if chosen != "literal":
            state.representation["retrieval_structure"] = sorted(
                self._retrieval_tokens(structure, trial.payload)
            )
        self._transition(
            state, "represent", "representation selected by measured net utility",
            {"structure": sorted(structure),
             "observation_count": len(observations),
             "representation_kind": chosen,
             "adopted": bool(trial.accepted),
             "baseline_utility": trial.baseline_utility,
             "candidate_utility": trial.candidate_utility,
             "cost": trial.cost,
             "rationale": trial.rationale,
             "representation_trial": {
                 "kind": chosen,
                 "accepted": bool(trial.accepted),
                 "baseline_utility": trial.baseline_utility,
                 "candidate_utility": trial.candidate_utility,
                 "cost": trial.cost,
                 "rationale": trial.rationale,
             }},
        )

    def _compare_hypotheses(
        self,
        state: CognitiveState,
        intervention: Any,
        observed: Mapping[str, Any],
        predictions: Mapping[str, Sequence],
    ) -> None:
        action = intervention.action if hasattr(intervention, "action") else str(intervention)
        posterior_update = getattr(self.discriminator, "posterior_update", None)
        if callable(posterior_update):
            # Likelihood-based update: confidence is the posterior, status is
            # a reporting summary of it — no fixed increments.
            self._probe_index += 1
            state.add_evidence(
                EvidenceItem(
                    f"int-{self._probe_index}",
                    EvidenceOrigin.OBSERVED,
                    EpistemicStatus.KNOWN,
                    {"action": action, "result": dict(observed)},
                    source="governed-executor:intervention",
                    uncertainty=0.0,
                )
            )
            updated, details = posterior_update(state, intervention, observed)
            for hypothesis in updated:
                if any(h.hypothesis_id == hypothesis.hypothesis_id for h in state.hypotheses):
                    state.replace_hypothesis(hypothesis)
                else:
                    state.hypotheses.append(hypothesis)
            self._record_uncertainty(state, f"intervention:{self._probe_index}")
            self._transition(
                state,
                "hypothesis-update",
                "posterior updated by intervention evidence",
                {
                    **dict(details),
                    "remaining_active": [h.hypothesis_id for h in state.active_hypotheses()],
                },
            )
            self._refresh_analogies(state)
            return
        observed_token = str(observed.get("observation", ""))
        confirmed, refuted = [], []
        for hypothesis in state.active_hypotheses():
            expected = next(
                (p for p in predictions.get(hypothesis.hypothesis_id, ()) if p.action == action),
                None,
            )
            if expected is None:
                continue
            # Born-rule confidence update: the stored confidence is the Born
            # probability of the confirmation channel of the hypothesis's
            # evidence state  |psi> ~ (sqrt(c*K), sqrt((1-c)*K))  with K the
            # declared evidence strength; each measured intervention outcome
            # adds one unit of Born mass to the matching channel.
            k = self.hypothesis_evidence_strength
            confirm_mass = hypothesis.confidence * k
            refute_mass = (1.0 - hypothesis.confidence) * k
            if expected.expected == observed_token:
                confirm_mass += 1.0
                updated = hypothesis.with_update(
                    confidence=confirm_mass / (confirm_mass + refute_mass),
                    status=HypothesisStatus.CONFIRMED,
                    support=f"intervention:{action}",
                )
                confirmed.append(hypothesis.hypothesis_id)
            else:
                refute_mass += 1.0
                updated = hypothesis.with_update(
                    confidence=confirm_mass / (confirm_mass + refute_mass),
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

    def _refresh_analogies(self, state: CognitiveState) -> None:
        """Re-match analogies whenever evidence reshapes the representation."""
        refresh = getattr(self.analogy, "refresh", None)
        if not (self.ablations.analogy and callable(refresh)):
            return
        mappings = list(refresh(state))
        if not mappings:
            return
        known = {a.analogy_id for a in state.analogies}
        for mapping in mappings:
            if mapping.analogy_id in known:
                state.analogies[:] = [
                    mapping if a.analogy_id == mapping.analogy_id else a
                    for a in state.analogies
                ]
            else:
                state.analogies.append(mapping)
        self._transition(
            state,
            "analogy-refresh",
            "analogies re-evaluated against the evolved representation",
            {
                "mappings": [
                    {
                        "analogy_id": m.analogy_id,
                        "source": m.source_ref,
                        "status": m.status.value,
                        "structural_overlap": m.structural_overlap,
                        "surface_overlap": m.surface_overlap,
                    }
                    for m in mappings
                ]
            },
        )

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
            boost = min(
                self.memory_bias_cap,
                self.memory_bias_base
                + self.memory_bias_overlap * overlap
                + self.memory_bias_transfer * float(item.transfer_value or 0.0),
            )
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
            # replay protection there fails closed on duplicates.  A learner
            # rejection is recorded evidence, never a reason to kill the episode.
            payload = dict(result or {})
            payload.setdefault("goal_met", success)
            payload.setdefault("problem_class", problem_class)
            try:
                record = self.episode_learner.record_episode
                extra = (
                    {"channel": "consolidation"}
                    if "channel" in inspect.signature(record).parameters
                    else {}
                )
                recorded = record(
                    state, success=success, cycle=cycle, result=payload, **extra
                )
            except Exception as exc:  # noqa: BLE001 - learner is advisory
                state.learning_updates.append(
                    {
                        "kind": "canonical-learning-service-rejected",
                        "reason": str(exc),
                        "cycle": cycle,
                        "counts_for_control": False,
                    }
                )
                self._transition(
                    state, "learn", "episode learner rejected the outcome",
                    {"error": f"{type(exc).__name__}: {exc}",
                     "problem_class": problem_class, "cycle": cycle},
                )
            else:
                self._transition(
                    state, "learn", "episode closed into LearningService",
                    {"experience_id": recorded, "success": success,
                     "problem_class": problem_class, "cycle": cycle},
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
