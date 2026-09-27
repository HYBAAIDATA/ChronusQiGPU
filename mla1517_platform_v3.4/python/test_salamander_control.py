import unittest

from salamander_control import (
    FAILOVER_COOLDOWN_MS,
    FaultBucket,
    FailoverState,
    McLarenController,
    MichieController,
    NonceLedger,
)
from salamander_engine import SalamanderEngine


class SalamanderControlTests(unittest.TestCase):
    def test_bucket_decays_and_rearms(self):
        bucket = FaultBucket()
        bucket.update([3] + [0] * 31, 0)
        self.assertEqual(bucket.level[0], 3)
        bucket.armed[0] = False
        bucket.level[0] = 0.1
        bucket.update([3] + [0] * 31, 60000)
        self.assertTrue(bucket.armed[0])

    def test_lane_floor_degrades_without_excising(self):
        bucket = FaultBucket()
        bucket.level[0] = 3.0
        bucket.armed[0] = True
        state = McLarenController().state
        state.active = [i < 24 for i in range(32)]
        controller = McLarenController(state)
        calls = []
        actions = controller.step(
            bucket,
            NonceLedger(),
            1000,
            lambda mask: calls.append(mask) or True,
            lambda lane: True,
        )
        self.assertIn("degraded_mode", actions)
        self.assertEqual(sum(controller.state.active), 24)
        self.assertEqual(calls, [])

    def test_retirement_requires_ack(self):
        bucket = FaultBucket()
        bucket.level[4] = 3.0
        bucket.armed[4] = True
        controller = McLarenController()
        calls = []
        actions = controller.step(
            bucket,
            NonceLedger(),
            1000,
            lambda mask: calls.append(mask) or False,
            lambda lane: True,
        )
        self.assertEqual(actions, [])
        self.assertTrue(controller.state.active[4])
        self.assertEqual(len(calls), 1)

    def test_michie_dwell_accepts_improvement(self):
        controller = MichieController(dwell_ms=100)
        calls = []
        snapshot = {"hashes_tested": [1] * 32, "faults": [0] * 32}
        actions = controller.step(
            current_mask=0xFFFF,
            snapshot=snapshot,
            now_ms=0,
            commit_poly_mask=lambda mask: calls.append(mask) or True,
        )
        self.assertEqual(len(calls), 1)
        self.assertTrue(controller.state.pending)
        improved = {"hashes_tested": [2] * 32, "faults": [0] * 32}
        actions = controller.step(
            current_mask=calls[0],
            snapshot=improved,
            now_ms=100,
            commit_poly_mask=lambda mask: calls.append(mask) or True,
        )
        self.assertTrue(any(action.startswith("accept:") for action in actions))
        self.assertFalse(controller.state.pending)

    def test_failover_cooldown(self):
        state = FailoverState()
        self.assertTrue(state.should_switch(4, 0))
        self.assertFalse(state.should_switch(4, 1))
        self.assertFalse(state.should_switch(4, FAILOVER_COOLDOWN_MS - 1))
        self.assertTrue(state.primary_may_resume(10_000))

    def test_cursor_imbalance_uses_chi_square_threshold(self):
        balanced = [100] * 20
        skewed = [0] * 19 + [2000]
        self.assertFalse(SalamanderEngine._imbalanced(balanced))
        self.assertTrue(SalamanderEngine._imbalanced(skewed))
