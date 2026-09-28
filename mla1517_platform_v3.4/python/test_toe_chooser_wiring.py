"""Wiring-contract tests: TOECausalSignal drives the solver start lane and
the coordinator dispatch gate without ever reaching the consensus path.

The signal is feed-forward ordering/gating evidence only. These tests prove
the wire exists (face_bias -> solver start lane, causal_throttle -> dispatch
breadth + throttle latch) and that the proof boundary is never touched.
"""
from __future__ import annotations

import asyncio
import time
import struct
import unittest
from types import SimpleNamespace
from unittest import mock

from manifold_pool_coordinator import PoolEndpoint
import mla1517.mining.pow as pow_module
from mla1517.hardware import VaultRecord
from mla1517.mining.chooser import MiningIntelligenceChooser
from mla1517.mining.coordinator import IntelligentPoolCoordinator, _OBSERVED_WINDOW
from mla1517.mining.solver import M32SearchSolver
from mla1517.mining.toe_adapter import TOEMiningContext
from mla1517.mining.toe_signal import TOECausalSignal

_TORN_RESULT = {
    # entropy above _ENTROPY_THROTTLE -> causal_throttle derived True
    "state_tomography": {"coherence": 0.9, "entropy": 4.5, "energy": 1.0},
    # fisher >= _FISHER_FLOOR at time 1.7 -> face_bias = int(1.7 * 10) % 32 = 17
    "trajectory_prediction": {
        "trend": "rising",
        "trend_rate": 0.1,
        "intervention_points": [
            {"time": 1.7, "fisher_info": 1.0, "is_optimal": True}
        ],
    },
}


def _torn_record() -> VaultRecord:
    return VaultRecord(
        node_id=3,
        sequence=1,
        state=struct.pack("<Q14I", 9, *([0] * 8), 1, 0, 0, 0, 0, 0),
    )


class LaneStartOffsetTests(unittest.TestCase):
    """(a)/(b) solver-level lane-start contract."""

    def test_face_bias_reorders_lane(self):
        solver = M32SearchSolver()
        solver.set_lane_start_offset(17)
        solver.set_lane_start_offset(17)  # idempotent: no additional effect
        self.assertEqual(solver.get_lane_start_offset(), 17)
        nonce, lane = next(solver.candidates(0, 1))
        self.assertEqual(lane, 17)
        self.assertEqual(nonce, 17)

    def test_face_bias_out_of_range_fails_closed(self):
        solver = M32SearchSolver()
        for bad in (-1, 32):
            with self.assertRaises(ValueError):
                solver.set_lane_start_offset(bad)


class ChooserSignalWiringTests(unittest.TestCase):
    """(c) choose() consumes face_bias only for valid signals."""

    def test_invalid_signal_is_noop(self):
        solver = M32SearchSolver()
        solver.set_lane_start_offset(5)
        chooser = MiningIntelligenceChooser()
        torn = TOECausalSignal(face_bias=9, coherence=0.0, entropy=0.0)
        self.assertFalse(torn.is_valid())
        chooser.choose(has_job=True, toe_signal=torn, solver=solver)
        self.assertEqual(solver.get_lane_start_offset(), 5)

    def test_valid_signal_sets_start_lane_without_changing_lead(self):
        solver = M32SearchSolver()
        chooser = MiningIntelligenceChooser()
        signal = TOECausalSignal(face_bias=9, coherence=0.9, entropy=0.1)
        self.assertTrue(signal.is_valid())
        decision = chooser.choose(has_job=True, toe_signal=signal, solver=solver)
        self.assertEqual(solver.get_lane_start_offset(), 9)
        nonce, lane = next(solver.candidates(0, 1))
        self.assertEqual(lane, 9)
        # face_bias must not alter the lead selection on an unstructured window
        self.assertEqual(decision.lead, "flat_exhaustive")

    def test_no_signal_is_noop(self):
        solver = M32SearchSolver()
        chooser = MiningIntelligenceChooser()
        chooser.choose(has_job=True, toe_signal=None, solver=solver)
        self.assertEqual(solver.get_lane_start_offset(), 0)
        nonce, lane = next(solver.candidates(0, 1))
        self.assertEqual(lane, 0)


class CoordinatorThrottleWiringTests(unittest.TestCase):
    """(d)/(e) causal_throttle gates dispatch breadth, never consensus."""

    def _coordinator(self, result):
        coord = IntelligentPoolCoordinator(
            [PoolEndpoint("127.0.0.1", 3333, "stub")],
            username="u",
            password="x",
        )
        job = SimpleNamespace(
            job_id="job-toe-wiring",
            params=("job-toe-wiring", "00" * 32, "cb1", "cb2"),
            received_at=1.0,
        )
        coord.client = SimpleNamespace(latest_job=lambda: job)
        context = TOEMiningContext(
            job_id="job-toe-wiring",
            node_id=0,
            sequence=1,
            result=result,
            execution_evidence={"backend": "stub"},
        )
        coord.toe = SimpleNamespace(analyse=lambda **kwargs: context)
        return coord

    def test_throttle_pauses_polling_but_never_latches(self):
        # A throttle that stopped vault polling for good would also stop the
        # observations that clear it: the worker would wedge while alive.
        coord = self._coordinator(_TORN_RESULT)
        asyncio.run(coord.submit_record(_torn_record()))
        self.assertTrue(coord.work_throttled)
        self.assertFalse(coord.submit_enabled)
        coord.throttle_probe_s = 0.05
        self.assertFalse(asyncio.run(coord.before_hardware_poll()))
        time.sleep(0.06)
        self.assertTrue(asyncio.run(coord.before_hardware_poll()))
        self.assertTrue(coord.work_throttled)  # only a HOLD observation clears it

    def test_causal_throttle_halves_breadth(self):
        coord = self._coordinator(_TORN_RESULT)
        baseline = len(coord._observed_candidate_window())
        self.assertEqual(baseline, _OBSERVED_WINDOW)
        accepted = asyncio.run(coord.submit_record(_torn_record()))
        self.assertFalse(accepted)  # record state is never a share
        self.assertTrue(coord.mining_intelligence.throttle)
        self.assertTrue(coord.work_throttled)
        self.assertEqual(coord._dispatch_breadth, baseline // 2)
        self.assertEqual(len(coord._observed_candidate_window()), baseline // 2)
        event = coord.purity_torn_events[-1]
        self.assertEqual(event["event"], "PURITY_TORN")
        self.assertEqual(event["entropy"], 4.5)
        self.assertEqual(event["purity"], 0.9)
        self.assertEqual(event["face_bias"], 17)
        # The same dispatch applied face_bias to the solver start lane.
        self.assertEqual(coord.solver.get_lane_start_offset(), 17)
        self.assertIsNotNone(coord.last_toe_signal)
        self.assertIsNotNone(coord.last_toe_signal.ladder)

    def test_throttle_does_not_touch_consensus(self):
        coord = self._coordinator(_TORN_RESULT)
        boom = AssertionError("consensus path reached from throttle wiring")
        with mock.patch.object(pow_module, "sha256d", side_effect=boom), \
             mock.patch.object(pow_module, "check_pow", side_effect=boom), \
             mock.patch.object(pow_module, "compact_target", side_effect=boom):
            accepted = asyncio.run(coord.submit_record(_torn_record()))
        self.assertFalse(accepted)
        self.assertTrue(coord.mining_intelligence.throttle)


if __name__ == "__main__":
    unittest.main()
