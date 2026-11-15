import asyncio
import unittest
from chronus.stratum.gateway import StratumGateway


class TestStratumReplay(unittest.TestCase):
    def test_replayed_notify_and_difficulty_session(self):
        recorded_frames = [
            {"method": "mining.set_difficulty", "params": [131072]},
            {"method": "mining.set_extranonce", "params": ["a45b7889", 4]},
            {
                "method": "mining.notify",
                "params": [
                    "job_viabtc_9901",
                    "0000000000000000000000000000000000000000000000000000000000000001",
                    "01000000010000000000000000000000000000000000000000000000000000000000000000ffffffff0403759905",
                    "00000000",
                    [],
                    "20000000",
                    "1d00ffff",
                    "60000000",
                    True
                ]
            }
        ]

        gw = StratumGateway("localhost", 3333, "worker_01")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        for frame in recorded_frames:
            loop.run_until_complete(gw.handle_server_push(frame))

        self.assertEqual(gw.current_difficulty, 131072)
        self.assertEqual(gw.extranonce1_hex, "a45b7889")
        self.assertEqual(gw.extranonce2_size, 4)
        self.assertIn("job_viabtc_9901", gw.jobs)


if __name__ == "__main__":
    unittest.main()
