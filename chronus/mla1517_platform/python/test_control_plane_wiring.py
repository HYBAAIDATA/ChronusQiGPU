from __future__ import annotations

import unittest
from types import SimpleNamespace

from coordinator import CanonicalMiningCoordinator, CoordinatorUnavailable
from chronus.mla1517.mining.persistence import PrimeDBPersistence
from chronus.mla1517.mining.session import MiningSession
from chronus.mla1517.mining.toe_context import TOEContextBuilder


class RecordingSink:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def _record(self, name: str, **kwargs) -> None:
        self.calls.append((name, kwargs))

    def flush_lane(self, **kwargs):
        self._record("flush_lane", **kwargs)

    def resize_workgroup(self, **kwargs):
        self._record("resize_workgroup", **kwargs)

    def prune_window(self, **kwargs):
        self._record("prune_window", **kwargs)

    def sever_lane(self, **kwargs):
        self._record("sever_lane", **kwargs)

    def restart_lane(self, **kwargs):
        self._record("restart_lane", **kwargs)

    def apply_backpressure(self, **kwargs):
        self._record("apply_backpressure", **kwargs)

    def quarantine_record(self, **kwargs):
        self._record("quarantine_record", **kwargs)

    def flush_persistence_ring(self, **kwargs):
        self._record("flush_persistence_ring", **kwargs)

    def reset_cursor(self, **kwargs):
        self._record("reset_cursor", **kwargs)


def context(job_id: str = "job-1"):
    return (
        TOEContextBuilder()
        .with_job({"job_id": job_id, "params": ("notify",)})
        .with_hardware_state(b"h" * 64)
        .with_coordinates(lane_id=1, node_id=2, sequence=1, watermark=1)
        .with_telemetry({"source": "observed"})
        .build()
    )


def snapshot(**updates):
    result = {
        "kernel_latency_ms": 10.0,
        "kernel_latency_bound_ms": 100.0,
        "temperature_c": 55.0,
        "thermal_limit_c": 85.0,
        "stratum_state": "READY",
        "hardware_status": "READY",
        "new_job_observed": False,
    }
    result.update(updates)
    return result


class ControlPlaneWiringTests(unittest.TestCase):
    def make_coordinator(self, sink):
        return CanonicalMiningCoordinator(
            SimpleNamespace(session=MiningSession()),
            PrimeDBPersistence(":memory:"),
            control_sink=sink,
        )

    def test_thermal_spike_routes_resize_to_sink(self):
        sink = RecordingSink()
        coordinator = self.make_coordinator(sink)
        result = coordinator.route_observation(
            context=context(),
            telemetry=snapshot(temperature_c=90.0),
            observed_at_ns=100,
        )
        self.assertIn("RESIZE_WORKGROUP", result.dispatched_commands)
        self.assertEqual([name for name, _ in sink.calls], ["resize_workgroup"])
        self.assertEqual(sink.calls[0][1]["parameters"]["direction"], "down")

    def test_new_job_severs_before_flush_and_deduplicates_flush(self):
        sink = RecordingSink()
        coordinator = self.make_coordinator(sink)
        result = coordinator.route_observation(
            context=context("job-2"),
            telemetry=snapshot(new_job_observed=True, stratum_state="NEW_JOB"),
            observed_at_ns=101,
            current_job_id="job-2",
        )
        self.assertEqual(result.dispatched_commands[:2], ("SEVER_LANE", "FLUSH_LANE"))
        self.assertEqual([name for name, _ in sink.calls], ["sever_lane", "flush_lane"])

    def test_distinct_flush_intents_are_not_dropped(self):
        sink = RecordingSink()
        coordinator = self.make_coordinator(sink)
        result = coordinator.route_observation(
            context=context(),
            telemetry=snapshot(kernel_latency_ms=250.0),
            observed_at_ns=103,
        )
        flushes = [kwargs["parameters"] for name, kwargs in sink.calls if name == "flush_lane"]
        self.assertEqual(
            flushes,
            [
                {"preserve_proof_state": True},
                {"action": "restart_lane_after_ack"},
            ],
        )
        self.assertEqual(result.dispatched_commands.count("FLUSH_LANE"), 2)

    def test_missing_sink_fails_closed_for_non_hold_signal(self):
        coordinator = CanonicalMiningCoordinator(
            SimpleNamespace(session=MiningSession()), PrimeDBPersistence(":memory:")
        )
        with self.assertRaises(CoordinatorUnavailable):
            coordinator.route_observation(
                context=context(),
                telemetry=snapshot(temperature_c=90.0),
                observed_at_ns=102,
            )


if __name__ == "__main__":
    unittest.main()
