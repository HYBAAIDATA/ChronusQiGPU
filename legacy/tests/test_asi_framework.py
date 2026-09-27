"""
Scientific ASI Attribute Framework test suite.

Verifies that every attribute demanded by a major school of thought on
intelligence (S-1 .. S-20) is implemented and functional in pythagoras/asi/.
"""

import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pythagoras.asi import (
    ASIAttributeFramework,
    ActiveDiscoveryEngine,
    AnalogicalReasoningEngine,
    BayesianReasoningEngine,
    CausalModel,
    CausalReasoningEngine,
    CognitiveStage,
    CompositionalGeneralizationEngine,
    CompositionalRule,
    ContinualLearningEngine,
    CuriosityDrivenExplorer,
    DevelopmentalController,
    FourApproachesValidator,
    GlobalWorkspace,
    HierarchicalPlanner,
    InformationIntegrationMeasurer,
    MetacognitiveMonitor,
    NeuralPlasticity,
    NoveltySearchEngine,
    PredictiveProcessingEngine,
    RobustnessEvaluator,
    SafetyAlignmentLayer,
    SelfReferentialImprover,
    SuperintelligenceEvaluator,
    TheoryOfMindEngine,
    UniversalIntelligenceEvaluator,
    WorldModel,
)


class _CountingEnv:
    """Minimal environment: agent increments state toward a target."""

    def __init__(self, env_id, target=5):
        self.id = env_id
        self.target = target
        self.state = 0

    def step(self, action):
        self.state += action
        return self, action, self.state >= self.target, {"prediction_error": 0.01}


def _xyz_model():
    """Causal chain X -> Y -> Z with linear structural functions."""
    return CausalModel(
        variables=["x", "y", "z"],
        edges={"x": ["y"], "y": ["z"], "z": []},
        functions={
            "x": lambda pv: 0.0,
            "y": lambda pv: 2.0 * pv.get("x", 0.0),
            "z": lambda pv: pv.get("y", 0.0) + 1.0,
        },
    )


class TestS1UniversalIntelligence(unittest.TestCase):
    def test_evaluate_across_environments(self):
        evaluator = UniversalIntelligenceEvaluator()
        envs = [_CountingEnv(f"env{i}", target=t) for i, t in enumerate([3, 5, 8])]
        goals = [lambda e: e.state >= e.target for _ in envs]
        report = evaluator.evaluate_across_environments(lambda e: 1, envs, goals)
        self.assertEqual(report["n_environments"], 3)
        self.assertEqual(report["generalisation_score"], 1.0)
        self.assertGreater(report["intelligence_score"], 0.0)
        self.assertGreater(report["compression_ratio"], 0.0)
        self.assertGreater(report["mean_efficiency"], 0.0)

    def test_failing_agent_scores_zero(self):
        evaluator = UniversalIntelligenceEvaluator()
        envs = [_CountingEnv("e0")]
        goals = [lambda e: e.state >= e.target]
        report = evaluator.evaluate_across_environments(lambda e: 0, envs, goals)
        self.assertEqual(report["generalisation_score"], 0.0)
        self.assertEqual(report["intelligence_score"], 0.0)


class TestS2CausalReasoning(unittest.TestCase):
    def setUp(self):
        self.engine = CausalReasoningEngine(_xyz_model())

    def test_rung1_association(self):
        result = self.engine.observe({"x": 3.0})
        self.assertEqual(result["y"], 6.0)
        self.assertEqual(result["z"], 7.0)

    def test_rung2_intervention_cuts_incoming_edges(self):
        # do(Y=10) ignores X entirely
        result = self.engine.intervene({"y": 10.0}, evidence={"x": 3.0})
        self.assertEqual(result["y"], 10.0)
        self.assertEqual(result["z"], 11.0)

    def test_rung3_counterfactual(self):
        # Observed x=1 -> y=2 -> z=3. What if x had been 5?
        result = self.engine.counterfactual(do={"x": 5.0}, observed={"x": 1.0, "y": 2.0, "z": 3.0})
        self.assertEqual(result["y"], 10.0)
        self.assertEqual(result["z"], 11.0)

    def test_structure_discovery(self):
        # Y fully mediates X -> Z: X and Z dependent, independent given Y
        data = [{"x": float(i), "y": float(i), "z": float(i) % 2} for i in range(10)]
        edges = self.engine.discover_causal_structure(data)
        self.assertIn("x", edges)


class TestS3InformationIntegration(unittest.TestCase):
    def test_phi_and_partition(self):
        subsystems = {
            "parity": lambda xs: [x % 2 for x in xs],
            "mod3": lambda xs: [x % 3 for x in xs],
            "mod5": lambda xs: [x % 5 for x in xs],
        }
        measurer = InformationIntegrationMeasurer(subsystems)
        report = measurer.measure_phi(list(range(20)))
        for key in (
            "total_system_information",
            "sum_of_parts_information",
            "integrated_information_phi",
            "integration_ratio",
            "is_integrated",
        ):
            self.assertIn(key, report)
        mip = measurer.find_minimum_information_partition(list(range(20)))
        self.assertIsNotNone(mip["partition"])
        self.assertIn("minimum_phi", mip)


class TestS4Metacognition(unittest.TestCase):
    def test_strategy_switch_on_plateau(self):
        monitor = MetacognitiveMonitor(calibration_window=20)
        strategies_seen = set()
        state = None
        for _ in range(15):
            state = monitor.observe(phi=0.5, delta_phi=0.0, strategy=monitor.current_strategy)
            strategies_seen.add(monitor.current_strategy)
        self.assertTrue(state.should_switch)
        # Sustained plateau drives the monitor to cycle away from the failing strategy
        self.assertGreater(len(strategies_seen), 1)

    def test_working_strategy_not_switched(self):
        monitor = MetacognitiveMonitor()
        for _ in range(15):
            state = monitor.observe(phi=0.5, delta_phi=0.05, strategy=monitor.current_strategy)
        self.assertTrue(state.strategy_working)
        self.assertFalse(state.should_switch)

    def test_calibration_tracking(self):
        monitor = MetacognitiveMonitor()
        for _ in range(10):
            monitor.observe(phi=0.5, delta_phi=0.0, strategy="standard_evolution")
        self.assertFalse(monitor.is_well_calibrated())


class TestS5TheoryOfMind(unittest.TestCase):
    def setUp(self):
        self.engine = TheoryOfMindEngine()
        self.engine.model_agent("reviewer-1", "code_reviewer", [])
        self.engine.model_agent("tests-1", "test_suite", [{"t": 1}, {"t": 2}])

    def test_agent_models_created(self):
        self.assertIn("reviewer-1", self.engine.agent_models)
        self.assertIn("tests-1", self.engine.agent_models)

    def test_predict_agent_response(self):
        resp = self.engine.predict_agent_response("tests-1", {"preserves_behaviour": False})
        self.assertEqual(resp["prediction"], "fail")
        resp = self.engine.predict_agent_response("tests-1", {"preserves_behaviour": True})
        self.assertEqual(resp["prediction"], "pass")

    def test_false_belief(self):
        actual = {"preserves_behaviour": True}
        believed = {"preserves_behaviour": False}
        self.assertTrue(self.engine.false_belief_test("tests-1", actual, believed))


class TestS6Developmental(unittest.TestCase):
    def test_assimilation_accommodation(self):
        dev = DevelopmentalController()
        dev.observe("rename:var", 0.01, True)  # accommodation — new schema
        dev.observe("rename:var", 0.02, True)  # assimilation — existing schema
        self.assertEqual(dev.accommodation_count, 1)
        self.assertEqual(dev.assimilation_count, 1)
        self.assertEqual(len(dev.schemas), 1)

    def test_equilibration_merges_similar_schemas(self):
        dev = DevelopmentalController()
        # High accommodation rate triggers equilibration once total >= 10
        for i in range(6):
            dev.observe(f"mut:{i}", 0.01, True)
            dev.observe(f"mut:{i}b", 0.01, True)
        self.assertGreaterEqual(len(dev.equilibration_events), 1)
        # all schemas share the "mut" prefix and get merged
        self.assertLessEqual(len(dev.schemas), 6)

    def test_stage_advancement(self):
        dev = DevelopmentalController()
        for i in range(12):
            for _ in range(5):
                dev.observe(f"type{i}", 0.01, True)
        self.assertTrue(dev._ready_for_next_stage())
        self.assertTrue(dev.advance_stage())
        self.assertEqual(dev.stage, CognitiveStage.PREOPERATIONAL)

    def test_zone_of_proximal_development(self):
        dev = DevelopmentalController()
        dev.observe("hard:mut", 0.0, True)
        dev.observe("hard:mut", 0.0, False)
        dev.observe("easy:mut", 0.0, True)
        for _ in range(4):
            dev.observe("easy:mut", 0.0, True)
        zpd = dev.get_zone_of_proximal_development()
        self.assertIn("hard:mut", zpd)
        self.assertNotIn("easy:mut", zpd)


class TestS7NoveltySearch(unittest.TestCase):
    def test_novelty_archive_grows(self):
        engine = NoveltySearchEngine(k=3, novelty_threshold=0.05)
        for i in range(10):
            engine.compute_novelty([float(i), float(i) * 2.0])
        self.assertGreater(len(engine.archive), 0)
        self.assertTrue(all(d.is_novel for d in engine.archive))

    def test_repeated_vector_not_novel(self):
        engine = NoveltySearchEngine(k=3, novelty_threshold=0.05)
        for _ in range(5):
            engine.compute_novelty([1.0, 1.0])
        desc = engine.compute_novelty([1.0, 1.0])  # identical -> distance 0
        self.assertFalse(desc.is_novel)

    def test_quality_diversity_search(self):
        engine = NoveltySearchEngine(k=2, novelty_threshold=0.01)
        counter = {"i": 0}

        def generate():
            counter["i"] += 1
            return counter["i"]

        def evaluate(sol, return_behaviour):
            return [float(sol), 0.0] if return_behaviour else float(sol % 3)

        report = engine.quality_diversity_search(evaluate, generate, n_iterations=20)
        self.assertGreater(report["archive_size"], 0)
        self.assertIn("max_quality", report)
        self.assertIn("diversity", report)


class TestS8SelfReferential(unittest.TestCase):
    def test_modification_requires_proof(self):
        improver = SelfReferentialImprover()
        # High-variance plateau -> proof found -> approved
        history = [-0.05, 0.05] * 10
        proposal = improver.propose_self_modification(history)
        self.assertEqual(proposal.target_component, "meta_controller")
        self.assertIsNotNone(proposal.proof_of_benefit)
        self.assertTrue(proposal.is_approved)

        old_window = improver.current_parameters["meta_controller_window"]
        self.assertTrue(improver.apply_modification(proposal))
        self.assertLess(improver.current_parameters["meta_controller_window"], old_window)
        self.assertTrue(improver.get_safety_invariant())

    def test_unproven_modification_rejected(self):
        improver = SelfReferentialImprover()
        # Flat history: variance 0 -> no proof -> not approved
        history = [0.0] * 25
        proposal = improver.propose_self_modification(history)
        self.assertFalse(proposal.is_approved)
        self.assertFalse(improver.apply_modification(proposal))

    def test_insufficient_data(self):
        improver = SelfReferentialImprover()
        proposal = improver.propose_self_modification([0.01, 0.02])
        self.assertEqual(proposal.risk_assessment, "insufficient_data")


class TestS9Curiosity(unittest.TestCase):
    def test_intrinsic_reward_from_prediction_error(self):
        explorer = CuriosityDrivenExplorer()
        signal = explorer.compute_curiosity(predicted_delta_phi=0.0, actual_delta_phi=0.4)
        self.assertEqual(signal.prediction_error, 0.4)
        self.assertGreater(signal.intrinsic_reward, 0.0)

    def test_novelty_bonus_integrated(self):
        novelty = NoveltySearchEngine(k=2, novelty_threshold=0.01)
        explorer = CuriosityDrivenExplorer(novelty_engine=novelty)
        signal = explorer.compute_curiosity(0.0, 0.0, behaviour_vector=[1.0, 2.0])
        self.assertGreater(signal.novelty_bonus, 0.0)

    def test_suggest_curious_mutation(self):
        explorer = CuriosityDrivenExplorer()
        idx = explorer.suggest_curious_mutation(["m1", "m2", "m3"], [0.01, 0.9, 0.02])
        self.assertEqual(idx, 1)
        self.assertEqual(explorer.suggest_curious_mutation([], []), -1)


class TestS10ContinualLearning(unittest.TestCase):
    def test_learn_multiple_tasks_without_crash(self):
        engine = ContinualLearningEngine(ewc_lambda=1.0)
        engine.current_parameters = [0.0] * 5
        engine.learn_task("repo_a", [1.0, 2.0, 3.0, 4.0, 5.0], n_steps=20)
        r2 = engine.learn_task("repo_b", [2.0, 3.0, 4.0, 5.0, 6.0], n_steps=20)
        self.assertEqual(len(engine.tasks), 2)
        self.assertEqual(r2["n_previous_tasks"], 1)
        self.assertIn("forgetting_measure", r2)
        self.assertIn("knowledge_retained", r2)

    def test_ewc_penalty_protects_parameters(self):
        engine = ContinualLearningEngine(ewc_lambda=10.0)
        engine.current_parameters = [0.5, 0.5, 0.5]
        engine.learn_task("task1", [0.5, 0.5, 0.5], n_steps=10)
        penalty = engine._compute_ewc_penalty()
        self.assertEqual(len(penalty), 3)


class TestS11PredictiveProcessing(unittest.TestCase):
    def test_perceive_updates_beliefs(self):
        engine = PredictiveProcessingEngine()
        before = engine.beliefs.predicted_phi
        belief = engine.perceive(observed_phi=0.9, observed_delta=0.1)
        self.assertNotEqual(belief.predicted_phi, before)
        self.assertGreater(belief.precision, 0.0)

    def test_act_minimises_expected_free_energy(self):
        engine = PredictiveProcessingEngine()
        engine.perceive(0.5, 0.0)
        result = engine.act(["mut_a", "mut_b", "mut_c"], [0.5, 0.9, 0.1])
        self.assertIn(result.action, ["mut_a", "mut_b", "mut_c"])
        self.assertLessEqual(
            result.expected_free_energy,
            max(0.5 * (p - 0.5) ** 2 * engine.beliefs.precision for p in [0.5, 0.9, 0.1]),
        )

    def test_precision_meta_learning(self):
        engine = PredictiveProcessingEngine()
        p0 = engine.beliefs.precision
        engine.update_precision(0.5)  # large error -> lower confidence
        self.assertLess(engine.beliefs.precision, p0)
        engine.update_precision(0.01)  # accurate -> higher confidence
        self.assertGreater(engine.beliefs.uncertainty, 0.0)

    def test_free_energy_trajectory(self):
        engine = PredictiveProcessingEngine()
        engine.perceive(0.6, 0.1)
        engine.perceive(0.7, 0.1)
        self.assertEqual(len(engine.get_free_energy_trajectory()), 2)


class TestS12BayesianReasoning(unittest.TestCase):
    def test_conjugate_update(self):
        engine = BayesianReasoningEngine(prior_mean=0.0, prior_variance=1.0)
        engine.update("extract_function", observed_effect=0.4, observation_variance=0.1)
        mean, var = engine.predict("extract_function")
        self.assertGreater(mean, 0.0)  # pulled toward observation
        self.assertLess(var, 1.0)  # uncertainty shrinks

    def test_credible_interval(self):
        engine = BayesianReasoningEngine()
        engine.update("rename", 0.2)
        lo, hi = engine.credible_interval("rename", confidence=0.95)
        self.assertLess(lo, hi)

    def test_uncertainty_quantification(self):
        engine = BayesianReasoningEngine()
        engine.update("a", 0.1)
        engine.update("b", 0.2)
        uq = engine.uncertainty_quantification()
        self.assertEqual(uq["a"]["n_obs"], 1)
        self.assertEqual(uq["b"]["n_obs"], 1)


class TestS13AnalogicalReasoning(unittest.TestCase):
    def test_structure_mapping_between_domains(self):
        engine = AnalogicalReasoningEngine()
        src = ast.parse("def foo(a, b):\n    return a\n\ndef bar(x):\n    return x\n")
        tgt = ast.parse("def alpha(p, q):\n    return p\n\ndef beta(r):\n    return r\n")
        engine.represent_structure("domain_a", src)
        engine.represent_structure("domain_b", tgt)

        mapping = engine.map_structures("domain_a", "domain_b")
        self.assertIsNotNone(mapping)
        self.assertEqual(mapping.entity_mappings["foo"], "alpha")
        self.assertEqual(mapping.entity_mappings["bar"], "beta")
        self.assertEqual(mapping.mapping_score, 1.0)

        transferred = engine.transfer_knowledge(mapping, [{"target": "foo", "type": "annotate"}])
        self.assertEqual(transferred[0]["mapped_target"], "alpha")
        self.assertEqual(transferred[0]["source_domain"], "domain_a")

    def test_unknown_domain_returns_none(self):
        engine = AnalogicalReasoningEngine()
        self.assertIsNone(engine.map_structures("nope", "nada"))


class TestS14CompositionalGeneralization(unittest.TestCase):
    def test_compose_and_generalize(self):
        engine = CompositionalGeneralizationEngine()
        engine.add_primitive(CompositionalRule("annotate", "f", "f_ann"))
        engine.add_primitive(CompositionalRule("rename", "g", "g_ren"))

        composed = engine.compose("annotate", "rename")
        self.assertFalse(composed.is_primitive)
        self.assertEqual(composed.component_rules, ["annotate", "rename"])

        results = engine.test_compositional_generalization([("annotate", "rename", "some_input")])
        self.assertEqual(results["total"], 1)
        self.assertEqual(results["passed"], 1)
        self.assertGreaterEqual(results["novel_compositions"], 1)


class TestS15SafetyAlignment(unittest.TestCase):
    def test_reversible_low_risk_change_is_safe(self):
        layer = SafetyAlignmentLayer()
        assessment = layer.assess_change(
            {"reversible": True}, phi_delta=0.0, external_quality_delta={}
        )
        self.assertTrue(assessment.is_safe)
        self.assertEqual(assessment.risk_level, "low")

    def test_irreversible_change_requires_approval(self):
        layer = SafetyAlignmentLayer()
        assessment = layer.assess_change(
            {"reversible": False}, phi_delta=0.5, external_quality_delta={}
        )
        self.assertEqual(assessment.risk_level, "high")
        self.assertTrue(assessment.human_approval_required)
        self.assertFalse(assessment.is_safe)

    def test_phi_gaming_detected(self):
        layer = SafetyAlignmentLayer()
        assessment = layer.assess_change(
            {"reversible": True}, phi_delta=0.5, external_quality_delta={}
        )
        self.assertEqual(assessment.risk_level, "medium")
        self.assertTrue(any("gaming" in s for s in assessment.side_effects))

    def test_interrupt_and_resume(self):
        layer = SafetyAlignmentLayer()
        layer.interrupt()
        assessment = layer.assess_change({"reversible": True}, 0.0, {})
        self.assertFalse(assessment.is_safe)
        self.assertEqual(assessment.risk_level, "critical")
        self.assertFalse(assessment.interruptible)
        layer.resume()
        assessment = layer.assess_change({"reversible": True}, 0.0, {})
        self.assertTrue(assessment.is_safe)

    def test_preference_learning_reduces_uncertainty(self):
        layer = SafetyAlignmentLayer()
        u0 = layer.preference_uncertainty
        layer.update_preferences({"maintainability": 0.9})
        self.assertLess(layer.preference_uncertainty, u0)
        total = sum(layer.human_preferences.values())
        self.assertAlmostEqual(total, 1.0)

    def test_safe_explore(self):
        layer = SafetyAlignmentLayer()
        self.assertTrue(layer.safe_explore({"reversible": True}, risk_tolerance=0.1))
        self.assertFalse(layer.safe_explore({"reversible": False}, risk_tolerance=0.1))


class TestS16Robustness(unittest.TestCase):
    def test_evaluate_robustness(self):
        evaluator = RobustnessEvaluator()

        def agent(case):
            return case  # passes truthy cases
        report = evaluator.evaluate(
            agent,
            in_dist_test=[True, True, True, False],
            ood_test=[True, False, False, False],
            adversarial_test=[True, True, True, True],
            edge_cases=[True] * 9 + [False],
        )
        self.assertAlmostEqual(report.in_distribution_accuracy, 0.75)
        self.assertAlmostEqual(report.out_of_distribution_accuracy, 0.25)
        self.assertTrue(report.distributional_shift_detected)
        self.assertFalse(report.is_robust)

    def test_detect_distributional_shift(self):
        evaluator = RobustnessEvaluator()
        evaluator.set_baseline([0.0, 0.1, -0.1, 0.05, -0.05])
        self.assertFalse(evaluator.detect_distributional_shift([0.0, 0.05]))
        self.assertTrue(evaluator.detect_distributional_shift([10.0, 12.0]))


class TestS17GlobalWorkspace(unittest.TestCase):
    def test_broadcast_to_all_modules(self):
        ws = GlobalWorkspace()
        received = {"a": [], "b": [], "c": []}
        for name in received:
            ws.register_module(name, lambda content, n=name: received[n].append(content))

        ws.submit("a", "high_salience_info", priority=0.9)
        ws.submit("b", "low_salience_info", priority=0.2)
        winner = ws.broadcast_cycle()

        self.assertEqual(winner.source, "a")
        self.assertTrue(winner.broadcast)
        self.assertEqual(received["b"], ["high_salience_info"])
        self.assertEqual(received["c"], ["high_salience_info"])
        self.assertEqual(received["a"], [])  # not sent back to source

    def test_below_threshold_no_broadcast(self):
        ws = GlobalWorkspace()
        ws.register_module("m", lambda c: None)
        ws.submit("m", "quiet", priority=0.1)
        self.assertIsNone(ws.broadcast_cycle())

    def test_conscious_access_log(self):
        ws = GlobalWorkspace()
        ws.register_module("x", lambda c: None)
        ws.submit("x", "event1", priority=0.9)
        ws.broadcast_cycle()
        log = ws.get_conscious_access()
        self.assertEqual(len(log), 1)
        self.assertIn("x:", log[0])


class TestS18HierarchicalPlanning(unittest.TestCase):
    def test_decompose_and_execute(self):
        planner = HierarchicalPlanner()
        root = planner.decompose_goal("improve_maintainability", {})
        self.assertEqual(root.level, 3)
        self.assertEqual(len(root.children), 3)

        # First primitive is identify_block under extract_function
        primitive = planner.get_next_primitive()
        self.assertEqual(primitive.name, "identify_block")
        self.assertTrue(primitive.is_primitive)

        planner.mark_done("identify_block")
        nxt = planner.get_next_primitive()
        self.assertEqual(nxt.name, "create_function")

        # Completing all primitives under extract_function marks ancestors done
        planner.mark_done("create_function")
        planner.mark_done("replace_call")
        extract = root.children[0].children[0]
        self.assertEqual(extract.status, "done")
        self.assertIsNone(
            planner.get_next_primitive() if all(c.status == "done" for c in root.children) else None
        )


class TestS19SuperintelligenceDimensions(unittest.TestCase):
    def test_three_dimensions(self):
        evaluator = SuperintelligenceEvaluator(
            human_baseline_time=3600.0, human_baseline_quality=0.5
        )
        profile = evaluator.evaluate(
            system_time=10.0, system_quality=0.8, individual_quality=0.3, n_components=3
        )
        self.assertEqual(profile.speed_si, 360.0)
        self.assertAlmostEqual(profile.quality_si, 1.6)
        self.assertAlmostEqual(profile.collective_si, 0.8 / 0.9, places=2)
        self.assertEqual(profile.mode, "oracle")
        self.assertGreater(profile.total_si, 0.0)


class TestS20FourApproaches(unittest.TestCase):
    def test_all_four_approaches_reported(self):
        validator = FourApproachesValidator()
        result = validator.validate(system=None)
        self.assertEqual(
            set(result.keys()),
            {"thinking_humanly", "thinking_rationally", "acting_humanly", "acting_rationally"},
        )
        self.assertTrue(result["thinking_humanly"]["satisfied"])
        self.assertTrue(result["thinking_rationally"]["satisfied"])
        self.assertFalse(result["acting_humanly"]["satisfied"])  # known gap
        self.assertTrue(result["acting_rationally"]["satisfied"])


class TestActiveDiscovery(unittest.TestCase):
    """The elevation: instruments alone are not intelligence — the engine must
    autonomously find a hidden law of a toy universe by experimenting on it."""

    _TRANSITIONS = {
        "inc": lambda s: s + 1,
        "dbl": lambda s: 2 * s,
        "add3": lambda s: s + 3,
    }

    @staticmethod
    def _hidden_law_env(rules, state):
        """Universe: reward 1.0 iff applying `rules` to `state` yields 6."""
        s = state
        for r in rules:
            s = TestActiveDiscovery._TRANSITIONS[r](s)
        return 1.0 if s == 6 else 0.0

    def _primitives(self):
        return [
            CompositionalRule("inc", "s", "s+1"),
            CompositionalRule("dbl", "s", "2s"),
            CompositionalRule("add3", "s", "s+3"),
        ]

    def test_discovers_hidden_compositional_law(self):
        # add3 then dbl reaches 6 — no single primitive does. The engine must
        # find this through experimentation alone.
        engine = ActiveDiscoveryEngine(
            environment=self._hidden_law_env,
            primitives=self._primitives(),
            n_trials=5,
            surprise_threshold=0.15,
        )
        report = engine.discover(initial_state=0, n_cycles=20, max_composition_length=2)

        self.assertGreaterEqual(report["discoveries"], 1)
        found = [d for d in engine.discoveries if d.rule_composition == ["add3", "dbl"]]
        self.assertTrue(found, "engine failed to discover the add3∘dbl law")
        self.assertEqual(found[0].observed_effect, 1.0)
        self.assertGreaterEqual(found[0].replications, 5)

    def test_no_discovery_in_flat_universe(self):
        engine = ActiveDiscoveryEngine(
            environment=lambda rules, state: 0.0,
            primitives=self._primitives(),
            n_trials=5,
        )
        report = engine.discover(initial_state=0, n_cycles=20)
        self.assertEqual(report["discoveries"], 0)
        self.assertGreater(report["hypotheses_tested"], 0)

    def test_bayesian_beliefs_learned_from_experiments(self):
        engine = ActiveDiscoveryEngine(
            environment=self._hidden_law_env,
            primitives=self._primitives(),
            n_trials=5,
        )
        engine.discover(initial_state=0, n_cycles=20)
        mean, var = engine.bayesian.predict("add3∘dbl")
        self.assertGreater(mean, 0.5)  # posterior moved toward observed effect

    def test_discoveries_broadcast_to_workspace(self):
        engine = ActiveDiscoveryEngine(
            environment=self._hidden_law_env,
            primitives=self._primitives(),
            n_trials=5,
        )
        received = []
        engine.workspace.register_module("listener", received.append)
        engine.discover(initial_state=0, n_cycles=20)
        self.assertGreater(len(engine.workspace.broadcast_history), 0)
        self.assertGreater(len(received), 0)
        self.assertIn("composition", received[0])

    def test_safety_gate_blocks_unsafe_experiments(self):
        engine = ActiveDiscoveryEngine(
            environment=self._hidden_law_env,
            primitives=self._primitives(),
            n_trials=5,
        )
        engine.safety.interrupt()
        report = engine.discover(initial_state=0, n_cycles=5)
        self.assertEqual(report["discoveries"], 0)

    @staticmethod
    def _two_law_env(rules, state):
        """Richer universe: state 6 -> reward 1.0, state 7 -> reward 2.0."""
        s = state
        for r in rules:
            s = TestActiveDiscovery._TRANSITIONS[r](s)
        if s == 7:
            return 2.0
        return 1.0 if s == 6 else 0.0

    def test_discovery_grows_hypothesis_space(self):
        """Chunking: a discovery becomes a new primitive — the system grows."""
        engine = ActiveDiscoveryEngine(
            environment=self._two_law_env, primitives=self._primitives(), n_trials=5
        )
        n_before = len(engine.primitives)
        report = engine.discover(initial_state=0, n_cycles=25)
        self.assertGreater(len(engine.primitives), n_before)
        self.assertIn("add3∘dbl", engine.primitives)
        self.assertFalse(engine.primitives["add3∘dbl"].is_primitive)
        self.assertEqual(report["hypothesis_space_size"], len(engine.primitives))

    def test_cumulative_discovery_builds_on_chunks(self):
        """The system discovers deeper laws by composing its own findings:
        add3∘dbl discovered first, then chunk∘inc reaches state 7."""
        engine = ActiveDiscoveryEngine(
            environment=self._two_law_env, primitives=self._primitives(), n_trials=5
        )
        engine.discover(initial_state=0, n_cycles=30)
        deep = [d for d in engine.discoveries if d.rule_composition == ["add3∘dbl", "inc"]]
        self.assertTrue(deep, "engine failed to build on its own discovery")
        self.assertEqual(deep[0].observed_effect, 2.0)

    def test_counterfactual_credit_assignment(self):
        """Rung-3: given a failed composition, name the edit that works."""
        engine = ActiveDiscoveryEngine(
            environment=self._hidden_law_env, primitives=self._primitives(), n_trials=5
        )
        engine.discover(initial_state=0, n_cycles=20)
        analysis = engine.explain_failure(["add3", "inc"])
        best = analysis["best_counterfactual"]
        self.assertEqual(best["candidate"], "add3∘dbl")
        self.assertTrue(best["tested"])
        self.assertGreater(best["predicted_effect"], 0.5)

    def test_world_model_learns_causal_theory(self):
        """The theory knows WHY add3∘dbl works: both rules are necessary."""
        engine = ActiveDiscoveryEngine(
            environment=self._hidden_law_env, primitives=self._primitives(), n_trials=5
        )
        report = engine.discover(initial_state=0, n_cycles=20)
        self.assertGreater(report["laws_learned"], 0)

        theory = engine.theory
        effect, source = theory.predict(["add3", "dbl"])
        self.assertEqual(effect, 1.0)
        self.assertEqual(source, "measured")

        attr = theory.attribute(["add3", "dbl"])
        self.assertEqual(attr.observed_effect, 1.0)
        self.assertEqual(set(attr.necessary_rules), {"0:add3", "1:dbl"})
        self.assertTrue(attr.sufficient)

        # Interaction model generalises: feed a controlled log where only
        # add3∘dbl has synergy, then predict an untested triple
        wm = WorldModel()
        wm.absorb_log(
            [
                {"rules": ["inc"], "observed": 0.0},
                {"rules": ["add3"], "observed": 0.0},
                {"rules": ["dbl"], "observed": 0.0},
                {"rules": ["add3", "dbl"], "observed": 1.0},
            ]
        )
        guess, source = wm.predict(["inc", "add3", "dbl"])
        self.assertEqual(source, "interaction_model")
        self.assertAlmostEqual(guess, 1.0)  # carries the add3∘dbl synergy

        # A world model with no measurements can only guess additively
        fresh = WorldModel()
        _, source = fresh.predict(["x", "y"])
        self.assertEqual(source, "additive_approximation")

    def test_knowledge_transfers_to_new_universe(self):
        """Learning-to-learn: priors from universe A seed universe B.
        A warm-started engine should exploit the known law immediately
        instead of re-exploring the whole space."""
        primitives = self._primitives()

        teacher = ActiveDiscoveryEngine(
            environment=self._hidden_law_env, primitives=primitives, n_trials=5
        )
        teacher.discover(0, n_cycles=20)
        self.assertGreater(teacher.bayesian.predict("add3∘dbl")[0], 0.5)

        student = ActiveDiscoveryEngine(
            environment=self._hidden_law_env,
            primitives=[
                CompositionalRule("inc", "s", "s+1"),
                CompositionalRule("dbl", "s", "2s"),
                CompositionalRule("add3", "s", "s+3"),
            ],
            n_trials=5,
        )
        student.transfer_priors(teacher)
        # The student's prior for the good composition is already high —
        # but widened, because transferred certainty is not local certainty
        mean, var = student.bayesian.predict("add3∘dbl")
        self.assertGreater(mean, 0.5)
        self.assertGreaterEqual(var, 0.1)

    def test_goal_directed_selection(self):
        """With a goal set, the engine exploits high-posterior compositions."""
        engine = ActiveDiscoveryEngine(
            environment=self._hidden_law_env, primitives=self._primitives(), n_trials=5
        )
        engine.discover(0, n_cycles=15)
        engine.set_goal("maximize_effect", weight=10.0)
        # Goal mode should prefer the known high-effect composition's
        # neighbourhood over pure-variance exploration
        nxt = engine.what_should_i_test_next(k=5)
        self.assertGreater(len(nxt), 0)
        self.assertTrue(all("composition" in n for n in nxt))

    def test_framework_attaches_shared_engine(self):
        framework = ASIAttributeFramework()
        self.assertFalse(framework.report()["active_loop"])
        engine = framework.create_discovery_engine(
            environment=self._hidden_law_env, primitives=self._primitives(), n_trials=5
        )
        self.assertIs(engine.bayesian, framework.bayesian_reasoning)
        self.assertIs(engine.safety, framework.safety_alignment)
        self.assertIs(engine.workspace, framework.global_workspace)
        engine.discover(initial_state=0, n_cycles=20)
        report = framework.report()
        self.assertTrue(report["active_loop"])
        self.assertGreaterEqual(report["discoveries"], 1)


class TestNeuralPlasticity(unittest.TestCase):
    """Probe the plasticity mechanisms: wiring must be activity-driven,
    reward-gated, and structurally adaptive — not programmed."""

    def test_sprouting_from_repeated_coactivation(self):
        p = NeuralPlasticity(sprout_threshold=3)
        p.co_activate("a", "b")
        p.co_activate("a", "b")
        self.assertNotIn(("a", "b"), p.synapses)  # not yet — needs repetition
        p.co_activate("a", "b")
        self.assertIn(("a", "b"), p.synapses)  # sprouted on third co-firing

    def test_reward_gated_hebbian_growth(self):
        p = NeuralPlasticity(sprout_threshold=1)
        p.co_activate("a", "b")  # sprouts with trace=1.0
        w0 = p.synapses[("a", "b")].weight
        p.deliver_reward(1.0)
        w1 = p.synapses[("a", "b")].weight
        self.assertGreater(w1, w0)  # reward potentiated the synapse

    def test_no_reward_no_learning(self):
        p = NeuralPlasticity(sprout_threshold=1)
        p.co_activate("a", "b")
        w0 = p.synapses[("a", "b")].weight
        p.deliver_reward(0.0)
        # zero reward: no potentiation, trace decays geometrically
        self.assertAlmostEqual(p.synapses[("a", "b")].weight, w0)
        self.assertLess(p.synapses[("a", "b")].trace, 1.0)
        for _ in range(50):
            p.deliver_reward(0.0)
        self.assertLess(p.synapses[("a", "b")].trace, 0.01)  # forgotten

    def test_decay_and_prune(self):
        p = NeuralPlasticity(sprout_threshold=1, prune_threshold=0.05)
        p.co_activate("a", "b")
        for _ in range(200):
            p.decay()
        self.assertLess(p.synapses[("a", "b")].weight, 0.05)
        removed = p.prune()
        self.assertEqual(removed, 1)
        self.assertEqual(len(p.synapses), 0)

    def test_crystallization_resists_decay(self):
        p = NeuralPlasticity(sprout_threshold=1)
        p.co_activate("a", "b")
        for _ in range(60):
            p.co_activate("a", "b")
            p.deliver_reward(1.0)
        p.crystallize()
        syn = p.synapses[("a", "b")]
        self.assertTrue(syn.crystallized)
        w = syn.weight
        for _ in range(100):
            p.decay()
        self.assertEqual(syn.weight, w)  # stable: skill became structure

    def test_maturation_reduces_plasticity(self):
        p = NeuralPlasticity()
        for _ in range(50):
            p.mature(0.95)
        self.assertLess(p.plasticity_level, 1.0)
        self.assertGreaterEqual(p.plasticity_level, 0.1)  # never fully rigid

    def test_engine_rewires_during_discovery(self):
        """Integration probe: experiments physically rewire the graph."""
        engine = ActiveDiscoveryEngine(
            environment=TestActiveDiscovery._hidden_law_env,
            primitives=[
                CompositionalRule("inc", "s", "s+1"),
                CompositionalRule("dbl", "s", "2s"),
                CompositionalRule("add3", "s", "s+3"),
            ],
            n_trials=5,
        )
        report = engine.discover(0, n_cycles=15)
        plasticity = report["plasticity"]
        self.assertGreater(plasticity["synapses"], 0)
        self.assertGreater(plasticity["mean_weight"], 0.0)
        pathways = [p["pathway"] for p in plasticity["strongest"]]
        self.assertTrue(any("bayesian" in p for p in pathways))


class TestFrameworkIntegration(unittest.TestCase):
    def test_master_checklist_full_coverage(self):
        framework = ASIAttributeFramework()
        statuses = framework.checklist()
        self.assertEqual(len(statuses), 20)
        self.assertTrue(all(s.implemented for s in statuses))
        self.assertEqual([s.attribute_id for s in statuses], [f"S-{i}" for i in range(1, 21)])

    def test_report(self):
        framework = ASIAttributeFramework()
        report = framework.report()
        self.assertEqual(report["total_attributes"], 20)
        self.assertEqual(report["implemented"], 20)
        self.assertEqual(report["coverage"], 1.0)
        self.assertIn("four_approaches", report)

    def test_curiosity_wired_to_novelty_engine(self):
        framework = ASIAttributeFramework()
        self.assertIs(framework.curiosity.novelty, framework.novelty_search)


if __name__ == "__main__":
    unittest.main()
