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
        problem_id = str(problem.get("problem_id") or "").strip()
        if not problem_id:
            raise ValueError("problem requires a problem_id")
        goal_text = str(goal or problem.get("goal") or "").strip()
        if not goal_text:
            raise ValueError("a goal is required")
        structure = frozenset(str(s) for s in problem.get("structure", ()))
        observations = tuple(problem.get("observations", ()))
        problem_class = str(problem_class or problem.get("problem_class") or "unclassified")

        state = CognitiveState(problem_id, {"structure": sorted(structure)}, clock=self.clock)
        state.goals.append(Goal("g0", goal_text))

        # 1. REPRESENT -----------------------------------------------------
        self._represent(state, problem, structure)
        representation_kind = str(state.representation.get("representation_kind", "literal"))
        retrieval_structure = frozenset(
            str(s) for s in state.representation.get("retrieval_structure", structure)
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

        context = str(problem.get("context_key") or problem_id)
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
                self._ablated(state, "meta_learning")

            # 8. PLAN ------------------------------------------------------------
            state.plan = self.planner.plan(goal_text, state)
            self._transition(
                state, "plan", "hierarchical plan formed",
                {"nodes": [n.node_id for n in state.plan]},
            )

            # 9. COMPOSE ----------------------------------------------------------
            if not self.ablations.mathematical_structure:
                # Remove the mathematical prior at its source: the composer
                # itself must stop routing to phi-parameterised search, not
                # merely be told to ignore the result afterwards.
                if hasattr(self.skills, "mathematical_enabled"):
                    self.skills.mathematical_enabled = False
                self._ablated(state, "mathematical_structure")
            if self.ablations.skill_composition:
                state.candidates = self.skills.compose(goal_text, state)
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
            result = dict(self.executor.execute(best.action_id,
                                                {"kind": "plan", "cycle": cycle}))
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
                self._transition(
                    state, "compare", "observed outcome compared with prediction",
                    {"expected": expected.expected, "observed": observed_token,
                     "prediction_error": error,
                     "model_health": self.world_model.health().status},
                )

            # 14. METACONTROL ------------------------------------------------------------
            assessment = self._objective_bias(state, self.metacontroller.assess(state))
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
                self._learn(state, problem_class, success=True, cycle=cycle,
                            result=result)
                break
            self._learn(state, problem_class, success=False, cycle=cycle,
                        result=result)

        if solved:
            state.outcome = Outcome.SOLVED
            state.outcome_detail = "goal verified by governed execution feedback"
        elif state.outcome is None:
            state.outcome = Outcome.STALLED if executed_once else Outcome.UNEXECUTED
            state.outcome_detail = (
                "cycle budget exhausted" if executed_once
                else "no governed execution occurred"
            )
        self._transition(state, "terminate", f"episode closed: {state.outcome.value}",
                         {"outcome": state.outcome.value, "detail": state.outcome_detail})
        state.verify_transitions()
        return state

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
             "rationale": trial.rationale},
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
            return utility, 0.05 * float(len(payload))

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
             "rationale": trial.rationale},
        )

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
        self,
        state: CognitiveState,
        problem_class: str,
        *,
        success: bool,
        cycle: int,
        result: Mapping[str, Any] | None = None,
    ) -> None:
        if self.ablations.meta_learning and state.selected_strategy:
            self.metalearner.update(problem_class, state.selected_strategy, success,
                                    detail=f"cycle={cycle}")
            state.learning_updates.append(
                {"kind": "strategy", "strategy": state.selected_strategy,
                 "problem_class": problem_class, "success": success, "cycle": cycle}
            )
        # Close the episode into the governed LearningService so cognition
        # outcomes reach durable, replay-protected memory instead of
        # terminating in telemetry.  Fail-soft: a learner failure must never
        # abort an episode, but it is always recorded in the ledger.
        if self.episode_learner is not None:
            payload = dict(result or {})
            payload.setdefault("goal_met", success)
            payload.setdefault("problem_class", problem_class)
            try:
                recorded = self.episode_learner.record_episode(
                    state, success=success, cycle=cycle, result=payload
                )
            except Exception as exc:  # noqa: BLE001 - learner is advisory
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
        self._transition(
            state, "learn", "episode outcome fed back to learning",
            {"success": success, "problem_class": problem_class,
             "strategy": state.selected_strategy},
        )


__all__ = ["AblationConfig", "GeneralIntelligenceCore"]
