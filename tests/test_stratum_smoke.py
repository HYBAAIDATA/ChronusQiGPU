"""CI-discovered regressions for scripts/smoke Stratum V1 smoke."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

SMOKE_DIR = Path(__file__).resolve().parents[1] / "scripts" / "smoke"
sys.path.insert(0, str(SMOKE_DIR))

from fake_pool import (  # noqa: E402
    DIFF1,
    DIFFICULTY,
    JOB_ID,
    NBITS,
    NTIME,
    TARGET,
    accept_share,
    header,
    network_target,
)
from stratum_smoke import (  # noqa: E402
    Session,
    Transcript,
    meets,
    parse_host,
    target_from_difficulty,
)


class EndianSmokeTests(unittest.TestCase):
    def test_default_pool_is_bitcoin_difficulty_1(self) -> None:
        self.assertEqual(DIFFICULTY, 1)
        self.assertEqual(TARGET, DIFF1)
        self.assertEqual(target_from_difficulty(DIFFICULTY), TARGET)

    def test_network_target_harder_than_share_target(self) -> None:
        self.assertLess(network_target(NBITS), TARGET)

    def test_canonical_comparison_is_little_endian(self) -> None:
        digest = bytes([0xFF] * 31 + [0x00])
        threshold = 1 << 255
        le = int.from_bytes(digest, "little") <= threshold
        be = int.from_bytes(digest, "big") <= threshold
        self.assertNotEqual(le, be)
        self.assertEqual(meets(digest, threshold), le)
        self.assertTrue(le)
        self.assertFalse(be)

    def test_accept_share_uses_le_and_rejects_unknown_job(self) -> None:
        soft = 1 << 248
        extranonce1 = "deadbeef"
        hit = None
        for nonce in range(20_000):
            params = ["smoke", JOB_ID, "00000000", NTIME, f"{nonce:08x}"]
            digest = hashlib.sha256(hashlib.sha256(header(extranonce1, params)).digest()).digest()
            if meets(digest, soft) and not (int.from_bytes(digest, "big") <= soft):
                hit = (params, digest)
                break
        self.assertIsNotNone(hit, "need an LE-only hit under the soft target")
        params, digest = hit
        ok, error = accept_share(extranonce1, params, soft)
        self.assertTrue(ok)
        self.assertIsNone(error)
        self.assertFalse(int.from_bytes(digest, "big") <= soft)

        bad_job = list(params)
        bad_job[1] = "not-the-job"
        ok, error = accept_share(extranonce1, bad_job, soft)
        self.assertFalse(ok)
        self.assertEqual(error[0], 21)

    def test_parse_host_preserves_tls_and_rejects_unknown(self) -> None:
        host, port, tls = parse_host("stratum+ssl://pool.example:5555", 3333)
        self.assertEqual((host, port, tls), ("pool.example", 5555, True))
        host, port, tls = parse_host("stratum+tcp://pool.example", 3333)
        self.assertEqual((host, port, tls), ("pool.example", 3333, False))
        with self.assertRaises(ValueError):
            parse_host("http://pool.example:80", 3333)

    def test_require_accept_without_submit_is_config_error(self) -> None:
        from stratum_smoke import main

        with patch("sys.argv", ["stratum_smoke.py", "--require-accept"]):
            with patch("sys.stderr", new=StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    main()
        self.assertEqual(raised.exception.code, 4)


class NotifyRetentionTests(unittest.TestCase):
    def test_call_retains_notify_for_wait_for(self) -> None:
        async def scenario() -> None:
            reader = asyncio.StreamReader()

            class W:
                def write(self, _data):
                    pass

                async def drain(self):
                    pass

                def close(self):
                    pass

                async def wait_closed(self):
                    pass

            session = Session(reader, W(), Transcript("fake"))
            try:
                call_task = asyncio.create_task(
                    session.call("mining.authorize", ["u", "p"], timeout=2.0)
                )
                await asyncio.sleep(0)
                # Notify arrives before the matching RPC reply.
                reader.feed_data(
                    (
                        json.dumps(
                            {
                                "id": None,
                                "method": "mining.notify",
                                "params": ["early-job"] + ["00"] * 7 + [True],
                            }
                        )
                        + "\n"
                    ).encode()
                )
                reader.feed_data(
                    (json.dumps({"id": 1, "result": True, "error": None}) + "\n").encode()
                )
                reply = await call_task
                self.assertTrue(reply.get("result") is True)
                notify = await session.wait_for("mining.notify", timeout=1.0)
                self.assertEqual(notify["params"][0], "early-job")
            finally:
                session.alive.clear()
                session.pump.cancel()
                try:
                    await session.pump
                except (asyncio.CancelledError, Exception):
                    pass

        asyncio.run(scenario())

    def test_search_stops_when_alive_clears(self) -> None:
        from stratum_smoke import search_share

        async def scenario() -> None:
            alive = asyncio.Event()
            alive.set()
            job = {
                "job_id": "j",
                "prevhash": "00" * 32,
                "coinb1": "00",
                "coinb2": "00",
                "merkle_branch": [],
                "version": "20000000",
                "nbits": "1c00ffff",
                "ntime": "67000000",
            }

            async def drop():
                await asyncio.sleep(0.05)
                alive.clear()

            stopper = asyncio.create_task(drop())
            with self.assertRaises(ConnectionError):
                await search_share(
                    "python",
                    job,
                    "deadbeef",
                    "00000000",
                    DIFF1,
                    deadline=time_deadline(),
                    alive=alive,
                )
            await stopper

        def time_deadline() -> float:
            import time

            return time.monotonic() + 30.0

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
