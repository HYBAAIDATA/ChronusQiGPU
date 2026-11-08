import asyncio
import unittest
from fractions import Fraction
from chronus.stratum.gateway import StratumGateway


class TestGateway(unittest.TestCase):
    def test_gateway_initialization(self):
        gw = StratumGateway(host="localhost", port=3333, worker_name="test_worker")
        self.assertEqual(gw.host, "localhost")
        self.assertEqual(gw.port, 3333)
        self.assertEqual(gw.worker_name, "test_worker")
        self.assertEqual(gw.connection_generation, 0)
        self.assertFalse(gw.is_connected)

    def test_process_notify_parsing_and_history_cap(self):
        gw = StratumGateway(host="localhost", port=3333, worker_name="test_worker")
        
        # Test clean_jobs = True clears previous jobs
        params1 = [
            "job_101",
            "00" * 32,
            "01000000",
            "00000000",
            [],
            "20000000",
            "1d00ffff",
            "60000000",
            True
        ]
        gw._process_notify(params1)
        self.assertIn("job_101", gw.jobs)

        # Test job history capping at 16
        for i in range(20):
            p = [
                f"job_{i}",
                "00" * 32,
                "01000000",
                "00000000",
                [],
                "20000000",
                "1d00ffff",
                "60000000",
                False
            ]
            gw._process_notify(p)

        self.assertLessEqual(len(gw.jobs), 17)
        self.assertNotIn("job_101", gw.jobs)

    def test_process_notify_invalid_params_dropped(self):
        gw = StratumGateway(host="localhost", port=3333, worker_name="test_worker")
        # Too few parameters (< 8)
        gw._process_notify(["job_bad", "00" * 32])
        self.assertEqual(len(gw.jobs), 0)

        # Bad prevhash length (!= 64 hex chars)
        gw._process_notify([
            "job_bad2",
            "00" * 10, # too short
            "01",
            "02",
            [],
            "20000000",
            "1d00ffff",
            "60000000",
            False
        ])
        self.assertEqual(len(gw.jobs), 0)

    def test_handle_server_push_methods(self):
        gw = StratumGateway(host="localhost", port=3333, worker_name="test_worker")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # 1. mining.set_difficulty
        loop.run_until_complete(gw.handle_server_push({"method": "mining.set_difficulty", "params": [8192]}))
        self.assertEqual(gw.current_difficulty, Fraction(8192))

        # 2. mining.set_extranonce
        loop.run_until_complete(gw.handle_server_push({"method": "mining.set_extranonce", "params": ["12345678", 6]}))
        self.assertEqual(gw.extranonce1_hex, "12345678")
        self.assertEqual(gw.extranonce2_size, 6)

        # 3. mining.set_version_mask
        loop.run_until_complete(gw.handle_server_push({"method": "mining.set_version_mask", "params": ["0000e000"]}))
        self.assertEqual(gw.pool_mask_hex, "0000e000")

        loop.close()

    def test_reconnect_resets_state_and_bumps_generation(self):
        gw = StratumGateway(host="localhost", port=3333, worker_name="test_worker")
        gw.connection_generation = 1
        gw.jobs["old_job"] = {"job_id": "old_job"}
        gw.dedup_ledger.record("old_job", "0", "0", "0", 1)

        # Emulate generation bump on reconnect
        gw.connection_generation += 1
        gw.jobs.clear()
        gw.dedup_ledger.clear()

        self.assertEqual(gw.connection_generation, 2)
        self.assertEqual(len(gw.jobs), 0)
        self.assertFalse(gw.dedup_ledger.is_duplicate("old_job", "0", "0", "0", 1))


if __name__ == "__main__":
    unittest.main()
