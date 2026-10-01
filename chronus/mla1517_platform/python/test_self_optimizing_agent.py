"""Behavioral tests for observed self-optimization and proof-gated pruning."""

from __future__ import annotations

import unittest

from chronus.mla1517.mining.self_optimizing_agent import (
    ExclusionCertificate,
    OptimizationObservation,
    OptimizationRejected,
    SelfOptimizingTuner,
    WorkGroupPlan,
)


class SelfOptimizingAgentTests(unittest.TestCase):
    def observation(self, **overrides):
        values = {
            "kernel_latency_ms": 20,
            "kernel_latency_bound_ms": 100,
            "temperature_c": 50,
            "thermal_limit_c": 85,
            "hashes_computed": 1000,
            "elapsed_seconds": 1,
            "power_w": 100,
            "stratum_state": "READY",
            "new_job_observed": False,
        }
        values.update(overrides)
        return OptimizationObservation.from_telemetry(values, observed_at_ns=1)

    def current(self):
        return WorkGroupPlan(1024, 64, 256, "initial observed plan", {})

    def test_headroom_can_increase_only_valid_dimensions(self):
        plan = SelfOptimizingTuner(max_local_size=256).suggest_workgroup(
            self.observation(), current=self.current()
        )
        self.assertEqual(plan.global_size % plan.local_size, 0)
        self.assertLessEqual(plan.local_size, 256)

    def test_thermal_or_latency_overload_reduces_dimensions(self):
        plan = SelfOptimizingTuner().suggest_workgroup(
            self.observation(temperature_c=90, kernel_latency_ms=150), current=self.current()
        )
        self.assertLess(plan.local_size, 64)
        self.assertLess(plan.global_size, 1024)

    def test_live_job_transition_holds_dimensions(self):
        plan = SelfOptimizingTuner().suggest_workgroup(
            self.observation(new_job_observed=True, stratum_state="NEW_JOB"), current=self.current()
        )
        self.assertEqual(plan.local_size, 64)
        self.assertIn("transition", plan.reason)

    def test_schedule_is_complete_without_certificate(self):
        plan = SelfOptimizingTuner().schedule(window=257, seed=9)
        self.assertEqual(len(plan.nonces), 257)
        self.assertEqual(set(plan.nonces), set(range(257)))
        self.assertFalse(plan.pruning_applied)

    def test_pruning_requires_independent_verifier(self):
        certificate = ExclusionCertificate((1, 3), "proof-1", "target-1", True)
        tuner = SelfOptimizingTuner()
        with self.assertRaises(OptimizationRejected):
            tuner.schedule(window=8, seed=0, certificate=certificate)
        plan = tuner.schedule(
            window=8,
            seed=0,
            certificate=certificate,
            proof_verifier=lambda cert, size: cert.proof_reference == "proof-1" and size == 8,
        )
        self.assertTrue(plan.pruning_applied)
        self.assertNotIn(1, plan.nonces)
        self.assertNotIn(3, plan.nonces)
        self.assertEqual(len(plan.nonces), 6)


if __name__ == "__main__":
    unittest.main()
