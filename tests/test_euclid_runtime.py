import json
import tempfile
import unittest
from pathlib import Path

from euclid.contracts import Authority, Experience, RewardAuthority
from euclid.adapters import (
    mining_policy_organ,
    reasoning_organ,
    repository_status_organ,
    self_healing_proposal_organ,
)
from euclid.evidence import EvidenceChain
from euclid.governance import Organ
from euclid.kairos_runtime import Role
from euclid.learning_service import LearningService
from euclid.memory_database import MemoryDatabase, MemoryScope
from euclid.rights import ProviderManifest, require_provider
from euclid.runtime import EuclidRuntime
from euclid.production_harness import run_production_gates


class EuclidRuntimeTests(unittest.TestCase):
    def test_kairos_checkpoint_restore_replay_and_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            runtime = EuclidRuntime(creator_id="andre", state_dir=directory)
            runtime.kairos.open_session("andre", Role.CREATOR)
            runtime.kairos.create_world("kairos", {"phase": 0})
            runtime.kairos.dispatch({
                "schema": "kairos.command/1", "world_id": "kairos",
                "op": "set", "key": "phase", "value": 1,
            })
            runtime.kairos.save(path)
            restored = runtime.kairos.restore(path)
            self.assertTrue(restored.replay_verify())
            payload = json.loads(path.read_text())
            payload["worlds"]["kairos"]["state"]["phase"] = 2
            path.write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                runtime.kairos.restore(path)

    def test_single_session_and_observer_fail_closed(self):
        runtime = EuclidRuntime(creator_id="andre", state_dir="unused")
        runtime.kairos.open_session("observer", Role.OBSERVER)
        with self.assertRaises(RuntimeError):
            runtime.kairos.open_session("andre", Role.CREATOR)
        with self.assertRaises(PermissionError):
            runtime.kairos.create_world("forbidden")

    def test_all_delegation_gates_and_integration_gates(self):
        runtime = EuclidRuntime(creator_id="andre", state_dir="unused")
        runtime.register_organ(Organ(
            "reasoner", frozenset({"reason"}), Authority.PROPOSE,
            lambda request: {"answer": request["question"]},
        ))
        runtime.rights.grant("andre", "reasoner", "reason", "dispatch")
        result = runtime.delegator.dispatch(
            "reasoner", "reason", {"question": "why"},
            confident=True, safe=True,
        )
        self.assertEqual(result["answer"], "why")
        for failed in ("confident", "safe"):
            kwargs = {"confident": True, "safe": True}
            kwargs[failed] = False
            with self.assertRaises(PermissionError):
                runtime.delegator.dispatch("reasoner", "reason", {}, **kwargs)
        runtime.rights.revoke("andre", "reasoner", "reason", "dispatch")
        with self.assertRaises(PermissionError):
            runtime.delegator.dispatch(
                "reasoner", "reason", {}, confident=True, safe=True
            )
        with self.assertRaises(PermissionError):
            runtime.delegator.dispatch(
                "reasoner", "missing", {}, confident=True, safe=True
            )
        self.assertTrue(runtime.delegator.approve_integration(
            coherent=True, truth_evidence=True, causal=True, feedback=True
        ).accepted)
        self.assertFalse(runtime.delegator.approve_integration(
            coherent=True, truth_evidence=False, causal=True, feedback=True
        ).accepted)

    def test_rights_revoke_and_provider_mismatch(self):
        runtime = EuclidRuntime(creator_id="andre", state_dir="unused")
        runtime.rights.grant("andre", "repo-engineer", "repo", "read")
        runtime.rights.require("andre", "repo-engineer", "repo", "read")
        runtime.rights.revoke("andre", "repo-engineer", "repo", "read")
        with self.assertRaises(PermissionError):
            runtime.rights.require("andre", "repo-engineer", "repo", "read")
        with self.assertRaises(PermissionError):
            runtime.rights.grant("attacker", "repo-engineer", "repo", "read")
        manifest = ProviderManifest("local", "sha256:abc", frozenset({"text"}), "offline")
        require_provider(
            manifest, provider_id="local", identity="sha256:abc",
            modality="text", deployment="offline",
        )
        with self.assertRaises(PermissionError):
            require_provider(
                manifest, provider_id="local", identity="sha256:def",
                modality="text", deployment="offline",
            )

    def test_absent_reward_is_not_applied_and_replay_rejected(self):
        service = LearningService(evidence=EvidenceChain())
        experience = Experience(
            "e1", "m1", "research", "operator", {"q": 1}, "observe",
            {"a": 1}, None, RewardAuthority.NONE, "sha256:source", 0.5, "r1",
        )
        service.record(experience)
        with self.assertRaises(ValueError):
            service.record(experience)
        self.assertEqual(service.evidence.records[-1].payload["reward_applied"], False)

    def test_mining_authority_boundary_is_explicit_and_closed(self):
        report = EuclidRuntime(creator_id="andre", state_dir="unused").startup_report()
        forbidden = set(report["authority_boundary"]["forbidden"])
        self.assertIn("sha256d", forbidden)
        self.assertIn("target", forbidden)
        self.assertIn("share-validation", forbidden)
        self.assertFalse(report["network_enabled"])
        self.assertFalse(report["federation_enabled"])

    def test_full_runtime_checkpoint_preserves_rights_worlds_and_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "euclid.json"
            runtime = EuclidRuntime(creator_id="andre", state_dir=directory)
            runtime.kairos.open_session("andre", Role.CREATOR)
            runtime.kairos.create_world("kairos", {"ready": False})
            runtime.rights.grant("andre", "reasoner", "kairos", "read")
            runtime.save(path)
            restored = EuclidRuntime.restore(path, state_dir=directory)
            restored.rights.require("andre", "reasoner", "kairos", "read")
            self.assertEqual(restored.kairos.worlds["kairos"].state, {"ready": False})
            self.assertTrue(restored.kairos.replay_verify())
            # Release the sqlite handles so the tempdir can be removed on
            # platforms that lock open database files.
            restored.close()
            runtime.close()

    def test_governed_adapters_are_narrow(self):
        reasoner = reasoning_organ("reasoner", {"reason": lambda value: {"seen": value}})
        self.assertEqual(
            reasoner.handler({"capability": "reason", "input": {"x": 1}})["proposal"],
            {"seen": {"x": 1}},
        )
        with self.assertRaises(PermissionError):
            reasoner.handler({"capability": "unknown"})

        class Repo:
            def status(self):
                return {"ready": True}

        repo = repository_status_organ(Repo())
        self.assertTrue(repo.handler({"operation": "status"})["status"]["ready"])
        with self.assertRaises(PermissionError):
            repo.handler({"operation": "ask"})

        healing = self_healing_proposal_organ(lambda evidence: {"diagnosis": evidence})
        self.assertFalse(
            healing.handler({"operation": "propose", "evidence": {"error": "x"}})["executed"]
        )
        with self.assertRaises(PermissionError):
            healing.handler({"operation": "execute"})

        class Advice:
            __dataclass_fields__ = {"action": None}
            state = "ACTIVE"
            action = "hold"
            dispatch_breadth = 4
            reason = "bounded"
            evidence = {}

        class Support:
            def advise(self, *_args, **_kwargs):
                return Advice()

        # Use a real dataclass-like mapping path for stable adapter output.
        support = Support()
        support.advise = lambda *_args, **_kwargs: {
            "state": "ACTIVE", "action": "hold", "dispatch_breadth": 4,
            "reason": "bounded", "evidence": {},
        }
        mining = mining_policy_organ(support)
        self.assertEqual(mining.handler({"snapshot": {}})["action"], "hold")
        with self.assertRaises(PermissionError):
            mining.handler({"header": "forbidden"})

    def test_production_harness_passes_local_fail_closed_gates(self):
        report = run_production_gates(
            lambda root: EuclidRuntime.production(creator_id="andre", state_dir=root)
        )
        self.assertTrue(report["passed"], report)
        self.assertEqual(len(report["results"]), 5)

    def test_memory_database_scope_replay_tombstone_backup_and_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "memory.sqlite3"
            scope = MemoryScope("local", "mission-1", "research")
            with MemoryDatabase(path) as database:
                record = database.put(
                    scope=scope,
                    tier="semantic",
                    content={"fact": "bounded evidence"},
                    provenance="sha256:source",
                    reward_authority=RewardAuthority.OPERATOR,
                    uncertainty=0.2,
                    replay_id="replay-1",
                    memory_id="memory-1",
                )
                self.assertEqual(database.get("memory-1", scope=scope), record)
                with self.assertRaises(KeyError):
                    database.get(
                        "memory-1",
                        scope=MemoryScope("other", "mission-1", "research"),
                    )
                with self.assertRaises(Exception):
                    database.put(
                        scope=scope, tier="semantic", content={"fact": "duplicate"},
                        provenance="sha256:source",
                        reward_authority=RewardAuthority.OPERATOR,
                        uncertainty=0.2, replay_id="replay-1",
                    )
                self.assertTrue(database.verify()["valid"])
                backup = database.backup(Path(directory) / "backup.sqlite3")
                self.assertTrue(backup.is_file())
                database.tombstone("memory-1", scope=scope, reason="operator removal")
                with self.assertRaises(KeyError):
                    database.get("memory-1", scope=scope)
                database._connection.execute(
                    "UPDATE memories SET content_json='{\"fact\":\"tampered\"}' "
                    "WHERE memory_id='memory-1'"
                )
                with self.assertRaises(ValueError):
                    database.verify()

    def test_learning_service_persists_governed_experience(self):
        with tempfile.TemporaryDirectory() as directory:
            with MemoryDatabase(Path(directory) / "memory.sqlite3") as database:
                service = LearningService(
                    evidence=EvidenceChain(), memory_database=database
                )
                experience = Experience(
                    "experience-1", "mission-1", "research", "operator",
                    {"question": "q"}, "observe", {"answer": "a"},
                    1.0, RewardAuthority.OPERATOR, "sha256:source", 0.1,
                    "replay-1",
                )
                service.record(experience)
                record = database.get(
                    "experience-1",
                    scope=MemoryScope("local", "mission-1", "research"),
                )
                self.assertEqual(record.content["action"], "observe")

    def test_replay_is_rejected_before_learner_update_after_restart(self):
        class Learner:
            def __init__(self):
                self.tasks = {}
                self.observations = []

            def register_task(self, task, actions, reward_range):
                self.tasks[task] = type("Task", (), {"actions": tuple(actions)})()

            def observe(self, *args, **kwargs):
                self.observations.append((args, kwargs))

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "memory.sqlite3"
            first = Experience(
                "experience-1", "mission-1", "research", "operator",
                {"question": "q"}, "observe", {"answer": "a"},
                1.0, RewardAuthority.OPERATOR, "sha256:source", 0.1,
                "replay-1",
            )
            with MemoryDatabase(path) as database:
                LearningService(memory_database=database).record(first)

            learner = Learner()
            replay = Experience(
                "experience-2", "mission-1", "research", "operator",
                {"question": "changed"}, "observe", {"answer": "changed"},
                1.0, RewardAuthority.OPERATOR, "sha256:source", 0.1,
                "replay-1",
            )
            with MemoryDatabase(path) as database:
                service = LearningService(
                    experience_learner=learner, memory_database=database
                )
                with self.assertRaises(ValueError):
                    service.record(replay)
            self.assertEqual(learner.observations, [])

    def test_unrewarded_observation_is_memorized_without_learning_reward(self):
        with tempfile.TemporaryDirectory() as directory:
            with MemoryDatabase(Path(directory) / "memory.sqlite3") as database:
                service = LearningService(
                    evidence=EvidenceChain(), memory_database=database
                )
                experience = Experience(
                    "experience-null", "mission-1", "research", "sensor",
                    {"signal": 1}, "observe", {"result": "unscored"},
                    None, RewardAuthority.NONE, "sha256:sensor", 0.4,
                    "replay-null",
                )
                service.record(experience)
                record = database.get(
                    "experience-null",
                    scope=MemoryScope("local", "mission-1", "research"),
                )
                self.assertIsNone(record.content["reward"])
                self.assertFalse(
                    service.evidence.records[-1].payload["reward_applied"]
                )


if __name__ == "__main__":
    unittest.main()
