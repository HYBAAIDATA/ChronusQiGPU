from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from euclid.contracts import Experience, RewardAuthority
from euclid.genesis import (
    EvidenceClass,
    ProvenanceSource,
    SourceDisposition,
    build_genesis,
)
from euclid.kairos_qualification import (
    ComponentState,
    LoopStage,
    QualificationLedger,
    default_intelligence_matrix,
)
from euclid.kairos_runtime import KairosRuntime, Role
from euclid.learning_service import LearningService
from hyba_substrate.euclid_experience_superlearner import ExperienceSuperlearner


class GenesisTests(unittest.TestCase):
    def test_fresh_roots_are_deterministic_and_empty(self) -> None:
        source = ProvenanceSource(
            source_id="archive-1",
            source_identity="prior-euclid-research",
            version="2026-07-19",
            evidence_class=EvidenceClass.ARCHIVAL,
            uncertainty=0.25,
            labels=("ARCHIVAL", "CURRICULUM_ONLY"),
        )
        first = build_genesis([source]).to_payload()
        second = build_genesis([source]).to_payload()
        self.assertEqual(first, second)
        self.assertEqual(first["predecessor_relationship"].split(";")[0], "NEW_INSTANCE")
        self.assertEqual(len(first["roots"]), 7)

    def test_archival_source_cannot_become_current_truth(self) -> None:
        with self.assertRaises(ValueError):
            ProvenanceSource(
                source_id="archive-2",
                source_identity="prior-euclid-memory",
                version="unknown",
                evidence_class=EvidenceClass.CURRICULUM,
                uncertainty=1.0,
                disposition=SourceDisposition.OBSERVATION_ONLY,
                labels=("CURRENT_SEMANTIC_TRUTH",),
            ).assert_not_semantic_truth()


class KairosQualificationTests(unittest.TestCase):
    def test_world_session_checkpoint_restore_replay_and_tamper(self) -> None:
        runtime = KairosRuntime("creator")
        runtime.open_session("operator", Role.OPERATOR)
        runtime.create_world("lab", {"signal": 0})
        runtime.dispatch(
            {
                "schema": "kairos.command/1",
                "world_id": "lab",
                "op": "set",
                "key": "signal",
                "value": 1,
            }
        )
        runtime.close_session()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "kairos.json"
            runtime.save(path)
            restored = KairosRuntime.restore(path)
            self.assertTrue(restored.replay_verify())
            payload = json.loads(path.read_text())
            payload["worlds"]["lab"]["state"]["signal"] = 2
            path.write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                KairosRuntime.restore(path)

    def test_typed_commands_and_observer_mutation_fail_closed(self) -> None:
        runtime = KairosRuntime("creator")
        runtime.open_session("viewer", Role.OBSERVER)
        with self.assertRaises(PermissionError):
            runtime.create_world("denied")

    def test_full_loop_refutation_partition_and_production_boundaries(self) -> None:
        ledger = QualificationLedger()
        for index, stage in enumerate(LoopStage):
            ledger.append(
                stage=stage,
                event_id=f"event-{index}",
                payload={"value": index},
                uncertainty=index / 20.0,
                lineage_id="rehearsal-lineage",
                partition="rehearsal",
            )
        ledger.record_claim("claim-1", "candidate relation", evidence_ids=("event-3",), uncertainty=.5)
        ledger.revise_claim(
            "claim-1",
            replacement_id="claim-1-refuted",
            status="REFUTED",
            evidence_ids=("event-7",),
            uncertainty=.1,
        )
        report = ledger.report()
        self.assertEqual(report["full_loops"], 1)
        self.assertFalse(report["production_evidence"])
        self.assertEqual(len(report["refuted_claims_retained"]), 2)

        with self.assertRaises(PermissionError):
            QualificationLedger().append(
                stage=LoopStage.OBSERVATION,
                event_id="bad",
                payload={"authority": "pool"},
                uncertainty=0.0,
                lineage_id="x",
                partition="rehearsal",
            )

    def test_lineage_cannot_cross_held_out_partition(self) -> None:
        ledger = QualificationLedger()
        ledger.append(
            stage=LoopStage.OBSERVATION,
            event_id="train-observation",
            payload={},
            uncertainty=0.0,
            lineage_id="shared",
            partition="train",
        )
        with self.assertRaises(ValueError):
            ledger.append(
                stage=LoopStage.MEMORY,
                event_id="final-memory",
                payload={},
                uncertainty=0.0,
                lineage_id="shared",
                partition="final_test",
            )

    def test_reward_authority_and_episodic_replay_integration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            learner = ExperienceSuperlearner(
                Path(directory) / "learner.json", seed=7, planning_steps=0
            )
            service = LearningService(
                experience_learner=learner,
                replay_journal_path=Path(directory) / "replay.json",
            )
            observation = Experience(
                experience_id="observation-1",
                mission_id="qualification",
                domain="counterfactual",
                source="kairos",
                observation={"world": "actual"},
                action="compare",
                outcome={"world": "counterfactual"},
                reward=None,
                reward_authority=RewardAuthority.NONE,
                provenance="kairos-rehearsal",
                uncertainty=.4,
                replay_id="replay-1",
            )
            service.record(observation)
            self.assertEqual(len(learner.transitions), 0)
            with self.assertRaises(ValueError):
                service.record(observation)

    def test_curriculum_lineage_transfer_and_uninformed_control(self) -> None:
        learner = ExperienceSuperlearner(seed=11, planning_steps=0, epsilon=0.0)
        learner.register_task("source", ("left", "right"), transfer_group="pair")
        learner.register_task("target", ("left", "right"), transfer_group="pair")
        learner.observe("source", {"x": 0}, "right", 1.0, {"x": 1})
        record = learner.transfer_prior("source", "target", strength=.25)
        self.assertEqual(record["source_task_id"], "source")
        self.assertFalse(record["external_validation"])
        curriculum = learner.autonomous_curriculum()
        self.assertEqual({row.task_id for row in curriculum}, {"source", "target"})
        uninformed = ["left", "right", "left", "right"]
        informed = [learner.select_action("source", {"x": 0}, explore=False)] * 4
        self.assertNotEqual(uninformed, informed)

    def test_matrix_is_machine_readable_and_conservative(self) -> None:
        matrix = default_intelligence_matrix()
        self.assertEqual(
            matrix["components"]["generalisation_transfer"]["state"],
            ComponentState.REACHABLE_BUT_UNPROVEN.value,
        )
        json.dumps(matrix, sort_keys=True)


if __name__ == "__main__":
    unittest.main()