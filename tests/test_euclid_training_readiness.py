"""Bounded training/readiness contracts for the governed EUCLID pipeline.

These tests prove only what the batch implements: mandatory whole-lineage
partition validation, named controls, action/reward contract enforcement,
durable replay rejection across restart, a real ExperienceSuperlearner
train/checkpoint/restore cycle on a mining-shaped HOLD/REDUCE/RESTORE task,
and the manifest-gated handoff into the mining adapter.  No live-pool,
hardware or profitability claims are made or required.
"""

import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PLATFORM = _REPO_ROOT / "chronus/mla1517_platform" / "python"
for _path in (str(_PLATFORM), str(_REPO_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from euclid.checkpoint_manifest import (  # noqa: E402
    load_manifest,
    verify_manifest,
)
from euclid.contracts import Experience, RewardAuthority  # noqa: E402
from euclid.learning_service import LearningService  # noqa: E402
from euclid.memory_database import MemoryDatabase  # noqa: E402
from euclid.mining_training_task import (  # noqa: E402
    breadth_reward,
    make_breadth_cases,
    make_partitioned_dataset,
)
from euclid.training_pipeline import (  # noqa: E402
    TrainingCase,
    TrainingPipeline,
    validate_partitions,
)
from hyba_substrate.euclid_experience_superlearner import (  # noqa: E402
    ExperienceSuperlearner,
)

MINING_TASK_ID = "bitcoin-mining-operating-breadth"
MINING_ACTIONS = ("hold", "reduce", "restore")


def _case(case_id, state, *, lineage=None, session=None, seed=None):
    return TrainingCase(
        case_id,
        state,
        lineage_id=lineage,
        session_id=session,
        seed=seed,
    )


def _service(test_case, directory, learner=None):
    root = Path(directory)
    database = MemoryDatabase(root / "memory.sqlite3")
    test_case.addCleanup(database.close)
    return LearningService(
        experience_learner=learner,
        memory_database=database,
        replay_journal_path=root / "replay_journal.json",
    )


def _experience(replay_id, reward=0.5, mission="mission-1", domain=MINING_TASK_ID):
    return Experience(
        experience_id=f"exp-{replay_id}",
        mission_id=mission,
        domain=domain,
        source="test",
        observation={"accepted_band": 1},
        action="hold",
        outcome={"accepted": 1},
        reward=reward,
        reward_authority=RewardAuthority.VALIDATED_SIMULATION,
        provenance="sha256:test",
        uncertainty=0.0,
        replay_id=replay_id,
    )


class PartitionContractTests(unittest.TestCase):
    def test_rejects_duplicate_case_id_across_partitions(self):
        train = [_case("a", {"x": 1}, session="s1")]
        validation = [_case("a", {"x": 2}, session="s2")]
        with self.assertRaises(ValueError):
            validate_partitions(
                train_cases=train, validation_cases=validation
            )

    def test_rejects_shared_lineage_across_partitions(self):
        train = [_case("a", {"x": 1}, lineage="fam-1")]
        validation = [_case("b", {"x": 2}, lineage="fam-1")]
        with self.assertRaises(ValueError):
            validate_partitions(
                train_cases=train, validation_cases=validation
            )

    def test_rejects_shared_session_and_seed_across_partitions(self):
        train = [_case("a", {"x": 1}, session="sess", seed=1)]
        validation = [_case("b", {"x": 2}, session="sess", seed=2)]
        with self.assertRaises(ValueError):
            validate_partitions(
                train_cases=train, validation_cases=validation
            )
        with self.assertRaises(ValueError):
            validate_partitions(
                train_cases=[_case("a", {"x": 1}, seed=7)],
                validation_cases=[_case("b", {"x": 2}, seed=7)],
            )

    def test_rejects_identical_declared_record_across_partitions(self):
        train = [_case("a", {"x": 1}, session="s1", seed=1)]
        clone = _case("b", {"x": 1}, session="s1", seed=1)
        with self.assertRaises(ValueError):
            validate_partitions(
                train_cases=train, validation_cases=[clone]
            )

    def test_mining_dataset_partitions_are_disjoint_by_lineage(self):
        dataset = make_partitioned_dataset(per_partition=6)
        report = validate_partitions(
            train_cases=dataset["train"],
            validation_cases=dataset["validation"],
            final_test_cases=dataset["final_test"],
        )
        self.assertEqual(report.partitions["final_test"], 6)
        self.assertEqual(report.distinct_lineages["train"], 6)


class ContractValidationTests(unittest.TestCase):
    def _pipeline(self, directory, learner, service):
        return TrainingPipeline(
            learner, service, mission_id="m1", provenance="sha256:test"
        )

    def test_requires_two_unique_actions(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            learner = ExperienceSuperlearner(
                Path(directory) / "learner.json", seed=1
            )
            pipeline = self._pipeline(directory, learner, _service(self, directory, learner))
            cases = make_breadth_cases(count=3, session_id="s1", seed=1)
            with self.assertRaises(ValueError):
                pipeline.run(
                    task_id=MINING_TASK_ID,
                    actions=("hold",),
                    train_cases=cases,
                    validation_cases=make_breadth_cases(
                        count=2, session_id="s2", seed=2
                    ),
                    reward=breadth_reward,
                )
            with self.assertRaises(ValueError):
                pipeline.run(
                    task_id=MINING_TASK_ID,
                    actions=("hold", "hold"),
                    train_cases=cases,
                    validation_cases=make_breadth_cases(
                        count=2, session_id="s2", seed=2
                    ),
                    reward=breadth_reward,
                )

    def test_rejects_unregistered_action_selection(self):
        class RogueLearner(ExperienceSuperlearner):
            def select_action(self, task_id, state, *, explore=True):
                return "explode-everything"

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            learner = RogueLearner(Path(directory) / "learner.json", seed=1)
            pipeline = self._pipeline(directory, learner, _service(self, directory, learner))
            dataset = make_partitioned_dataset(per_partition=4)
            with self.assertRaises(ValueError):
                pipeline.run(
                    task_id=MINING_TASK_ID,
                    actions=MINING_ACTIONS,
                    train_cases=dataset["train"],
                    validation_cases=dataset["validation"],
                    reward=breadth_reward,
                )

    def test_rejects_out_of_range_and_non_finite_reward(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            learner = ExperienceSuperlearner(
                Path(directory) / "learner.json", seed=1
            )
            pipeline = self._pipeline(directory, learner, _service(self, directory, learner))
            dataset = make_partitioned_dataset(per_partition=4)
            for bad_reward in (
                lambda _case, _action: math.inf,
                lambda _case, _action: 2.5,
            ):
                with self.assertRaises(ValueError):
                    pipeline.run(
                        task_id=MINING_TASK_ID,
                        actions=MINING_ACTIONS,
                        train_cases=dataset["train"],
                        validation_cases=dataset["validation"],
                        reward=bad_reward,
                        reward_range=(-1.0, 1.0),
                    )

    def test_service_learner_must_be_the_pipeline_learner(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            trained = ExperienceSuperlearner(
                Path(directory) / "trained.json", seed=1
            )
            other = ExperienceSuperlearner(
                Path(directory) / "other.json", seed=2
            )
            pipeline = self._pipeline(directory, trained, _service(self, directory, other))
            dataset = make_partitioned_dataset(per_partition=4)
            with self.assertRaises(ValueError):
                pipeline.run(
                    task_id=MINING_TASK_ID,
                    actions=MINING_ACTIONS,
                    train_cases=dataset["train"],
                    validation_cases=dataset["validation"],
                    reward=breadth_reward,
                )


class DurableReplayTests(unittest.TestCase):
    def test_replay_rejected_after_restart_without_learner_mutation(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            root = Path(directory)
            learner = ExperienceSuperlearner(root / "learner.json", seed=1)
            learner.register_task(
                MINING_TASK_ID, MINING_ACTIONS, reward_range=(-1.0, 1.0)
            )
            first = _service(self, directory, learner)
            first.record(_experience("rp-1"))

            # Restart: fresh learner object from the checkpoint plus a fresh
            # service on the same durable journal and memory database.
            restarted_learner = ExperienceSuperlearner(root / "learner.json")
            restarted = _service(self, directory, restarted_learner)
            transitions_before = list(restarted_learner.transitions)

            with self.assertRaises(ValueError):
                restarted.record(_experience("rp-1"))
            self.assertEqual(
                list(restarted_learner.transitions), transitions_before
            )

            # Conflicting content under a claimed replay_id fails closed too.
            with self.assertRaises(ValueError):
                restarted.record(_experience("rp-1", reward=-0.5))
            self.assertEqual(
                list(restarted_learner.transitions), transitions_before
            )

    def test_replay_journal_tamper_fails_closed(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            root = Path(directory)
            service = _service(self, directory)
            service.record(_experience("rp-3"))
            journal_path = root / "replay_journal.json"
            payload = json.loads(journal_path.read_text())
            payload["entries"]["rp-3"]["content_hash"] = "forged"
            journal_path.write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                _service(self, directory)

    def test_replay_state_reports_durable_protection(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            service = _service(self, directory)
            service.record(_experience("rp-2"))
            state = service.replay_state()
            self.assertTrue(state["durable"])
            self.assertEqual(state["journal_entries"], 1)
            self.assertTrue(
                (Path(directory) / "replay_journal.json").is_file()
            )


class RealLearnerIntegrationTests(unittest.TestCase):
    def _train(self, directory):
        root = Path(directory)
        dataset = make_partitioned_dataset(per_partition=12)
        learner = ExperienceSuperlearner(
            root / "learner.json", epsilon=0.2, seed=7
        )
        service = _service(self, directory, learner)
        pipeline = TrainingPipeline(
            learner, service, mission_id="mining-1", provenance="sha256:test"
        )
        report = pipeline.run(
            task_id=MINING_TASK_ID,
            actions=MINING_ACTIONS,
            train_cases=dataset["train"],
            validation_cases=dataset["validation"],
            final_test_cases=dataset["final_test"],
            reward=breadth_reward,
            reward_range=(-1.0, 1.0),
            epochs=3,
            control_seed=7,
            report_path=root / "report.json",
            manifest_path=root / "manifest.json",
            source_revision="test-revision",
        )
        return dataset, learner, service, report

    def test_experience_superlearner_train_checkpoint_restore(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            root = Path(directory)
            dataset, learner, service, report = self._train(directory)

            self.assertTrue(report.passed)
            self.assertGreater(report.trained_mean, report.fixed_action_mean)
            self.assertGreater(report.trained_mean, report.uninformed_mean)
            self.assertEqual(report.controls["uninformed"]["seed"], 7)
            self.assertIsNotNone(report.final_test_mean)
            self.assertTrue(
                report.learner_identity["service_learner_is_pipeline_learner"]
            )
            self.assertTrue((root / "learner.json").is_file())

            # Fresh learner object constructed solely from the checkpoint.
            restored = ExperienceSuperlearner(root / "learner.json")
            self.assertEqual(
                sorted(restored.tasks), sorted(learner.tasks.keys())
            )
            self.assertEqual(restored.q_values, learner.q_values)
            self.assertEqual(restored.world_model, learner.world_model)
            for case in dataset["validation"] + dataset["final_test"]:
                self.assertEqual(
                    restored.select_action(
                        MINING_TASK_ID, dict(case.state), explore=False
                    ),
                    learner.select_action(
                        MINING_TASK_ID, dict(case.state), explore=False
                    ),
                )

    def test_manifest_sealed_and_fail_closed_on_corruption(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            root = Path(directory)
            _dataset, _learner, _service, report = self._train(directory)

            manifest = load_manifest(root / "manifest.json")
            verification = verify_manifest(
                manifest,
                learner_checkpoint_path=root / "learner.json",
                evidence_path=root / "report.json",
            )
            self.assertTrue(verification["valid"])
            self.assertEqual(
                verification["source_revision"], "test-revision"
            )

            # Seal corruption fails closed.
            tampered = json.loads((root / "manifest.json").read_text())
            tampered["source_revision"] = "forged-revision"
            (root / "tampered.json").write_text(json.dumps(tampered))
            with self.assertRaises(ValueError):
                load_manifest(root / "tampered.json")

            # Learner drift fails closed.
            drifted = root / "drifted.json"
            drifted.write_text((root / "learner.json").read_text() + " ")
            with self.assertRaises(ValueError):
                verify_manifest(
                    manifest, learner_checkpoint_path=drifted
                )

    def test_mining_adapter_consumes_verified_checkpoint_only(self):
        from chronus.mla1517.mining.euclid_support import (
            EuclidMiningSupport,
            load_policy_checkpoint,
        )

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            root = Path(directory)
            _dataset, learner, _service, report = self._train(directory)
            self.assertTrue(report.passed)

            identity = load_policy_checkpoint(
                root / "learner.json",
                manifest_path=root / "manifest.json",
                task_id=MINING_TASK_ID,
                actions=MINING_ACTIONS,
            )
            self.assertTrue(identity["manifest_verified"])
            self.assertEqual(
                identity["source_revision"], "test-revision"
            )

            support = EuclidMiningSupport(
                8,
                state_path=str(root / "learner.json"),
                manifest_path=str(root / "manifest.json"),
            )
            self.assertTrue(support.available)
            snapshot = support.snapshot()
            self.assertEqual(
                snapshot["policy_identity"]["checkpoint_sha256"],
                identity["checkpoint_sha256"],
            )
            self.assertEqual(
                snapshot["single_actuator"],
                "dispatch_breadth via this support only",
            )

            # A corrupted manifest cannot reach the adapter.
            tampered = json.loads((root / "manifest.json").read_text())
            tampered["task"]["task_id"] = "different-task"
            (root / "bad_manifest.json").write_text(json.dumps(tampered))
            rejected = EuclidMiningSupport(
                8,
                state_path=str(root / "learner.json"),
                manifest_path=str(root / "bad_manifest.json"),
            )
            self.assertFalse(rejected.available)
            self.assertIn("policy checkpoint rejected", rejected.unavailable_reason)


if __name__ == "__main__":
    unittest.main()
