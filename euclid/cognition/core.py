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
from dataclasses import dataclass
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
    representation_restructuring: bool = True
    mathematical_structure: bool = True
    replanning: bool = True


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
        self.episode_learner = episode_learner
        self.representation_controller = representation_controller
        self.objective_controller = objective_controller
        self.evidence = evidence or EvidenceChain()
        self.clock = clock
        self.max_cycles = max_cycles
        self.ablations = ablations or AblationConfig()
        self.analogy_adopt_threshold = analogy_adopt_threshold

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

        representation = {
            str(key): value for key, value in problem.items()
            if key not in {"observations"}
        }
        representation["structure"] = sorted(structure)
        representation["problem_class"] = problem_class
        state = CognitiveState(problem_id, representation, clock=self.clock)
        state.goals.append(Goal("g0", goal_text))

        # Representation changes require measured superiority to the literal
        # baseline; absent measurements, the baseline is retained.
        if self.representation_controller is not None and self.ablations.representation_restructuring:
            measured = dict(problem.get("representation_evidence", {}))

            def evaluate(kind: str, payload: Mapping[str, Any]) -> tuple[float, float]:
                record = measured.get(kind, {})
                return (
                    float(record.get("utility", 0.0)),
                    float(record.get("cost", 0.0)),
                )

            trial = self.representation_controller.select(problem, evaluate)
            record = {
                "representation_id": trial.representation_id,
                "kind": trial.kind,
                "accepted": trial.accepted,
                "baseline_utility": trial.baseline_utility,
                "candidate_utility": trial.candidate_utility,
                "cost": trial.cost,
                "rationale": trial.rationale,
            }
            state.representation_history.append(record)
            if trial.accepted:
                state.representation["active_representation"] = trial.kind
                state.representation["representation_payload"] = dict(trial.payload)
            self._transition(
                state, "representation-control",
                "representation compared against measured baseline", record,
            )
        elif not self.ablations.representation_restructuring:
            self._ablated(state, "representation_restructuring")

        if self.objective_controller is not None:
            objectives = self.objective_controller.derive(
                goal_text,
                uncertainty=float(problem.get("uncertainty", 1.0)),
                contradictions=int(problem.get("contradictions", 0)),
                missing_evidence=int(problem.get("missing_evidence", 0)),
                prediction_error=0.0,
            )
            state.objectives = [
                {
                    "objective_id": item.objective_id,
                    "description": item.description,
                    "parent_goal": item.parent_goal,
                    "evidence_basis": item.evidence_basis,
                    "metric": item.metric,
                    "target": item.target,
                    "weight": item.weight,
                    "status": item.status,
                }
                for item in objectives
            ]
            state.subgoals = [
                Goal(item.objective_id, item.description, parent_id="g0")
                for item in objectives
            ]
            self._transition(
                state, "objective-construction",
                "intermediate objectives derived from measured gaps",
                {"objectives": state.objectives},
            )

        # 1. REPRESENT -----------------------------------------------------
        self._transition(
            state, "represent", "problem representation formed",
            {"structure": sorted(structure), "observation_count": len(observations)},
        )

        # 2. RETRIEVE --------------------------------------------------------
        memories = self.memory.retrieve(structure, ALL_MEMORY_KINDS)
        state.retrieved_memory_refs.extend(m.memory_id for m in memories)
        state.transfer_history.extend({
            "memory_id": memory.memory_id,
            "kind": memory.kind.value,
            "structural_relevance": memory.transfer_value,
            "status": "candidate",
        } for memory in memories)
        self._transition(
            state, "retrieve", "memory retrieved by structural relevance",
            {"retrieved": [m.memory_id for m in memories]},
        )

        # 3. ANALOGY ----------------------------------------------------------
        if self.ablations.analogy:
            surface = frozenset(str(s) for s in problem.get("surface", ()))
            analogies = self.analogy.find(structure, memories, surface)
            state.analogies.extend(analogies)
            adopted = [
                a for a in analogies
                if a.structural_overlap >= self.analogy_adopt_threshold
            ]
            state.analogies[:] = [
                a if a not in adopted else type(a)(
                    a.analogy_id, a.source_ref, a.structural_overlap,
                    a.surface_overlap, a.reliability, AnalogyStatus.ADOPTED,
                    a.rationale + " | adopted: structural overlap above threshold",
                )
                for a in state.analogies
            ]
            self._transition(
                state, "analogy", "structural analogies evaluated",
                {
                    "candidates": [a.analogy_id for a in state.analogies],
                    "adopted": [a.analogy_id for a in state.analogies
                                if a.status is AnalogyStatus.ADOPTED],
                    "rejected": [a.analogy_id for a in state.analogies
                                 if a.status is AnalogyStatus.REJECTED],
                },
            )
        else:
            self._ablated(state, "analogy")

        # seed observed evidence
        for index, observation in enumerate(observations):
            state.add_evidence(EvidenceItem(
                f"obs-{index}", EvidenceOrigin.OBSERVED, EpistemicStatus.KNOWN,
                {"observation": str(observation)}, source="problem-statement", uncertainty=0.0,
            ))

        context = problem_id
        solved = False
        executed_once = False
        for cycle in range(self.max_cycles):
            self._transition(state, "cycle", f"reasoning cycle {cycle} opened",
                             {"cycle": cycle})

            # 4. ABDUCE -----------------------------------------------------
            hypotheses = self.abducer.hypothesise(state.evidence_items, state)
            if len(hypotheses) < 2:
                self._transition(
                    state, "abduce", "abducer returned a single hypothesis; uncertainty retained",
                    {"hypotheses": [h.hypothesis_id for h in hypotheses], "warning": "no competition"},
                )
            else:
                self._transition(
                    state, "abduce", "competing hypotheses generated",
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
                    state, "deduce", "consequences derived per hypothesis",
                    {key: [p.prediction_id for p in value]
                     for key, value in predictions_by_hypothesis.items()},
                )
                confidences = [
                    prediction.confidence
                    for values in predictions_by_hypothesis.values()
                    for prediction in values
                ]
                state.uncertainty = (
                    1.0 - sum(confidences) / len(confidences)
                    if confidences else 1.0
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
                        state, "discriminate",
                        "no discriminating intervention available; alternatives retained",
                        {},
                    )
                else:
                    self._transition(
                        state, "discriminate", "discriminating intervention selected",
                        {"action": intervention.action,
                         "expected_divergence": intervention.expected_divergence,
                         "rationale": intervention.rationale},
                    )
                    state.causal_assumptions.append({
                        "action": intervention.action,
                        "expected_divergence": intervention.expected_divergence,
                        "status": "assumption-pending-intervention",
                    })
                    counterfactual = getattr(self.world_model, "counterfactual", None)
                    if callable(counterfactual):
                        futures = counterfactual(
                            context, [intervention.action, "no-intervention"]
                        )
                        state.counterfactuals.extend(futures)
                        self._transition(
                            state, "counterfactual",
                            "alternative intervention outcomes compared",
                            {"futures": futures},
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
            strategy_source = getattr(self.skills, "available_strategies", None)
            available_strategies = (
                tuple(strategy_source()) if callable(strategy_source)
                else ("analogy-causal-plan", "abduce-intervene-deduce",
                      "rollout-search-execute")
            )
            if self.ablations.meta_learning:
                requested = str(problem.get("strategy") or "").strip()
                if requested:
                    if requested not in available_strategies:
                        raise ValueError(f"requested strategy is unavailable: {requested}")
                    state.selected_strategy = requested
                    state.alternative_strategies = [
                        strategy for strategy in available_strategies
                        if strategy != requested
                    ]
                    basis = "explicit episode strategy request"
                else:
                    choice = self.metalearner.select_strategy(
                        problem_class, available_strategies
                    )
                    state.selected_strategy = choice.strategy_id
                    state.alternative_strategies = list(choice.alternatives)
                    basis = choice.basis
                self._transition(
                    state, "strategy", "reasoning strategy selected",
                    {"selected": state.selected_strategy,
                     "alternatives": list(state.alternative_strategies),
                     "basis": basis},
                )
            else:
                state.selected_strategy = available_strategies[0]
                state.alternative_strategies = list(available_strategies[1:])
                self._ablated(state, "meta_learning")

            # 8. PLAN ------------------------------------------------------------
            state.plan = self.planner.plan(goal_text, state)
            self._transition(
                state, "plan", "hierarchical plan formed",
                {"nodes": [n.node_id for n in state.plan]},
            )

            # 9. COMPOSE ----------------------------------------------------------
            if self.ablations.skill_composition:
                if hasattr(self.skills, "mathematical_enabled"):
                    self.skills.mathematical_enabled = (
                        self.ablations.mathematical_structure
                    )
                if not self.ablations.mathematical_structure:
                    self._ablated(state, "mathematical_structure")
                state.candidates = self.skills.compose(goal_text, state)
                state.selected_capabilities = sorted({
                    candidate.origin for candidate in state.candidates
                })
            else:
                state.candidates = []
                self._ablated(state, "skill_composition")
            self._transition(
                state, "compose", "candidate actions composed",
                {"candidates": [c.action_id for c in state.candidates]},
            )
            if not state.candidates:
                # planning fallback: plan nodes are themselves candidate actions
                state.candidates = [
                    CandidateAction(f"plan-{n.node_id}", n.description, origin="planner",
                                    features={"correctness_estimate": 0.5, "cost": 0.5,
                                              "uncertainty": 0.5, "novelty": 0.0,
                                              "transfer_value": 0.0})
                    for n in state.plan
                ]

            # 10. IMAGINE ------------------------------------------------------------
            imagined = 0
            if self.ablations.world_model:
                for candidate in state.candidates:
                    rollout = self.world_model.rollout(context, [candidate.action_id])
                    state.predictions.extend(rollout)
                    imagined += len(rollout)
                self._transition(
                    state, "imagine", "imagined rollouts generated (never observed evidence)",
                    {"rollout_predictions": imagined},
                )
            else:
                self._ablated(state, "world_model:rollout")

            # 11. RANK ---------------------------------------------------------------
            ranked = self.objective.evaluate(state.candidates, {"cycle": cycle})
            state.candidates = ranked
            self._transition(
                state, "rank", "candidates ranked by multi-objective evidence",
                {"ranking": [c.action_id for c in ranked],
                 "weights": dict(ranked[0].weights_used) if ranked else {}},
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
                if self.ablations.world_model else None
            )
            state.expected_outcome = (
                {
                    "action": best.action_id,
                    "expected": expected.expected,
                    "confidence": expected.confidence,
                }
                if expected is not None else None
            )
            result = dict(self.executor.execute(best.action_id,
                                                {"kind": "plan", "cycle": cycle}))
            state.actual_outcome = dict(result)
            if self.objective_controller is not None and state.objectives:
                audited = []
                for raw in state.objectives:
                    from .adaptive import IntermediateObjective
                    item = IntermediateObjective(**raw)
                    checked = self.objective_controller.audit_alignment(
                        item,
                        metric_improved=bool(result.get("metric_improved", False)),
                        goal_progressed=bool(result.get("goal_met", False)),
                    )
                    audited.append({
                        "objective_id": checked.objective_id,
                        "description": checked.description,
                        "parent_goal": checked.parent_goal,
                        "evidence_basis": checked.evidence_basis,
                        "metric": checked.metric,
                        "target": checked.target,
                        "weight": checked.weight,
                        "status": checked.status,
                    })
                state.objectives = audited
                detached = [
                    item["objective_id"] for item in audited
                    if item["status"] == "detached-proxy"
                ]
                if detached:
                    self._transition(
                        state, "objective-drift",
                        "intermediate metric improved without goal progress",
                        {"detached": detached},
                    )
            executed_once = True
            state.add_evidence(EvidenceItem(
                f"exec-{cycle}", EvidenceOrigin.OBSERVED, EpistemicStatus.KNOWN,
                {"action": best.action_id, "result": result},
                source="governed-executor", uncertainty=0.0,
            ))
            self._transition(
                state, "execute", "candidate executed through governed boundary",
                {"action": best.action_id, "result": result},
            )

            # 13. COMPARE / WORLD-MODEL UPDATE ------------------------------------------
            if self.ablations.world_model and expected is not None:
                observed_token = str(result.get("observation", ""))
                error = self.world_model.update(context, best.action_id, observed_token)
                state.prediction_errors.append(error)
                state.uncertainty = min(1.0, max(0.0, float(error)))
                self._transition(
                    state, "compare", "observed outcome compared with prediction",
                    {"expected": expected.expected, "observed": observed_token,
                     "prediction_error": error,
                     "model_health": self.world_model.health().status},
                )

            # 14. METACONTROL ------------------------------------------------------------
            assessment = self.metacontroller.assess(state)
            state.control_decisions.append(
                {"cycle": cycle, "action": assessment.action,
                 "rationale": assessment.rationale, "signals": dict(assessment.signals)}
            )
            self._transition(
                state, "metacontrol", f"control decision: {assessment.action}",
                {"action": assessment.action, "rationale": assessment.rationale,
                 "signals": dict(assessment.signals)},
            )
            if assessment.action == "replan":
                if self.ablations.replanning:
                    state.plan = self.planner.replan(
                        goal_text, state, {"cycle": cycle, "signals": dict(assessment.signals)}
                    )
                    state.replanning_events.append(
                        {"cycle": cycle, "rationale": assessment.rationale}
                    )
                    self._transition(state, "replan", "plan revised after control decision",
                                     {"nodes": [n.node_id for n in state.plan]})
                else:
                    self._ablated(state, "replanning")
            if assessment.action == "halt_stalled":
                break

            # 15. SUCCESS CHECK ---------------------------------------------------------
            if bool(result.get("goal_met")):
                solved = True
                self._learn(
                    state, problem_class, success=True, cycle=cycle, result=result
                )
                break
            self._learn(
                state, problem_class, success=False, cycle=cycle, result=result
            )

        if solved:
            state.outcome = Outcome.SOLVED
            state.outcome_detail = "goal verified by governed execution feedback"
        elif state.outcome is None:
            state.outcome = Outcome.STALLED if executed_once else Outcome.UNEXECUTED
            state.outcome_detail = (
                "cycle budget exhausted" if executed_once
                else "no governed execution occurred"
            )
        for transfer in state.transfer_history:
            transfer["status"] = (
                "positive-transfer" if state.outcome is Outcome.SOLVED
                else "negative-or-inconclusive-transfer"
            )
            transfer["outcome"] = state.outcome.value
        self._transition(state, "terminate", f"episode closed: {state.outcome.value}",
                         {"outcome": state.outcome.value, "detail": state.outcome_detail})
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
                    status=HypothesisStatus.CONFIRMED, support=f"intervention:{action}",
                )
                confirmed.append(hypothesis.hypothesis_id)
            else:
                updated = hypothesis.with_update(
                    confidence=max(0.0, hypothesis.confidence - 0.5),
                    status=HypothesisStatus.REFUTED, refute=f"intervention:{action}",
                )
                refuted.append(hypothesis.hypothesis_id)
            state.replace_hypothesis(updated)
        self._transition(
            state, "hypothesis-update", "hypotheses updated by intervention evidence",
            {"confirmed": confirmed, "refuted": refuted,
             "remaining_active": [h.hypothesis_id for h in state.active_hypotheses()]},
        )

    def _learn(
        self, state: CognitiveState, problem_class: str, *, success: bool,
        cycle: int, result: Mapping[str, Any],
    ) -> None:
        if self.ablations.meta_learning and state.selected_strategy:
            self.metalearner.update(problem_class, state.selected_strategy, success,
                                    detail=f"cycle={cycle}")
            state.learning_updates.append(
                {"kind": "strategy", "strategy": state.selected_strategy,
                 "problem_class": problem_class, "success": success, "cycle": cycle}
            )
        if self.episode_learner is not None:
            self.episode_learner.record_episode(
                state, success=success, cycle=cycle, result=result
            )
        self._transition(
            state, "learn", "episode outcome fed back to learning",
            {"success": success, "problem_class": problem_class,
             "strategy": state.selected_strategy},
        )


__all__ = ["AblationConfig", "GeneralIntelligenceCore"]
