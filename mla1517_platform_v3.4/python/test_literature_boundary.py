from __future__ import annotations

import hashlib
import unittest
from pathlib import Path
from types import SimpleNamespace

from coordinator import CoordinatorControlRouter
from mla1517.mining.intelligence_controller import ControlCommand, IntelligenceController
from mla1517.mining.lane import (
    KERNEL_BETA_MIDSTATE,
    WORK_WINDOW_MAX_S,
    Partition,
    ScheduleFingerprint,
    SearchPolicy,
    build_lane_descriptor,
)
from mla1517.mining.stratum_adapter import StratumAdapterError, StratumProofAdapter


ROOT = Path(__file__).resolve().parents[2]


def context():
    return SimpleNamespace(
        synthetic=False,
        sequence=7,
        stratum_job={"job_id": "job-1"},
        observation=lambda: {"job_id": "job-1"},
    )


class LiteratureBoundaryTests(unittest.TestCase):
    def test_partition_validation_rejects_malformed_inputs(self):
        cases = (
            {"nonce_start": 10, "nonce_end": 10},
            {"stride": 0},
            {"extra_nonce_start": 4, "extra_nonce_end": 3},
            {"ntime_variation": -1},
        )
        for updates in cases:
            params = {"nonce_start": 0, "nonce_end": 99, "stride": 1,
                      "extra_nonce_start": 0, "extra_nonce_end": 1,
                      "ntime_variation": 0}
            params.update(updates)
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                Partition("device-1", **params)

    def test_partition_carries_extra_nonce_and_timestamp_contract(self):
        partition = Partition("device-1", 0, 99, extra_nonce_end=3, ntime_variation=60)
        self.assertEqual(partition.extra_nonce_end, 3)
        self.assertEqual(partition.ntime_variation, 60)

    def test_schedule_fingerprint_is_deterministic(self):
        partition = Partition("device-1", 0, 99, extra_nonce_end=3)
        schedule = ScheduleFingerprint(k_hash=2, merkle_recompute=True)
        self.assertEqual(schedule.fingerprint_bytes(partition), schedule.fingerprint_bytes(partition))
        self.assertEqual(hashlib.sha256(schedule.fingerprint_bytes(partition)).digest(), hashlib.sha256(schedule.fingerprint_bytes(partition)).digest())

    def test_schedule_fingerprint_changes_alpha_merkle(self):
        partition = Partition("device-1", 0, 99)
        self.assertNotEqual(
            ScheduleFingerprint(merkle_recompute=False).fingerprint_bytes(partition),
            ScheduleFingerprint(merkle_recompute=True).fingerprint_bytes(partition),
        )

    def test_schedule_fingerprint_changes_beta_midstate(self):
        partition = Partition("device-1", 0, 99)
        full_cost = ScheduleFingerprint(midstate_reuse=False, kernel_beta_midstate=1.0)
        reused = ScheduleFingerprint(midstate_reuse=True, kernel_beta_midstate=KERNEL_BETA_MIDSTATE)
        self.assertNotEqual(full_cost.fingerprint_bytes(partition), reused.fingerprint_bytes(partition))

    def test_ntime_anomaly_boundary(self):
        controller = IntelligenceController(default_ntime_tolerance_seconds=60)
        at_edge = controller.evaluate(context=context(), telemetry={"ntime": 1060, "job_ntime": 1000}, observed_at_ns=1)
        beyond = controller.evaluate(context=context(), telemetry={"ntime": 1061, "job_ntime": 1000}, observed_at_ns=2)
        normal = controller.evaluate(context=context(), telemetry={"ntime": 1040, "job_ntime": 1000}, observed_at_ns=3)
        self.assertNotIn(ControlCommand.PAUSE, [s.command for s in at_edge.signals])
        self.assertIn(ControlCommand.PAUSE, [s.command for s in beyond.signals])
        self.assertNotIn(ControlCommand.PAUSE, [s.command for s in normal.signals])

    def test_pause_routing_has_one_backpressure_side_effect_and_provenance(self):
        decision = IntelligenceController(default_ntime_tolerance_seconds=60).evaluate(
            context=context(), telemetry={"ntime": 1061, "job_ntime": 1000}, observed_at_ns=1
        )
        pause = [s for s in decision.signals if s.command == ControlCommand.PAUSE]
        self.assertEqual(len(pause), 1)
        self.assertIn("model_versions", pause[0].evidence)

        class Sink:
            def __init__(self):
                self.calls = []

            def apply_backpressure(self, **kwargs):
                self.calls.append(("apply_backpressure", kwargs))

        sink = Sink()
        routed = CoordinatorControlRouter().dispatch_signal(sink, pause[0])
        self.assertEqual(routed, "PAUSE")
        self.assertEqual([name for name, _ in sink.calls], ["apply_backpressure"])
        self.assertEqual(sink.calls[0][1]["evidence"]["model_versions"]["intelligence_controller"], "1.1.0")

    def test_work_window_bound_is_enforced_at_job_receipt(self):
        adapter = StratumProofAdapter()
        job = SimpleNamespace(job_id="job-1", clean_jobs=True)
        with self.assertRaises(StratumAdapterError):
            adapter.on_job_received(job, work_window_seconds=WORK_WINDOW_MAX_S + 1)

    def test_schedule_fingerprint_rejects_window_over_bound(self):
        with self.assertRaises(ValueError):
            ScheduleFingerprint(work_window_seconds=WORK_WINDOW_MAX_S + 1)

    def test_strict_boundary_names_all_review_categories(self):
        content = (ROOT / "STRICT_QUANTUM_BOUNDARY.md").read_text(encoding="utf-8")
        for category in (
            "SHA256d mining boundary",
            "Quantum-search theory",
            "Signature migration",
            "Quantum-sampling PoW",
            "Proof-of-quantum-work blockchains",
            "QRNG claims",
        ):
            self.assertIn(category, content)

    def test_descriptor_does_not_claim_quantum_execution(self):
        descriptor = build_lane_descriptor(SearchPolicy())
        self.assertEqual(descriptor["proof"], "sha256d")
        self.assertIn("schedule_fingerprint", descriptor)
        self.assertNotIn("quantum_speedup", descriptor)


if __name__ == "__main__":
    unittest.main()
