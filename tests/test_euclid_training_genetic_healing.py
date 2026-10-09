import tempfile
import unittest
from pathlib import Path

from chronus.seam.genetic_mining import evolve_mining_config
from euclid.evidence import EvidenceChain
from euclid.evidence_bundle import create_evidence_bundle
from euclid.learning_service import LearningService
from euclid.memory_database import MemoryDatabase
from euclid.self_healing_evidence import verify_proposal_only_self_healing
from euclid.training_pipeline import TrainingCase, TrainingPipeline


class Scale:
    def __init__(self, work_items, ladder_index):
        self.work_items = work_items
        self.ladder_index = ladder_index


class TinyLearner:
    def __init__(self):
        self.tasks = {}
        self.values = {}

    def register_task(self, task_id, actions, **_kwargs):
        if task_id not in self.tasks:
            self.tasks[task_id] = type("Task", (), {"actions": tuple(actions)})()
            self.values[task_id] = {action: 0.0 for action in actions}

    def select_action(self, task_id, state, *, explore):
        target = state.get("target")
        if explore:
            return target
        return max(self.values[task_id], key=self.values[task_id].get)

    def observe(self, task_id, state, action, reward, next_state, **_kwargs):
        self.values[task_id][action] += reward


class EvidenceTrainingGeneticHealingTests(unittest.TestCase):
    def test_genetic_mining_is_deterministic_bounded_and_evolves(self):
        def scale(_job_id, requested):
            return Scale(requested, max(1, requested.bit_length() - 1))

        first = evolve_mining_config(64, scale, generations=5, population_size=8)
        second = evolve_mining_config(64, scale, generations=5, population_size=8)
        self.assertEqual(first, second)
        # LUCAS_SCALED (lemma_lucas_universal): search-effort envelopes snap
        # to ladder stops inside the validated bounds — 5 -> 10, 8 -> 10.
        self.assertEqual(first.generations_run, 10)
        self.assertEqual(first.population_size, 10)
        self.assertGreater(first.batch, 0)
        self.assertGreaterEqual(first.fitness, 0.0)
        self.assertEqual(len(first.evidence_hash), 64)
        self.assertTrue(first.to_evidence()["passed"])
        self.assertLessEqual(first.window, 128)
        with self.assertRaises(ValueError):
            evolve_mining_config(0, scale)

    def test_training_pipeline_has_holdout_null_and_durable_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            database = MemoryDatabase(Path(directory) / "memory.sqlite3")
            learner = TinyLearner()
            service = LearningService(
                experience_learner=learner,
                memory_database=database,
                evidence=EvidenceChain(),
            )
            pipeline = TrainingPipeline(
                learner, service, mission_id="training-1", provenance="sha256:test"
            )
            train = [
                TrainingCase(f"train-{i}", {"target": "right"}) for i in range(8)
            ]
            holdout = [
                TrainingCase(f"holdout-{i}", {"target": "right"}) for i in range(4)
            ]
            report = pipeline.run(
                task_id="binary-choice",
                actions=("left", "right"),
                train_cases=train,
                holdout_cases=holdout,
                reward=lambda case, action: 1.0 if action == case.state["target"] else -1.0,
                epochs=2,
                report_path=Path(directory) / "training.json",
            )
            self.assertTrue(report.passed)
            self.assertGreater(report.trained_mean, report.null_mean)
            self.assertTrue((Path(directory) / "training.json").is_file())
            self.assertEqual(database.verify()["memories"], 16)
            database.close()

    def test_self_healing_gate_detects_mutation_and_accepts_proposal_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "module.py"
            source.write_text("VALUE = 1\n")
            clean = verify_proposal_only_self_healing(
                lambda: {
                    "diagnosis_completed": True,
                    "proposals": 1,
                    "repairs_applied": 0,
                },
                [root],
            )
            self.assertTrue(clean.passed)

            def mutate():
                source.write_text("VALUE = 2\n")
                return {
                    "diagnosis_completed": True,
                    "proposals": 1,
                    "repairs_applied": 1,
                }

            unsafe = verify_proposal_only_self_healing(mutate, [root])
            self.assertFalse(unsafe.passed)
            self.assertTrue(unsafe.mutation_detected)

    def test_sealed_evidence_bundle_requires_every_gate(self):
        bundle = create_evidence_bundle(
            runtime={
                "schema": "euclid.startup/1",
                "network_enabled": False,
                "federation_enabled": False,
            },
            memory={"valid": True},
            training={"passed": True},
            genetic_mining={"passed": True},
            self_healing={"passed": True},
        )
        self.assertTrue(bundle["passed"])
        self.assertEqual(len(bundle["seal"]), 64)
        failed = create_evidence_bundle(
            runtime={
                "schema": "euclid.startup/1",
                "network_enabled": False,
                "federation_enabled": False,
            },
            memory={"valid": True},
            training={"passed": False},
            genetic_mining={"passed": True},
            self_healing={"passed": True},
        )
        self.assertFalse(failed["passed"])


if __name__ == "__main__":
    unittest.main()
