from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from chronus.mla1517.mining.closed_loop import ClosedLoopOptimizer
from chronus.mla1517.mining.recovery_authority import RecoveryGovernor, RecoveryState


def observe(opt, route, window, rate, state="COMPLETE", error=None):
    opt.observe(
        route=route,
        planned_window=window,
        completed_work=window if state != "DEVICE_ERROR" else 0,
        elapsed_seconds=(window / rate) if rate else 0.001,
        completion_state=state,
        device_error=error,
    )


def baseline(opt, route="cpu_reference", window=64, rate=100.0):
    assert opt.select(route=route, proposed_window=window) == window
    for _ in range(3):
        observe(opt, route, window, rate)


class ClosedLoopRuntimeTests(unittest.TestCase):
    def test_better_candidate_is_measured_and_retained(self):
        opt = ClosedLoopOptimizer(min_samples=3, min_improvement=0.05)
        baseline(opt)
        self.assertEqual(opt.select(route="cpu_reference", proposed_window=128), 128)
        for _ in range(3):
            observe(opt, "cpu_reference", 128, 120.0)
        self.assertEqual(opt.active["cpu_reference"], 128)
        self.assertIs(opt.history[-1].accepted, True)

    def test_worse_candidate_rolls_back_and_cools_down(self):
        opt = ClosedLoopOptimizer(min_samples=3, min_improvement=0.05, cooldown_windows=2)
        baseline(opt)
        self.assertEqual(opt.select(route="cpu_reference", proposed_window=128), 128)
        for _ in range(3):
            observe(opt, "cpu_reference", 128, 90.0)
        self.assertEqual(opt.active["cpu_reference"], 64)
        self.assertTrue(opt.history[-1].rollback)
        self.assertEqual(opt.select(route="cpu_reference", proposed_window=128), 64)

    def test_route_fallback_cannot_validate_candidate(self):
        opt = ClosedLoopOptimizer(min_samples=3)
        baseline(opt, route="opencl_m32")
        self.assertEqual(opt.select(route="opencl_m32", proposed_window=128), 128)
        opt.observe(
            route="opencl_m32", executed_route="cpu_reference",
            planned_window=128, completed_work=128, elapsed_seconds=0.1,
            completion_state="FALLBACK_COMPLETE",
        )
        self.assertEqual(opt.active["opencl_m32"], 64)
        self.assertTrue(opt.history[-1].rollback)
        self.assertIn("fell back", opt.history[-1].reason)

    def test_device_failure_rolls_back_immediately(self):
        opt = ClosedLoopOptimizer(min_samples=3)
        baseline(opt)
        self.assertEqual(opt.select(route="cpu_reference", proposed_window=128), 128)
        observe(opt, "cpu_reference", 128, 0, "DEVICE_ERROR", "accelerator lost")
        self.assertEqual(opt.active["cpu_reference"], 64)
        self.assertIn("accelerator lost", opt.history[-1].reason)

    def test_accepted_configuration_survives_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "optimisation.json"
            opt = ClosedLoopOptimizer(min_samples=3, min_improvement=0.05, state_path=path)
            baseline(opt)
            self.assertEqual(opt.select(route="cpu_reference", proposed_window=128), 128)
            for _ in range(3):
                observe(opt, "cpu_reference", 128, 120.0)
            restored = ClosedLoopOptimizer(state_path=path)
            self.assertEqual(restored.active["cpu_reference"], 128)
            self.assertIs(restored.history[-1].accepted, True)
            self.assertEqual(restored.min_improvement, 0.05)

    def test_healing_executes_and_requires_fresh_healthy_observation(self):
        state = {"healthy": False, "acted": False}
        governor = RecoveryGovernor(fail_after=2)
        recovery = governor.propose(["RESTART_LANE"], "worker fault")
        self.assertIsNotNone(recovery)

        def repair():
            state["acted"] = True
            state["healthy"] = True
            return "RESTART_LANE"

        governor.dispatch(recovery, [("RESTART_LANE", repair)])
        self.assertNotEqual(recovery.state, RecoveryState.VERIFIED)
        governor.observe(state["healthy"])
        self.assertTrue(state["acted"])
        self.assertEqual(recovery.state, RecoveryState.VERIFIED)

    def test_failed_healing_escalates_to_faulted(self):
        governor = RecoveryGovernor(fail_after=2)
        recovery = governor.propose(["RESTART_LANE"], "persistent fault")
        governor.dispatch(recovery, [("RESTART_LANE", lambda: "RESTART_LANE")])
        governor.observe(False)
        governor.observe(False)
        self.assertEqual(recovery.state, RecoveryState.FAILED)
        self.assertEqual(governor.mode, "FAULTED")

    def test_incomplete_work_is_not_accepted_as_improvement(self):
        opt = ClosedLoopOptimizer(min_samples=3)
        baseline(opt)
        opt.select(route="cpu_reference", proposed_window=128)
        for _ in range(4):
            opt.observe(
                route="cpu_reference", planned_window=128, completed_work=64,
                elapsed_seconds=0.01, completion_state="INVALIDATED"
            )
        self.assertIsNotNone(opt.trial)
        self.assertEqual(
            opt.snapshot()["last_observation"]["useful_work_per_second"], "Unavailable"
        )


if __name__ == "__main__":
    unittest.main()
