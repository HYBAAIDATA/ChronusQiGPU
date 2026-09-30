"""Contract tests for the EUCLID production-mining support seam."""
from __future__ import annotations

import tempfile
import unittest

from mla1517.mining.euclid_support import EuclidMiningSupport


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
        support = EuclidMiningSupport(baseline, state_path=tmp.name)
        return support

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

    def test_learning_requires_a_previous_action_and_observed_outcome(self):
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
        support.advise(
            {
                "ready": True,
                "outcomes": {
                    "accepted_ratio": 1.0,
                    "rejected_ratio": 0.0,
                    "unknown_ratio": 0.0,
                    "stale_ratio": 0.0,
                },
            },
            recovery_mode="NORMAL",
            hashrate_hs=100_000,
        )
        self.assertEqual(len(learner.observations), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
