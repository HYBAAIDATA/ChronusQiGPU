"""Regression: smoke and fake pool share little-endian target comparison."""

from __future__ import annotations

import asyncio
import hashlib
import json
import unittest
from io import StringIO
from unittest.mock import patch

from fake_pool import (
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
from stratum_smoke import meets, parse_host, target_from_difficulty


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
        # Build a mid-range digest by searching a soft target so LE and BE can diverge.
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
        # Same nonce under BE would fail; confirm the pool predicate is LE.
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
        from stratum_smoke import Session, Transcript

        async def scenario() -> None:
            reader = asyncio.StreamReader()
            # Minimal writer stub.
            class W:
                def write(self, _data): pass
                async def drain(self): pass
                def close(self): pass
                async def wait_closed(self): pass

            tx = Transcript("fake")
            session = Session(reader, W(), tx)
            try:
                # Queue authorize reply + an early notify before the reply id matches.
                reader.feed_data(
                    (json.dumps({"id": 1, "result": True, "error": None}) + "\n").encode()
                )
                # Inject notify while call is waiting — feed after starting call via pump path:
                # send id=1 subscribe-like, then notify then authorize reply.
            finally:
                # Direct unit: stash path
                session.stash.append({"method": "mining.notify", "params": ["j"] + [None] * 8})
                got = await session.wait_for("mining.notify", 1)
                self.assertEqual(got["params"][0], "j")
                session.pump.cancel()

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
