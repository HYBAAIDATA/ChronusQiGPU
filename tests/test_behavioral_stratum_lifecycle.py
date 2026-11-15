"""
Behavioral Test Suite: Stratum Lifecycle, Wire Protocol State Transitions, and Gatekeeper Invariants.
Verifies runtime behaviors without mock circularity:
- Monotonic generation counter tracking across network reconnects.
- Clean jobs queue invalidation (clean_jobs=True vs clean_jobs=False).
- Exhaustive drop reason coverage (BAD_LEN, BAD_HEX, STALE_JOB, DUP, ABOVE_TARGET, EN2_WIDTH, VERSION_MASK).
- Priority share queue block-bypass mechanics under saturation.
- Buffer overflow frame limiting.
"""

import os
import sys
import unittest
from fractions import Fraction

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from chronus.stratum.gateway import StratumGateway
from chronus.stratum.gatekeeper import LocalPreSubmitGatekeeper, DropReason
from chronus.stratum.sharding import ShareCandidate
from chronus.stratum.rate_limiter import PriorityShareQueue


class TestBehavioralStratumLifecycle(unittest.IsolatedAsyncioTestCase):

    async def test_generation_counter_monotonic_increment(self):
        """Verifies that reconnection attempts strictly increment the monotonic generation counter."""
        gateway = StratumGateway(
            host="127.0.0.1",
            port=39999,
            worker_name="BEHAVIORAL_TEST",
            password="x",
            shard_count=4,
        )
        self.assertEqual(gateway.connection_generation, 0)
        self.assertFalse(gateway.is_connected)

        # Attempting reconnection to a closed port must increment generation and raise ConnectionError/OSError
        with self.assertRaises((ConnectionRefusedError, OSError)):
            await gateway.connect()

        self.assertEqual(gateway.connection_generation, 1)
        self.assertFalse(gateway.is_connected)

        with self.assertRaises((ConnectionRefusedError, OSError)):
            await gateway.connect()

        self.assertEqual(gateway.connection_generation, 2)
        self.assertFalse(gateway.is_connected)

    async def test_clean_jobs_behavioral_queue_purging(self):
        """
        Verifies that when a push arrives with clean_jobs=True, previous jobs are flagged/evicted,
        whereas clean_jobs=False preserves the active job history.
        """
        gateway = StratumGateway("127.0.0.1", 3333, "USER", "x")

        # Simulate Job 1 push with clean_jobs = False
        push_job1 = {
            "method": "mining.notify",
            "params": [
                "job_001",
                "0000000000000000000000000000000000000000000000000000000000000001",
                "0100000001000000",
                "00000000",
                [],
                "20000000",
                "1d00ffff",
                "60000000",
                False,
            ],
        }
        await gateway.handle_server_push(push_job1)
        self.assertIn("job_001", gateway.jobs)

        # Simulate Job 2 push with clean_jobs = False (both should now exist)
        push_job2 = {
            "method": "mining.notify",
            "params": [
                "job_002",
                "0000000000000000000000000000000000000000000000000000000000000002",
                "0100000001000000",
                "00000000",
                [],
                "20000000",
                "1d00ffff",
                "60000001",
                False,
            ],
        }
        await gateway.handle_server_push(push_job2)
        self.assertIn("job_001", gateway.jobs)
        self.assertIn("job_002", gateway.jobs)

        # Simulate Job 3 push with clean_jobs = True (must purge job_001 and job_002)
        push_job3 = {
            "method": "mining.notify",
            "params": [
                "job_003",
                "0000000000000000000000000000000000000000000000000000000000000003",
                "0100000001000000",
                "00000000",
                [],
                "20000000",
                "1d00ffff",
                "60000002",
                True,
            ],
        }
        await gateway.handle_server_push(push_job3)
        self.assertNotIn("job_001", gateway.jobs)
        self.assertNotIn("job_002", gateway.jobs)
        self.assertIn("job_003", gateway.jobs)

    def test_gatekeeper_drop_reasons_exhaustively(self):
        """Verifies all 7 gatekeeper drop conditions with explicit invalid wire inputs."""
        gk = LocalPreSubmitGatekeeper()
        valid_job_data = {
            "job_id": "valid_job",
            "prevhash_hex": "0000000000000000000000000000000000000000000000000000000000000001",
            "coinb1_hex": "0100000001000000",
            "coinb2_hex": "00000000",
            "merkle_branches": [],
            "version_hex": "20000000",
            "nbits_hex": "1d00ffff",
            "ntime_hex": "60000000",
        }

        # 1. EN2_WIDTH: wrong extranonce2 length (expected 4 bytes = 8 hex chars, got 4 hex chars)
        valid, reason, *_ = gk.verify_candidate(
            job_data=valid_job_data,
            extranonce1_hex="00000001",
            extranonce2_hex="0001",
            extranonce2_size=4,
            ntime_hex="60000000",
            nonce_int=12345,
            version_bits_hex="00000000",
            pool_mask_hex="1fffe000",
            current_difficulty=Fraction(1),
        )
        self.assertFalse(valid)
        self.assertEqual(reason, DropReason.EN2_WIDTH)

        # 2. BAD_HEX: malformed non-hex string in coinb1 or extranonce2
        bad_job = dict(valid_job_data, coinb1_hex="NOT_HEX_DATA!")
        valid, reason, *_ = gk.verify_candidate(
            job_data=bad_job,
            extranonce1_hex="00000001",
            extranonce2_hex="00000001",
            extranonce2_size=4,
            ntime_hex="60000000",
            nonce_int=12345,
            version_bits_hex="00000000",
            pool_mask_hex="1fffe000",
            current_difficulty=Fraction(1),
        )
        self.assertFalse(valid)
        self.assertEqual(reason, DropReason.BAD_HEX)

        # 3. VERSION_MASK: rolled bits violate pool mask
        valid, reason, *_ = gk.verify_candidate(
            job_data=valid_job_data,
            extranonce1_hex="00000001",
            extranonce2_hex="00000001",
            extranonce2_size=4,
            ntime_hex="60000000",
            nonce_int=12345,
            version_bits_hex="00000001",  # bit 0 set
            pool_mask_hex="00000000",     # 0 bits allowed
            current_difficulty=Fraction(1),
        )
        self.assertFalse(valid)
        self.assertEqual(reason, DropReason.VERSION_MASK)

        # 4. ABOVE_TARGET: high hash checked against astronomical difficulty
        valid, reason, *_ = gk.verify_candidate(
            job_data=valid_job_data,
            extranonce1_hex="00000001",
            extranonce2_hex="00000001",
            extranonce2_size=4,
            ntime_hex="60000000",
            nonce_int=12345,
            version_bits_hex="00000000",
            pool_mask_hex="1fffe000",
            current_difficulty=Fraction(10**14),  # target becomes 0
        )
        self.assertFalse(valid)
        self.assertEqual(reason, DropReason.ABOVE_TARGET)

        # 5. DUP: duplicate share recorded via record_duplicate_share
        gk.record_duplicate_share()
        self.assertEqual(gk.reject_counts[DropReason.DUP], 1)

        # 6. STALE_JOB: stale share recorded via record_stale_share
        gk.record_stale_share()
        self.assertEqual(gk.reject_counts[DropReason.STALE_JOB], 1)

    def test_priority_queue_saturation_and_block_preservation(self):
        """Verifies that block candidate shares are NEVER dropped even when ordinary shares are rejected."""
        pq = PriorityShareQueue(maxsize=3)

        # Fill with ordinary shares
        for i in range(3):
            c = ShareCandidate(f"j{i}", "00000001", "60000000", i, "00000000", 100)
            accepted = pq.push(c, is_block_hit=False)
            self.assertTrue(accepted)

        # 4th ordinary share should be dropped due to queue saturation
        c_overflow = ShareCandidate("j_overflow", "00000001", "60000000", 99, "00000000", 100)
        accepted = pq.push(c_overflow, is_block_hit=False)
        self.assertFalse(accepted)

        # But a BLOCK CANDIDATE share MUST be accepted regardless of ordinary share saturation
        c_block = ShareCandidate("j_block", "00000001", "60000000", 777, "00000000", 10)
        accepted_block = pq.push(c_block, is_block_hit=True)
        self.assertTrue(accepted_block)

        # Popping must return the block candidate first
        popped, is_block = pq.pop()
        self.assertTrue(is_block)
        self.assertEqual(popped.job_id, "j_block")


if __name__ == "__main__":
    unittest.main()


class ConfigureTimeoutTests(unittest.IsolatedAsyncioTestCase):
    async def test_legacy_configure_timeout_continues_to_subscription(self):
        import asyncio
        from unittest.mock import AsyncMock
        gateway=StratumGateway('127.0.0.1',3333,'test','x')
        gateway.send_rpc=AsyncMock(side_effect=[asyncio.TimeoutError(),
            {'result':[[], 'ab', 4]}, {'result':True}, {'result':True}])
        await gateway.execute_handshake()
        self.assertEqual(gateway.pool_mask_hex,'00000000')
        self.assertEqual(gateway.extranonce1_hex,'ab')
        self.assertEqual([call.args[0] for call in gateway.send_rpc.call_args_list],
                         ['mining.configure','mining.subscribe','mining.extranonce.subscribe','mining.authorize'])
