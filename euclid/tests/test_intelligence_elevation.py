"""Decisive end-to-end proof for the intelligence-elevation wiring.

Proves the chartered chain with real implementations (no mocks in the core
intelligence path):

startup -> cognition request -> governed dispatch -> real implementation ->
measurable effect -> feedback -> learning -> persistence -> restart ->
replay -> transfer attempt on a structurally related problem.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from euclid.contracts import Authority
from euclid.governance import Organ
from euclid.runtime import EuclidRuntime

FIXED_CLOCK = lambda: 1700000000.0  # noqa: E731 - deterministic test clock

# Two structurally related but textually unrelated programs: both are
# "build a list in a loop then return it" with no annotations.
PROBLEM_A_CODE = """def transform_records(records):
    results = []
    for record in records:
        results.append(record * 2)
    return results
"""
PROBLEM_B_CODE = """def collect_metrics(samples):
    aggregates = []
    for sample in samples:
        aggregates.append(sample + 1)
    return aggregates
"""
TEST_CODE = "assert transform_records([1, 2]) == [2, 4]"  # behaviour guard for A
TEST_CODE_B = "assert collect_metrics([1, 2]) == [2, 3]"


def _problem(pid: str, code: str, test: str, seed: int = 7) -> dict:
    return {
        "problem_id": pid,
        "goal": "improve measured fitness with tests passing",
        "code": code,
        "external_test_code": test,
        "seed": seed,
    }


class TestEndToEndWiring(unittest.TestCase):
    def test_startup_to_transfer_full_chain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # STARTUP
            runtime = EuclidRuntime.production(creator_id="creator-1", state_dir=tmp)
            service = runtime.enable_intelligence(
                seed=7, clock=FIXED_CLOCK, software_revision="test-rev-1"
            )
            report = runtime.startup_report()
            organ_ids = {organ["organ_id"] for organ in report["organs"]}
            self.assertIn("euclid-engine", organ_ids)

            # COGNITION REQUEST -> DISPATCH -> REAL IMPLEMENTATION -> EFFECT
            episode_a = service.solve(
                _problem("prog-A", PROBLEM_A_CODE, TEST_CODE),
                budget_evaluations=8,
            )
            kinds = [record.kind for record in runtime.evidence.records]
            self.assertIn("delegation-result", kinds)  # real governed dispatch
            self.assertTrue(any(k.startswith("cognition-") for k in kinds))
            self.assertIn(episode_a.outcome, ("solved", "stalled", "unexecuted"))
            phases = [t["phase"] for t in episode_a.state_payload["transitions"]]
            for required in ("represent", "retrieve", "analogy", "abduce",
                             "deduce", "discriminate", "strategy", "plan",
                             "compose", "imagine", "rank", "execute",
                             "compare", "metacontrol", "learn", "terminate"):
                self.assertIn(required, phases, f"missing phase {required}")
            # measurable effect: a governed search ran and reported telemetry
            self.assertIn("measured_improvement", episode_a.actual_result)

            # FEEDBACK -> LEARNING
            status = runtime.learning.status()
            self.assertGreaterEqual(status["experiences_seen"], 1)

            # PERSISTENCE
            episode_path = Path(tmp) / "cognition" / "episodes" / "prog-A.json"
            self.assertTrue(episode_path.is_file())
            checkpoint = Path(tmp) / "runtime.checkpoint.json"
            runtime.save(checkpoint)
            runtime.close()

            # RESTART
            restored = EuclidRuntime.restore(checkpoint, state_dir=tmp)
            self.assertIsNotNone(restored.learning.memory_database)
            service2 = restored.enable_intelligence(
                seed=7, clock=FIXED_CLOCK, software_revision="test-rev-1"
            )
            # world model and strategy stats survived the restart
            self.assertTrue(service2.world_model.to_dict()["table"])
            # episodic memory hydrated from the sealed episode
            self.assertTrue(service2.memory.retrieve(frozenset()))

            # TRANSFER ATTEMPT: structurally related, textually different problem
            episode_b = service2.solve(
                _problem("prog-B", PROBLEM_B_CODE, TEST_CODE_B),
                budget_evaluations=8,
            )
            analogy_sources = [a["source_ref"] for a in episode_b.analogies]
            self.assertIn(
                "episode:prog-A", analogy_sources,
                "transfer episode must retrieve the structurally similar prior",
            )
            restored.close()

    def test_replay_determinism(self) -> None:
        seals = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as tmp:
                runtime = EuclidRuntime.production(creator_id="creator-1", state_dir=tmp)
                service = runtime.enable_intelligence(
                    seed=7, clock=FIXED_CLOCK, software_revision="test-rev-1"
                )
                episode = service.solve(
                    _problem("prog-A", PROBLEM_A_CODE, TEST_CODE),
                    budget_evaluations=8,
                )
                seals.append(episode.to_payload()["seal"])
                runtime.close()
        self.assertEqual(seals[0], seals[1], "episode replay must be deterministic")

    def test_execution_fails_closed_without_rights(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = EuclidRuntime.production(creator_id="creator-1", state_dir=tmp)
            service = runtime.enable_intelligence(seed=7, clock=FIXED_CLOCK)
            runtime.rights.revoke("creator-1", "euclid-engine", "search", "dispatch")
            with self.assertRaises(PermissionError):
                runtime.delegator.dispatch(
                    "euclid-engine", "search",
                    {"op_kind": "search", "strategy": "greedy-surrogate",
                     "code": PROBLEM_A_CODE, "target": "x", "seed": 7,
                     "budget_evaluations": 2, "signature": []},
                    confident=True, safe=True,
                )
            runtime.close()

    def test_episode_tamper_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime = EuclidRuntime.production(creator_id="creator-1", state_dir=tmp)
            service = runtime.enable_intelligence(seed=7, clock=FIXED_CLOCK)
            episode = service.solve(
                _problem("prog-A", PROBLEM_A_CODE, TEST_CODE), budget_evaluations=6
            )
            from euclid.cognition.episode import CognitiveEpisode
            payload = episode.to_payload()
            payload["outcome"] = "solved" if episode.outcome != "solved" else "stalled"
            with self.assertRaises(ValueError):
                CognitiveEpisode.from_payload(payload)
            runtime.close()


if __name__ == "__main__":
    unittest.main()
