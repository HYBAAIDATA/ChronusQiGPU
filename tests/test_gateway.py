import asyncio
import json
import unittest
import os
from unittest.mock import patch
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

        # 3. mining.set_version_mask (>=16 bits accepted; <16 bits refused per BIP310)
        loop.run_until_complete(gw.handle_server_push({"method": "mining.set_version_mask", "params": ["1fffe000"]}))
        self.assertEqual(gw.pool_mask_hex, "1fffe000")
        loop.run_until_complete(gw.handle_server_push({"method": "mining.set_version_mask", "params": ["0000e000"]}))
        self.assertEqual(gw.pool_mask_hex, "00000000")

        loop.close()

    def test_out_of_order_pushes_handled(self):
        """Validates that out-of-order pushes (notify, diff, extranonce, version mask) are handled correctly."""
        gw = StratumGateway(host="localhost", port=3333, worker_name="test_worker")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Push 1: set_version_mask arrives first
        loop.run_until_complete(gw.handle_server_push({"method": "mining.set_version_mask", "params": ["1fffe000"]}))
        self.assertEqual(gw.pool_mask_hex, "1fffe000")

        # Push 2: set_difficulty arrives second
        loop.run_until_complete(gw.handle_server_push({"method": "mining.set_difficulty", "params": [4096]}))
        self.assertEqual(gw.current_difficulty, Fraction(4096))

        # Push 3: set_extranonce arrives third
        loop.run_until_complete(gw.handle_server_push({"method": "mining.set_extranonce", "params": ["abcdef12", 4]}))
        self.assertEqual(gw.extranonce1_hex, "abcdef12")
        self.assertEqual(gw.extranonce2_size, 4)

        # Push 4: mining.notify arrives fourth
        notify_params = [
            "job_ooo",
            "11" * 32,
            "01000000",
            "00000000",
            ["22" * 32],
            "20000000",
            "1d00ffff",
            "60000000",
            True
        ]
        loop.run_until_complete(gw.handle_server_push({"method": "mining.notify", "params": notify_params}))
        self.assertIn("job_ooo", gw.jobs)
        self.assertEqual(gw.jobs["job_ooo"]["prevhash_hex"], "11" * 32)

        loop.close()

    def test_reconnect_resets_all_state(self):
        """[MOCK] Validates that reconnect resets jobs, difficulty, extranonce, and version mask."""
        async def run_mock_test():
            # 1. Start local mock Stratum server
            notify_frame1 = (
                '{"id": null, "method": "mining.notify", "params": ["m_job1", "' + ("00" * 32) +
                '", "01", "02", [], "20000000", "1d00ffff", "60000000", true]}\n'
            )
            notify_frame2 = (
                '{"id": null, "method": "mining.notify", "params": ["m_job2", "' + ("11" * 32) +
                '", "01", "02", [], "20000000", "1d00ffff", "60000000", false]}\n'
            )

            async def handle_client(reader, writer):
                try:
                    writer.write(notify_frame1.encode("utf-8"))
                    writer.write(notify_frame2.encode("utf-8"))
                    await writer.drain()
                    await asyncio.sleep(0.05)
                finally:
                    writer.close()
                    try:
                        await writer.wait_closed()
                    except Exception:
                        pass

            server = await asyncio.start_server(handle_client, "127.0.0.1", 0)
            port = server.sockets[0].getsockname()[1]

            gw = StratumGateway(host="127.0.0.1", port=port, worker_name="worker_mock")
            try:
                # First connect
                with patch.dict(os.environ, {"CHRONUS_ALLOWED_POOL_ENDPOINTS": json.dumps([f"stratum+tcp://127.0.0.1:{port}"])}):
                    await gw.connect()
                self.assertEqual(gw.connection_generation, 1)

                # Read the two notify frames
                msg1 = await gw.read_message()
                self.assertIsNotNone(msg1)
                await gw.handle_server_push(msg1)

                msg2 = await gw.read_message()
                self.assertIsNotNone(msg2)
                await gw.handle_server_push(msg2)

                self.assertEqual(len(gw.jobs), 2)
                self.assertIn("m_job1", gw.jobs)
                self.assertIn("m_job2", gw.jobs)

                # Mutate session state to non-default values
                gw.current_difficulty = Fraction(65536)
                gw.extranonce1_hex = "cafebeef"
                gw.extranonce2_size = 8
                gw.pool_mask_hex = "1fffe000"
                gw.dedup_ledger.record("m_job1", "0", "0", "0", 1)

                # Verify state before reconnect
                self.assertEqual(gw.current_difficulty, Fraction(65536))
                self.assertEqual(gw.extranonce1_hex, "cafebeef")
                self.assertEqual(gw.extranonce2_size, 8)
                self.assertEqual(gw.pool_mask_hex, "1fffe000")
                self.assertEqual(len(gw.jobs), 2)

                # Trigger Reconnect
                with patch.dict(os.environ, {"CHRONUS_ALLOWED_POOL_ENDPOINTS": json.dumps([f"stratum+tcp://127.0.0.1:{port}"])}):
                    await gw.connect()

                # Verify generation incremented
                self.assertEqual(gw.connection_generation, 2)

                # Verify ALL state fields are strictly reset
                self.assertEqual(len(gw.jobs), 0, "Jobs must be reset on reconnect")
                self.assertEqual(len(gw.job_history), 0, "Job history must be reset on reconnect")
                self.assertEqual(gw.current_difficulty, Fraction(1), "Difficulty must be reset to 1 on reconnect")
                self.assertEqual(gw.extranonce1_hex, "", "ExtraNonce1 must be reset to empty on reconnect")
                self.assertEqual(gw.extranonce2_size, 4, "ExtraNonce2 size must be reset to default 4 on reconnect")
                self.assertEqual(gw.pool_mask_hex, "00000000", "Pool mask must be reset to 00000000 on reconnect")
                self.assertFalse(gw.dedup_ledger.is_duplicate("m_job1", "0", "0", "0", 1), "Dedup ledger must be cleared")

            finally:
                await gw.close()
                server.close()
                await server.wait_closed()

        asyncio.run(run_mock_test())

    def test_malformed_json_dropped_not_disconnect(self):
        """Validates that malformed JSON lines are dropped without disconnecting the client."""
        async def run_malformed_test():
            async def handle_client(reader, writer):
                try:
                    req_line = await reader.readuntil(b"\n")
                    req = json.loads(req_line.decode("utf-8"))
                    req_id = req["id"]

                    # Send a malformed JSON line
                    writer.write(b'{"invalid_json": true, bad_field}\n')
                    await writer.drain()

                    # Send valid response matching request id
                    resp = json.dumps({"id": req_id, "result": "ok", "error": None}) + "\n"
                    writer.write(resp.encode("utf-8"))
                    await writer.drain()
                finally:
                    writer.close()
                    try:
                        await writer.wait_closed()
                    except Exception:
                        pass

            server = await asyncio.start_server(handle_client, "127.0.0.1", 0)
            port = server.sockets[0].getsockname()[1]
            gw = StratumGateway(host="127.0.0.1", port=port, worker_name="worker_mock")
            try:
                with patch.dict(os.environ, {"CHRONUS_ALLOWED_POOL_ENDPOINTS": json.dumps([f"stratum+tcp://127.0.0.1:{port}"])}):
                    await gw.connect()
                # send_rpc must not crash on malformed line; it must drop it and return valid response
                res = await gw.send_rpc("mining.test", [])
                self.assertEqual(res.get("result"), "ok")
            finally:
                await gw.close()
                server.close()
                await server.wait_closed()

        asyncio.run(run_malformed_test())


if __name__ == "__main__":
    unittest.main()
