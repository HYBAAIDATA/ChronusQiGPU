from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from euclid.cognition.adaptive import (
    CapabilityLifecycle,
    NoveltyArchive,
    ObjectiveController,
    PersistentStrategyLearner,
    RepresentationController,
)
from euclid.cognition.experiments import (
    BenchmarkProgramme,
    BenchmarkTask,
    TrialResult,
    adversarial_evaluation_tasks,
)
from euclid.cognition.math_experiments import paired_ordering_experiment


class RepresentationAndObjectiveTests(unittest.TestCase):
    def test_representation_changes_only_on_measured_net_gain(self):
        problem = {
            "structure": ["rel:a-b"],
            "observations": ["a -> b"],
            "initial_code": "def f(x): return x",
        }
        controller = RepresentationController()
        evidence = {
            "literal": (0.4, 0.1),
            "relational": (0.5, 0.3),
            "graph": (0.9, 0.2),
            "source-dependency": (0.6, 0.4),
        }
        trial = controller.select(problem, lambda kind, _: evidence[kind])
        self.assertTrue(trial.accepted)
        self.assertEqual(trial.kind, "graph")

        tied = controller.select(problem, lambda kind, _: (0.5, 0.1))
        self.assertFalse(tied.accepted, "complexity cannot be rewarded by itself")
        self.assertEqual(tied.kind, "literal")

    def test_objective_proxy_detachment_is_explicit(self):
        controller = ObjectiveController()
        objectives = controller.derive(
            "solve", uncertainty=0.8, contradictions=1,
            missing_evidence=1, prediction_error=0.4,
        )
        self.assertAlmostEqual(sum(item.weight for item in objectives), 1.0)
        detached = controller.audit_alignment(
            objectives[0], metric_improved=True, goal_progressed=False
        )
        self.assertEqual(detached.status, "detached-proxy")


class StrategyLearningTests(unittest.TestCase):
    def test_strategy_evidence_is_class_scoped_and_persistent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "strategies.json"
            learner = PersistentStrategyLearner(path)
            for _ in range(3):
                learner.update("graphs", "mcts-v16", True)
            unseen = learner.select_strategy(
                "symbolic", ("primitive-compose", "mcts-v16")
            )
            self.assertEqual(unseen.strategy_id, "primitive-compose")
            self.assertIn("cross-class preference blocked", unseen.basis)
            trained = PersistentStrategyLearner(path).select_strategy(
                "graphs", ("primitive-compose", "mcts-v16")
            )
            self.assertEqual(trained.strategy_id, "mcts-v16")

    def test_negative_transfer_is_recorded_not_hidden(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "strategies.json"
            learner = PersistentStrategyLearner(path)
            learner.record_transfer("graphs", "causal", "mcts-v16", 0.8, 0.2)
            restored = PersistentStrategyLearner(path)
            self.assertEqual(len(restored.negative_transfer), 1)
            self.assertLess(restored.negative_transfer[0]["delta"], 0)


class CapabilityLifecycleTests(unittest.TestCase):
    def test_semantic_equivalence_and_cross_domain_promotion(self):
        lifecycle = CapabilityLifecycle()
        lifecycle.discover(
            "double", kind="primitive", dependencies=(),
            provenance="episode:discovery-1",
        )
        self.assertTrue(lifecycle.validate(
            "double", implementation=lambda x: x + x,
            reference=lambda x: 2 * x, corpus=(0, 1, 2, -4), domain="numbers",
        ))
        self.assertTrue(lifecycle.validate(
            "double", implementation=lambda x: x + x,
            reference=lambda x: 2 * x, corpus=("a", "bc"), domain="strings",
        ))
        lifecycle.promote("double")
        self.assertEqual(lifecycle.records["double"].status, "promoted")
        self.assertIsNotNone(lifecycle.records["double"].semantic_digest)

    def test_failed_semantics_cannot_promote_and_history_survives_deprecation(self):
        lifecycle = CapabilityLifecycle()
        lifecycle.discover(
            "bad", kind="primitive", dependencies=(), provenance="episode:bad"
        )
        self.assertFalse(lifecycle.validate(
            "bad", implementation=lambda x: x + 1,
            reference=lambda x: x, corpus=(1, 2), domain="numbers",
        ))
        with self.assertRaises(ValueError):
            lifecycle.promote("bad")
        lifecycle.deprecate("bad", "semantic mismatch")
        self.assertTrue(any(event["event"] == "deprecated" for event in lifecycle.events))


class NoveltyAndMathematicsTests(unittest.TestCase):
    def test_novelty_never_overrides_correctness(self):
        archive = NoveltyArchive()
        rejected = archive.consider((100.0, 100.0), correct=False, invariants_hold=True)
        self.assertFalse(rejected["accepted"])
        self.assertEqual(archive.descriptors, [])
        self.assertTrue(
            archive.consider((0.0, 0.0), correct=True, invariants_hold=True)["accepted"]
        )

    def test_phi_negative_result_remains_in_evidence(self):
        def evaluator(order, seed):
            # Deliberately favours neutral ordering: falsification must survive.
            return (-sum(abs(index - value) for index, value in enumerate(order)), len(order))

        report = paired_ordering_experiment(32, evaluator, seeds=(1, 2, 3, 4))
        self.assertFalse(report["supported"])
        self.assertLess(report["mean_score_delta"], 0)
        self.assertEqual(len(report["paired_runs"]), 4)


class BenchmarkDisciplineTests(unittest.TestCase):
    def test_required_evaluation_families_are_present(self):
        programme = BenchmarkProgramme(adversarial_evaluation_tasks())
        self.assertEqual(programme.missing_families, [])
        self.assertTrue(all(
            task.partition == "evaluation" for task in programme.tasks
        ))

    def test_partition_identity_leak_fails_closed(self):
        task = {"problem_id": "x", "goal": "g"}
        with self.assertRaises(ValueError):
            BenchmarkProgramme([
                BenchmarkTask("same", "deduction", "train", task, "solved"),
                BenchmarkTask("same", "deduction", "evaluation", task, "solved"),
            ])

    def test_summary_reports_variation_not_single_score(self):
        rows = [
            TrialResult(
                "integrated", f"t-{seed}", "deduction", seed,
                True, seed % 2 == 0, 0.1 + seed * 0.01, 10, 0, 1,
                0.2, 0.2, 1, 1, False, "primitive-compose",
            )
            for seed in range(4)
        ]
        summary = BenchmarkProgramme.summarise(rows)["integrated"]
        self.assertIsNotNone(summary["correctness"]["stddev"])
        self.assertGreater(summary["correctness"]["high95"],
                           summary["correctness"]["low95"])


if __name__ == "__main__":
    unittest.main()