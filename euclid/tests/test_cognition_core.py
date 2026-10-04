"""Deterministic acceptance tests for the EUCLID cognition loop core.

All runs use an injected fixed clock and deterministic baselines; no network,
no I/O outside the evidence chain, no randomness.
"""
from __future__ import annotations

import unittest

from euclid.contracts import Authority
from euclid.evidence import EvidenceChain
from euclid.governance import Delegator, Organ, OrganRegistry
from euclid.rights import RightsLedger

from euclid.cognition import (
    AblationConfig,
    AnalogyStatus,
    BanditMetaLearner,
    CallbackExecutor,
    CognitiveState,
    ConsequenceDeducer,
    DelegatorExecutor,
    DivergenceDiscriminator,
    EpistemicStatus,
    EvidenceItem,
    EvidenceOrigin,
    GeneralIntelligenceCore,
    HierarchicalPlanner,
    InMemoryMemorySystem,
    MemoryKind,
    Outcome,
    RuleAbducer,
    SignalMetaController,
    StructuralAnalogyEngine,
    TableWorldModel,
    WeightedObjective,
    neutral_order,
    phi_order,
)
from euclid.cognition.interfaces import MemoryItem

FIXED_CLOCK = lambda: 1700000000.0  # noqa: E731 - deterministic test clock

STRUCTURE = frozenset({"rel:dependency-chain", "rel:action-outcome"})

EXPLANATIONS = {
    "mechanistic-align": {"probe": "P", "align": "S"},
    "confound-decoy": {"probe": "P", "align": "F"},
}

WEIGHTS = {
    "correctness_estimate": 0.5,
    "cost": -0.1,
    "uncertainty": -0.2,
    "novelty": 0.05,
    "transfer_value": 0.1,
}


class SyntheticDomain:
    """Hidden-rule environment: probes inform; only 'align' plans succeed."""

    def __init__(self, *, succeed_on_plan: bool = True) -> None:
        self.succeed_on_plan = succeed_on_plan
        self.calls: list[tuple[str, str]] = []

    def __call__(self, action: str, payload: dict) -> dict:
        kind = str(payload.get("kind", ""))
        self.calls.append((action, kind))
        observation = {"probe": "P", "align": "S", "decoy": "D"}.get(action, "null")
        goal_met = (
            kind == "plan" and action == "align" and self.succeed_on_plan
        )
        return {"observation": observation, "goal_met": goal_met}


def build_core(
    domain,
    *,
    ablations: AblationConfig | None = None,
    executor=None,
    memory: InMemoryMemorySystem | None = None,
    evidence: EvidenceChain | None = None,
    **extra,
) -> GeneralIntelligenceCore:
    from euclid.cognition import CandidateAction, StaticSkillComposer
    skills = StaticSkillComposer([
        CandidateAction(
            "align", "align the dependency chain", origin="skill:aligner",
            features={"correctness_estimate": 0.8, "cost": 0.2,
                      "uncertainty": 0.3, "novelty": 0.1, "transfer_value": 0.4},
        ),
        CandidateAction(
            "decoy", "surface-similar decoy", origin="skill:decoy",
            features={"correctness_estimate": 0.2, "cost": 0.2,
                      "uncertainty": 0.6, "novelty": 0.0, "transfer_value": 0.0},
        ),
    ])
    return GeneralIntelligenceCore(
        world_model=TableWorldModel(),
        memory=memory or InMemoryMemorySystem(),
        analogy=StructuralAnalogyEngine(),
        abducer=RuleAbducer(EXPLANATIONS),
        deducer=ConsequenceDeducer(EXPLANATIONS),
        discriminator=DivergenceDiscriminator(),
        metacontroller=SignalMetaController(),
        metalearner=BanditMetaLearner(),
        planner=HierarchicalPlanner(),
        skills=skills,
        objective=WeightedObjective(WEIGHTS),
        executor=executor if executor is not None else CallbackExecutor(domain),
        evidence=evidence or EvidenceChain(),
        clock=FIXED_CLOCK,
        ablations=ablations,
        **extra,
    )


PROBLEM = {
    "problem_id": "novel-001",
    "goal": "align the chain",
    "problem_class": "chain-alignment",
    "structure": sorted(STRUCTURE),
    "surface": ["chain", "align", "vertex"],
    "observations": ["link-0 precedes link-1", "align moves the chain"],
}


class TestPrimaryLoop(unittest.TestCase):
    def test_full_loop_solves_novel_problem(self) -> None:
        domain = SyntheticDomain()
        evidence = EvidenceChain()
        state = build_core(domain, evidence=evidence).solve(PROBLEM)

        self.assertEqual(state.outcome, Outcome.SOLVED, state.outcome_detail)
        # interventions (evidence) precede the plan execution (goal attempt)
        kinds = [kind for _, kind in domain.calls]
        self.assertIn("intervention", kinds)
        self.assertIn("plan", kinds)
        self.assertLess(kinds.index("intervention"), kinds.index("plan"))

        phases = [t.phase for t in state.transitions]
        for required in (
            "represent", "retrieve", "analogy", "abduce", "deduce",
            "discriminate", "hypothesis-update", "strategy", "plan",
            "compose", "imagine", "rank", "execute", "compare",
            "metacontrol", "learn", "terminate",
        ):
            self.assertIn(required, phases, f"missing phase {required}")
        # every transition is mirrored into the shared evidence chain
        cognition_records = [
            r for r in evidence.records if r.kind.startswith("cognition-")
        ]
        self.assertEqual(len(cognition_records), len(state.transitions))
        evidence.verify()
        state.verify_transitions()

    def test_confirmed_hypothesis_is_the_true_rule(self) -> None:
        state = build_core(SyntheticDomain()).solve(PROBLEM)
        by_id = {h.hypothesis_id: h for h in state.hypotheses}
        self.assertEqual(by_id["mechanistic-align"].status.value, "confirmed")
        self.assertEqual(by_id["confound-decoy"].status.value, "refuted")

    def test_competition_maintained_until_discrimination(self) -> None:
        state = build_core(SyntheticDomain()).solve(PROBLEM)
        abduce_index = next(
            i for i, t in enumerate(state.transitions) if t.phase == "abduce"
        )
        update_index = next(
            i for i, t in enumerate(state.transitions)
            if t.phase == "hypothesis-update"
        )
        self.assertLess(abduce_index, update_index)
        abduce = state.transitions[abduce_index]
        self.assertGreaterEqual(len(abduce.details["hypotheses"]), 2)


class TestStateIntegrity(unittest.TestCase):
    def test_serialise_restore_round_trip_and_tamper_rejection(self) -> None:
        state = build_core(SyntheticDomain()).solve(PROBLEM)
        payload = state.to_payload()
        restored = CognitiveState.from_payload(payload, clock=FIXED_CLOCK)
        self.assertEqual(restored.to_payload(), payload)

        tampered = dict(payload)
        tampered["outcome"] = "aborted"
        with self.assertRaises(ValueError):
            CognitiveState.from_payload(tampered, clock=FIXED_CLOCK)

    def test_replay_determinism(self) -> None:
        first = build_core(SyntheticDomain()).solve(PROBLEM).to_payload()
        second = build_core(SyntheticDomain()).solve(PROBLEM).to_payload()
        self.assertEqual(first["seal"], second["seal"])

    def test_imagined_evidence_can_never_be_observed(self) -> None:
        with self.assertRaises(ValueError):
            EvidenceItem(
                "bad-1", EvidenceOrigin.IMAGINED, EpistemicStatus.KNOWN,
                {"rollout": "fake"}, source="test", uncertainty=0.0,
            )
        state = build_core(SyntheticDomain()).solve(PROBLEM)
        for item in state.evidence_items:
            if item.origin is EvidenceOrigin.IMAGINED:
                self.assertNotEqual(item.status, EpistemicStatus.KNOWN)
        # rollout predictions exist and are flagged imagined
        imagined = [p for p in state.predictions if p.imagined]
        self.assertTrue(imagined)


class TestMetacognitionAndReplanning(unittest.TestCase):
    def test_replan_on_prediction_error_then_recover(self) -> None:
        domain = SyntheticDomain()
        # first plan execution reports a mismatching observation, then recovers
        original = domain.__call__
        holder = {"failed": False}

        def flaky(action, payload):
            result = original(action, payload)
            if payload.get("kind") == "plan" and not holder["failed"]:
                holder["failed"] = True
                return {"observation": "UNEXPECTED", "goal_met": False}
            return result

        state = build_core(domain, executor=CallbackExecutor(flaky)).solve(PROBLEM)
        self.assertEqual(state.outcome, Outcome.SOLVED, state.outcome_detail)
        self.assertTrue(state.replanning_events, "expected a replanning event")
        decisions = [d["action"] for d in state.control_decisions]
        self.assertIn("replan", decisions)

    def test_stall_is_explicit_not_opaque(self) -> None:
        domain = SyntheticDomain(succeed_on_plan=False)
        state = build_core(domain).solve(PROBLEM)
        self.assertIn(state.outcome, (Outcome.STALLED, Outcome.ABORTED))
        self.assertNotEqual(state.outcome, Outcome.SOLVED)
        self.assertTrue(state.outcome_detail)

    def test_no_executor_fails_closed(self) -> None:
        domain = SyntheticDomain()
        core = build_core(domain, executor=None)
        # build_core substitutes CallbackExecutor when None; construct directly
        core.executor = None
        state = core.solve(PROBLEM)
        self.assertEqual(state.outcome, Outcome.UNEXECUTED)
        self.assertEqual(domain.calls, [], "no execution may occur without a boundary")


class TestGovernedExecutionBoundary(unittest.TestCase):
    def test_delegator_executor_requires_rights_grant(self) -> None:
        evidence = EvidenceChain()
        rights = RightsLedger("creator-1", evidence)
        registry = OrganRegistry()
        domain = SyntheticDomain()
        registry.register(Organ(
            "cognition-executor", frozenset({"act"}), Authority.MUTATE_WORLD,
            lambda request: domain(request["action"], request["payload"]),
        ))
        delegator = Delegator(registry, evidence, rights)
        executor = DelegatorExecutor(delegator, "cognition-executor", "act")
        with self.assertRaises(PermissionError):
            executor.execute("align", {"kind": "plan", "cycle": 0})

        rights.grant("creator-1", "cognition-executor", "act", "dispatch")
        result = executor.execute("align", {"kind": "plan", "cycle": 0})
        self.assertTrue(result["goal_met"])


class TestAblations(unittest.TestCase):
    def test_ablation_is_recorded_and_fail_closed(self) -> None:
        ablations = AblationConfig(
            world_model=False, analogy=False, causal_reasoning=False,
            meta_learning=False, skill_composition=False, replanning=False,
        )
        state = build_core(SyntheticDomain(), ablations=ablations).solve(PROBLEM)
        self.assertIn("world_model:deduction", state.ablations)
        self.assertIn("analogy", state.ablations)
        self.assertIn("causal_reasoning", state.ablations)
        phases = [t.phase for t in state.transitions]
        self.assertIn("ablated", phases)
        self.assertNotIn("imagine", phases)
        # ablated runs still terminate explicitly, never silently
        self.assertIsNotNone(state.outcome)


class TestAnalogyDiscipline(unittest.TestCase):
    def test_deep_analogy_candidate_superficial_rejected(self) -> None:
        memory = InMemoryMemorySystem()
        memory.store(MemoryItem(
            "deep-1", MemoryKind.EPISODIC,
            {"surface": ["unrelated", "vocabulary"]},
            provenance="episode:prior-domain",
            structural_features=frozenset(
                {"rel:dependency-chain", "rel:action-outcome"}
            ),
        ))
        memory.store(MemoryItem(
            "shallow-1", MemoryKind.EPISODIC,
            {"surface": ["chain", "align", "vertex"]},
            provenance="episode:surface-twin",
            structural_features=frozenset({"rel:unrelated"}),
        ))
        engine = StructuralAnalogyEngine(min_overlap=0.5)
        mappings = engine.find(
            STRUCTURE, memory.retrieve(STRUCTURE), frozenset({"chain", "align", "vertex"})
        )
        by_source = {m.source_ref: m for m in mappings}
        self.assertEqual(by_source["deep-1"].status, AnalogyStatus.CANDIDATE)
        self.assertEqual(by_source["shallow-1"].status, AnalogyStatus.REJECTED)
        self.assertIn("superficial", by_source["shallow-1"].rationale)


class TestMetaLearningGuards(unittest.TestCase):
    def test_negative_transfer_guard(self) -> None:
        learner = BanditMetaLearner()
        for _ in range(3):
            learner.update("class-A", "rollout-search-execute", True)
        choice = learner.select_strategy(
            "class-B", ("analogy-causal-plan", "rollout-search-execute")
        )
        self.assertEqual(choice.strategy_id, "analogy-causal-plan")
        self.assertIn("negative-transfer guard", choice.basis)
        # and within the trained class the learned preference is used
        trained = learner.select_strategy(
            "class-A", ("analogy-causal-plan", "rollout-search-execute")
        )
        self.assertEqual(trained.strategy_id, "rollout-search-execute")


class TestPhiScheduleHonesty(unittest.TestCase):
    def test_phi_order_is_a_deterministic_permutation(self) -> None:
        self.assertEqual(sorted(phi_order(64)), neutral_order(64))
        self.assertEqual(phi_order(64), phi_order(64))
        self.assertNotEqual(phi_order(64), neutral_order(64))

    def test_phi_order_is_classified_exploratory(self) -> None:
        from euclid.cognition.phi_schedule import EVIDENCE_CLASS
        self.assertEqual(EVIDENCE_CLASS, "exploratory-parametric")


class TestObjectiveAuditability(unittest.TestCase):
    def test_weights_recorded_and_bad_weights_rejected(self) -> None:
        with self.assertRaises(ValueError):
            WeightedObjective({"correctness_estimate": 0.0})
        with self.assertRaises(ValueError):
            WeightedObjective({})
        state = build_core(SyntheticDomain()).solve(PROBLEM)
        for candidate in state.candidates:
            self.assertEqual(dict(candidate.weights_used), WEIGHTS)
            self.assertIsNotNone(candidate.total)


class TestProductionComponentWiring(unittest.TestCase):
    """Regression guard for the EuclidRuntime._compose_cognition seam.

    The production runtime constructs GeneralIntelligenceCore with
    episode_learner, representation_controller and objective_controller.
    The core must accept them and exercise each through measured,
    transition-recorded signals (a scrape/merge once shipped a runtime
    whose constructor call the core could not accept).
    """

    def test_production_components_accepted_and_exercised(self) -> None:
        from euclid.cognition.adaptive import (
            ObjectiveController,
            RepresentationController,
        )

        episodes: list[tuple[bool, int]] = []

        class _RecordingEpisodeLearner:
            def record_episode(self, state, *, success, cycle, result):
                episodes.append((bool(success), int(cycle)))
                state.learning_updates.append(
                    {"kind": "canonical-learning-service", "cycle": int(cycle)}
                )

        core = build_core(
            SyntheticDomain(),
            episode_learner=_RecordingEpisodeLearner(),
            representation_controller=RepresentationController(),
            objective_controller=ObjectiveController(),
        )
        state = core.solve(PROBLEM)
        phases = [t.phase for t in state.transitions]

        # Episode outcomes were closed into the learning channel.
        self.assertTrue(episodes)
        # Representation selection ran a measured, recorded trial.
        represent = next(t for t in state.transitions if t.phase == "represent")
        trial = represent.details.get("representation_trial")
        self.assertIsNotNone(trial)
        self.assertIn("baseline_utility", trial)
        self.assertIn("candidate_utility", trial)
        self.assertIn("cost", trial)
        # Intermediate objectives were derived from measured signals.
        self.assertIn("objectives", phases)


class TestProductionReviewRegressions(unittest.TestCase):
    def test_malformed_source_retains_literal_representation(self) -> None:
        from euclid.cognition.adaptive import RepresentationController

        problem = dict(PROBLEM, initial_code="def broken(:\n    pass")
        state = build_core(
            SyntheticDomain(), representation_controller=RepresentationController()
        ).solve(problem)
        self.assertEqual(state.representation["initial_code"], problem["initial_code"])
        self.assertIn("represent", [item.phase for item in state.transitions])

    def test_accepted_representation_is_canonical_not_dead_overlay(self) -> None:
        from euclid.cognition.adaptive import RepresentationTrial

        class _Controller:
            def select(self, problem, evaluator):
                return RepresentationTrial(
                    "repr-test", "graph", {"edges": [("a", "b")]},
                    0.0, 1.0, 0.1, True, "measured improvement",
                )

        state = build_core(
            SyntheticDomain(), representation_controller=_Controller()
        ).solve(PROBLEM)
        self.assertEqual(state.representation["edges"], [("a", "b")])
        self.assertEqual(state.representation["representation_overlay"]["edges"], [("a", "b")])

    def test_objectives_feed_the_next_planning_decision(self) -> None:
        from euclid.cognition.adaptive import ObjectiveController
        from euclid.cognition.baselines import HierarchicalPlanner

        goals = []

        class _Planner(HierarchicalPlanner):
            def plan(self, goal, state):
                goals.append(goal)
                return super().plan(goal, state)

        calls = {"plans": 0}

        def delayed(action, payload):
            if payload.get("kind") == "plan":
                calls["plans"] += 1
            return {
                "observation": "UNEXPECTED" if calls["plans"] == 1 else "S",
                "goal_met": calls["plans"] >= 2,
            }

        core = build_core(
            SyntheticDomain(), executor=CallbackExecutor(delayed),
            objective_controller=ObjectiveController(),
        )
        core.planner = _Planner()
        state = core.solve(PROBLEM)
        self.assertIn("objective-applied", [item.phase for item in state.transitions])
        self.assertTrue(any("intermediate objectives:" in item for item in goals[1:]))

    def test_persistence_bookkeeping_does_not_double_count_failure(self) -> None:
        controller = SignalMetaController(stall_after=2)
        state = CognitiveState("counting", {"structure": []}, clock=FIXED_CLOCK)
        state.learning_updates.extend([
            {"kind": "canonical-learning-service", "success": False,
             "counts_for_control": False},
            {"kind": "strategy", "success": False},
        ])
        assessment = controller.assess(state)
        self.assertEqual(assessment.action, "continue")
        self.assertEqual(assessment.signals["consecutive_failures"], 1.0)

    def test_terminal_halt_still_closes_learning(self) -> None:
        from euclid.cognition.interfaces import ControlAssessment

        episodes = []

        class _Halt:
            def assess(self, state):
                return ControlAssessment("halt_stalled", "test halt", {})

        class _Learner:
            def record_episode(self, state, *, success, cycle, result):
                episodes.append((success, cycle, dict(result)))

        core = build_core(SyntheticDomain(succeed_on_plan=False), episode_learner=_Learner())
        core.metacontroller = _Halt()
        state = core.solve(PROBLEM)
        self.assertTrue(episodes)
        learn_index = max(i for i, item in enumerate(state.transitions) if item.phase == "learn")
        terminate_index = next(i for i, item in enumerate(state.transitions) if item.phase == "terminate")
        self.assertLess(learn_index, terminate_index)


if __name__ == "__main__":
    unittest.main()
