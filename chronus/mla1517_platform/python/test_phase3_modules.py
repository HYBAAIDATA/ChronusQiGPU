"""Behavioral tests for Phase 3 hardware, TOE, seals, and persistence."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from chronus.mla1517.mining.cassini_seal import InvalidCassiniSeal, compute_seal, verify_seal
from chronus.mla1517.mining.opencl_driver import OpenCLDriver, OpenCLExecutionResult
from chronus.mla1517.mining.persistence import (
    BackpressureRequired,
    BoundedPersistenceQueue,
    CorruptRecord,
    PrimeDBPersistence,
    TelemetryCounters,
)
from chronus.mla1517.mining.toe_context import (
    ObservedTransition,
    TOEContextBuilder,
    TOEContextUnavailable,
)


class Phase3Tests(unittest.TestCase):
    def test_cassini_seal_rejects_state_or_coordinate_changes(self) -> None:
        state = bytes(range(64))
        seal = compute_seal(state=state, sequence=3, watermark=9, lane_id=2)
        verify_seal(state=state, sequence=3, watermark=9, lane_id=2, seal=seal)
        with self.assertRaises(InvalidCassiniSeal):
            verify_seal(state=state[:-1] + b"x", sequence=3, watermark=9, lane_id=2, seal=seal)

    def test_toe_context_requires_observed_inputs(self) -> None:
        transition = ObservedTransition({"state": "before"}, {"state": "after"}, 1, "hardware_ack")
        context = (
            TOEContextBuilder()
            .with_job({"job_id": "live-job", "notify": ["nine-fields"]})
            .with_hardware_state(bytes(64))
            .with_coordinates(lane_id=1, node_id=2, sequence=3, watermark=4)
            .with_telemetry({"hashes": 10, "elapsed_seconds": 1.0})
            .add_transition(transition)
            .build()
        )
        self.assertEqual(context.observation()["sha256d_authority"], "external_consensus_validator")
        with self.assertRaises(TOEContextUnavailable):
            TOEContextBuilder().with_job({"job_id": "synthetic"}).build()

    def test_persistence_round_trip_cursor_and_writer_counters(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            counters = TelemetryCounters()
            db = PrimeDBPersistence(Path(directory) / "prime.db", telemetry=counters)
            record = db.append(state=bytes(64), sequence=0, watermark=7, lane_id=3)
            self.assertEqual(db.get(record.record_id), record)
            self.assertEqual(db.recover_cursor(), 1)
            self.assertEqual(counters.snapshot(), {"records_written": 1, "records_read": 1})
            db.close()

    def test_corrupt_record_is_quarantined_not_silently_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db = PrimeDBPersistence(Path(directory) / "prime.db")
            record = db.append(state=bytes(64), sequence=0, watermark=0, lane_id=0)
            db.db.execute("UPDATE records SET state=? WHERE record_id=?", (b"bad", record.record_id))
            db.db.commit()
            with self.assertRaises(CorruptRecord):
                db.get(record.record_id)
            count = db.db.execute("SELECT COUNT(*) FROM quarantine").fetchone()[0]
            self.assertEqual(count, 1)
            db.close()

    def test_ring_overflow_requires_backpressure(self) -> None:
        queue = BoundedPersistenceQueue(1)
        queue.submit("first")
        with self.assertRaises(BackpressureRequired):
            queue.submit("second")

    def test_opencl_unavailable_never_becomes_cpu_success(self) -> None:
        result = OpenCLExecutionResult.unavailable()
        self.assertEqual(result.truth_class, "unavailable")
        self.assertFalse(result.hardware_execution)
        driver = OpenCLDriver()
        if not driver.available:
            with self.assertRaises(Exception):
                driver.execute_kernel(
                    source="__kernel void noop() {}",
                    kernel_name="noop",
                    global_size=(1,),
                    hashes_computed=1,
                )


if __name__ == "__main__":
    unittest.main()
