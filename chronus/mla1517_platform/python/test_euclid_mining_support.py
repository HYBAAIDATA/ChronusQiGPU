"""Contract tests for the EUCLID production-mining support seam."""
from __future__ import annotations

import tempfile
import unittest

from chronus.mla1517.mining.euclid_support import EuclidMiningSupport


class _Learner:
    def __init__(self, action: str) -> None:
        self.action = action
        self.observations = []

    def select_action(self, task_id, state, *, explore=False):
        assert explore is False
        return self.action

    def observe(self, *args, **kwargs):
        self.observations.append((args, kwargs))


class EuclidMiningSupportTests(unittest.TestCase):
    def _support(self, baseline: int = 64) -> EuclidMiningSupport:
        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=True)
        tmp.close()
        return EuclidMiningSupport(baseline, state_path=tmp.name)

    def test_missing_euclid_is_explicit_and_neutral(self):
        support = self._support()
        support.available = False
        support.learner = None
        support.unavailable_reason = "test: package absent"
        advice = support.advise(None, recovery_mode="NORMAL", hashrate_hs=None)
        self.assertEqual(advice.state, "UNAVAILABLE")
        self.assertEqual(advice.action, "hold")
        self.assertEqual(advice.dispatch_breadth, 64)
        self.assertIn("package absent", advice.reason)

    def test_no_submission_evidence_produces_no_reward(self):
        self.assertIsNone(EuclidMiningSupport.reward({"outcomes": {}}))
        self.assertIsNone(
            EuclidMiningSupport.reward(
                {
                    "outcomes": {
                        "accepted_ratio": None,
                        "rejected_ratio": None,
                        "unknown_ratio": None,
                        "stale_ratio": None,
                    }
                }
            )
        )

    def test_reward_uses_only_observed_outcome_ratios(self):
        reward = EuclidMiningSupport.reward(
            {
                "outcomes": {
                    "accepted_ratio": 0.95,
                    "rejected_ratio": 0.02,
                    "unknown_ratio": 0.01,
                    "stale_ratio": 0.01,
                }
            }
        )
        self.assertAlmostEqual(reward, 0.91)

    def test_reduce_is_bounded_to_half_baseline(self):
        support = self._support(80)
        support.available = True
        support.learner = _Learner("reduce")
        advice = support.advise(
            {"ready": True, "outcomes": {}},
            recovery_mode="NORMAL",
            hashrate_hs=100_000,
        )
        self.assertEqual(advice.state, "ACTIVE")
        self.assertEqual(advice.dispatch_breadth, 40)

    def test_restore_never_exceeds_baseline(self):
        support = self._support(80)
        support.current_breadth = 40
        support.available = True
        support.learner = _Learner("restore")
        advice = support.advise(
            {"ready": True, "outcomes": {}},
            recovery_mode="NORMAL",
            hashrate_hs=100_000,
        )
        self.assertEqual(advice.dispatch_breadth, 80)
        self.assertLessEqual(advice.dispatch_breadth, support.baseline_breadth)

    def test_learning_requires_new_observed_outcome(self):
        support = self._support(32)
        learner = _Learner("hold")
        support.available = True
        support.learner = learner
        support.advise(
            {"ready": True, "outcomes": {}},
            recovery_mode="NORMAL",
            hashrate_hs=100_000,
        )
        self.assertEqual(learner.observations, [])
        observed = {
            "ready": True,
            "counters": {"submitted": 1, "accepted": 1, "rejected": 0, "unknown": 0},
            "outcomes": {
                "accepted_ratio": 1.0,
                "rejected_ratio": 0.0,
                "unknown_ratio": 0.0,
                "stale_ratio": 0.0,
                "stale_dropped": 0,
            },
        }
        support.advise(observed, recovery_mode="NORMAL", hashrate_hs=100_000)
        self.assertEqual(len(learner.observations), 1)
        # Polling the same snapshot again must not replay the same pool result.
        support.advise(observed, recovery_mode="NORMAL", hashrate_hs=100_000)
        self.assertEqual(len(learner.observations), 1)

    def test_changed_outcome_generation_is_learned_once(self):
        support = self._support(32)
        learner = _Learner("hold")
        support.available = True
        support.learner = learner
        support.advise({"ready": True, "outcomes": {}}, recovery_mode="NORMAL", hashrate_hs=1)
        first = {
            "counters": {"submitted": 1, "accepted": 1, "rejected": 0, "unknown": 0},
            "outcomes": {"accepted_ratio": 1.0, "rejected_ratio": 0.0, "unknown_ratio": 0.0, "stale_ratio": 0.0, "stale_dropped": 0},
        }
        second = {
            "counters": {"submitted": 2, "accepted": 1, "rejected": 1, "unknown": 0},
            "outcomes": {"accepted_ratio": 0.5, "rejected_ratio": 0.5, "unknown_ratio": 0.0, "stale_ratio": 0.0, "stale_dropped": 0},
        }
        support.advise(first, recovery_mode="NORMAL", hashrate_hs=1)
        support.advise(second, recovery_mode="NORMAL", hashrate_hs=1)
        self.assertEqual(len(learner.observations), 2)


    def test_real_salamander_observation_feeds_bounded_euclid_and_pythia(self):
        """One real owner observer, one EUCLID advisory, one PYTHIA correlation.

        A heartbeat is never relabelled completed healing or canonical custody.
        """
        from pathlib import Path
        from types import SimpleNamespace
        from chronus.mla1517.mining.geodesic_support import (
            PythiaProductionMiningCoordinator,
        )
        from salamander.runtime import MiningAutonomyBridge

        with tempfile.TemporaryDirectory() as folder:
            bridge = MiningAutonomyBridge(Path(folder) / "salamander.jsonl")
            outcome = bridge.observe_mining_snapshot({
                "schema": "pythia.mining_evidence/1",
                "lifecycle": {
                    "transport_connected": True,
                    "subscribed": True,
                    "authorized": True,
                    "job_available": True,
                    "target_available": True,
                },
                "recovery": {"faulted": False},
                "optimization": {},
                "last_execution": {},
            })
            self.assertTrue(outcome["classification"]["WIRED"])
            self.assertEqual(
                outcome["evidence_custody"], "LOCAL_MIRROR_NOT_CANONICAL_THESEUS",
            )
            learner = _Learner("hold")
            support = EuclidMiningSupport(
                32, state_path=str(Path(folder) / "policy.json"), learner=learner,
            )
            root = PythiaProductionMiningCoordinator.__new__(
                PythiaProductionMiningCoordinator
            )
            root.euclid_support = support
            root.pythia_authority = SimpleNamespace(
                last_agentic_cycle={"stages": {"SEARCH": {"state": "COMPLETE"}}},
            )
            root.last_execution = {"executed": True}
            root.record_salamander_autonomy(outcome)
            advice = support.advise(
                {"ready": True, "outcomes": {}},
                recovery_mode="NORMAL", hashrate_hs=123_000,
            )
            self.assertEqual(advice.state, "ACTIVE")
            self.assertIn("salamander_health", advice.evidence["state"])
            self.assertEqual(
                advice.evidence["state"]["salamander_health"], outcome["health"],
            )
            self.assertEqual(
                root.pythia_authority.last_agentic_cycle["stages"]["HEAL_OPTIMISE"]["state"],
                "OBSERVED",
            )
            self.assertFalse(
                root.pythia_authority.last_agentic_cycle["stages"]["HEAL_OPTIMISE"]["healing_proved"],
            )
            self.assertEqual(root.last_execution["salamander_evidence_head"], outcome["evidence_head"])
            self.assertTrue(1 <= advice.dispatch_breadth <= 32)
            self.assertIsNone(support.reward({}))

    def test_unverified_salamander_is_not_promoted_into_euclid_state(self):
        with tempfile.TemporaryDirectory() as folder:
            support = EuclidMiningSupport(
                32, state_path=str(__import__("pathlib").Path(folder) / "policy.json"),
                learner=_Learner("hold"),
            )
            self.assertFalse(support.observe_salamander({
                "schema": "other",
                "health": "HEALTHY",
                "evidence_head": "forged",
                "classification": {"WIRED": True, "SELF_HEALING": True},
            }))
            advice = support.advise(
                {"ready": True, "outcomes": {}},
                recovery_mode="NORMAL", hashrate_hs=100_000,
            )
            self.assertEqual(
                advice.evidence["state"]["salamander_health"], "UNAVAILABLE",
            )
            self.assertFalse(support.snapshot()["salamander_observation"]["available"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
