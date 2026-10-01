"""Behavioral tests for the Phase 4 coordinator assembly."""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from coordinator import CandidateRequest, CanonicalMiningCoordinator, CoordinatorUnavailable
from chronus.mla1517.mining.persistence import PrimeDBPersistence
from chronus.mla1517.mining.session import MiningSession


class FakeAdapter:
    def validate_candidate(self, **kwargs):
        return SimpleNamespace(digest=b"digest-proof")


class FakePool:
    submit_enabled = False

    def __init__(self):
        self.session = MiningSession()
        self.client = SimpleNamespace(
            proof_adapter=FakeAdapter(),
            latest_job=lambda: SimpleNamespace(job_id="live-job", params=("notify",)),
        )
        self.calls = []

    async def submit_candidate(self, **kwargs):
        self.calls.append(kwargs)
        return False


class Phase4AssemblyTests(unittest.TestCase):
    def test_observed_candidate_is_validated_persisted_and_not_falsely_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            persistence = PrimeDBPersistence(Path(directory) / "prime.db")
            pool = FakePool()
            coordinator = CanonicalMiningCoordinator(pool, persistence)
            request = CandidateRequest(
                job_id="live-job",
                extranonce2="00000001",
                ntime="65abcdef",
                nonce=7,
                hardware_state=bytes(64),
                lane_id=1,
                node_id=2,
                sequence=0,
                watermark=0,
                telemetry={"hashes": 1, "elapsed_seconds": 1.0},
            )
            result = asyncio.run(coordinator.submit_observed_candidate(request))
            self.assertTrue(result.proof_checked)
            self.assertIsNone(result.pool_accepted)
            self.assertEqual(len(pool.calls), 1)
            self.assertEqual(persistence.recover_cursor(), 1)
            persistence.close()

    def test_missing_live_client_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            persistence = PrimeDBPersistence(Path(directory) / "prime.db")
            with self.assertRaises(CoordinatorUnavailable):
                asyncio.run(
                    CanonicalMiningCoordinator(
                        SimpleNamespace(client=None, session=MiningSession()), persistence
                    ).submit_observed_candidate(
                        CandidateRequest("job", "00", "00", 0, bytes(64), 0, 0, 0, 0, {"x": 1})
                    )
                )
            persistence.close()


if __name__ == "__main__":
    unittest.main()
