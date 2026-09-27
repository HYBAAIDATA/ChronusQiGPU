"""Behavioral tests for the Phase 1 intelligence controller ABI."""

from __future__ import annotations

import unittest

from mla1517.mining.intelligence_controller import ControlCommand, IntelligenceController
from mla1517.mining.toe_context import TOEContextBuilder, TOEContextUnavailable


def context():
    return (
        TOEContextBuilder()
        .with_job({"job_id": "live-job", "notify": ["observed"]})
        .with_hardware_state(bytes(64))
        .with_coordinates(lane_id=1, node_id=2, sequence=3, watermark=4)
        .with_telemetry({"source": "observed"})
        .build()
    )


class IntelligenceControllerTests(unittest.TestCase):
    def test_normal_telemetry_emits_hold(self):
        decision = IntelligenceController().evaluate(
            context=context(),
            telemetry={
                "kernel_latency_ms": 20.0,
                "temperature_c": 60.0,
                "stratum_state": "READY",
            },
            observed_at_ns=10,
        )
        self.assertEqual([signal.command for signal in decision.signals], [ControlCommand.HOLD])

    def test_new_job_emits_stale_lane_flush(self):
        decision = IntelligenceController().evaluate(
            context=context(),
            telemetry={"new_job_observed": True, "stratum_state": "NEW_JOB"},
            observed_at_ns=10,
        )
        self.assertEqual(decision.signals[0].command, ControlCommand.FLUSH_LANE)

    def test_latency_and_thermal_bounds_emit_resize(self):
        decision = IntelligenceController().evaluate(
            context=context(),
            telemetry={
                "kernel_latency_ms": 110.0,
                "kernel_latency_bound_ms": 100.0,
                "temperature_c": 90.0,
                "thermal_limit_c": 85.0,
            },
            observed_at_ns=10,
        )
        self.assertEqual(
            [signal.command for signal in decision.signals],
            [ControlCommand.RESIZE_WORKGROUP, ControlCommand.RESIZE_WORKGROUP],
        )

    def test_pruning_requires_explicit_coverage_preserving_evidence(self):
        base = {"kernel_latency_ms": 10.0, "temperature_c": 40.0}
        no_proof = IntelligenceController().evaluate(
            context=context(),
            telemetry={**base, "proven_exclusion": {"excluded_count": 3}},
            observed_at_ns=10,
        )
        self.assertNotIn(
            ControlCommand.PRUNE_WINDOW, [signal.command for signal in no_proof.signals]
        )
        with_proof = IntelligenceController().evaluate(
            context=context(),
            telemetry={
                **base,
                "proven_exclusion": {
                    "excluded_count": 3,
                    "proof_reference": "coverage-proof-1",
                    "complete_coverage_preserved": True,
                },
            },
            observed_at_ns=10,
        )
        self.assertIn(
            ControlCommand.PRUNE_WINDOW, [signal.command for signal in with_proof.signals]
        )

    def test_missing_telemetry_fails_closed(self):
        with self.assertRaises(TOEContextUnavailable):
            IntelligenceController().evaluate(context=context(), telemetry={}, observed_at_ns=10)


if __name__ == "__main__":
    unittest.main()
