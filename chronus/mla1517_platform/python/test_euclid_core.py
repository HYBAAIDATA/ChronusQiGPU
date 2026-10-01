import unittest

from euclid_core import EuclidCoreBandit


class EuclidCoreTests(unittest.TestCase):
    def test_candidate_masks_are_declared_and_measured_deterministic(self):
        first = EuclidCoreBandit(seed=7)
        second = EuclidCoreBandit(seed=7)
        self.assertEqual(first.select_optimal_mask(), second.select_optimal_mask())
        self.assertEqual(
            set(first.CANDIDATE_MASKS), {"A_baseline", "B_shifted", "C_sparse", "E_dense"}
        )

    def test_rewards_update_and_are_bounded(self):
        bandit = EuclidCoreBandit()
        bandit.register_reward("A_baseline", 4.0)
        bandit.register_reward("A_baseline", -2.0)
        bandit.register_reward("A_baseline", 10.0)
        stats = bandit.snapshot()["A_baseline"]
        self.assertEqual(stats["observations"], 3)
        self.assertEqual(stats["total_reward"], 12.0)
        self.assertEqual(stats["mean_reward"], 4.0)
        with self.assertRaises(ValueError):
            bandit.register_reward("A_baseline", float("nan"))
