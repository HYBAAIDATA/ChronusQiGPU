"""CI-discovered regressions for scripts/smoke Stratum V1 smoke."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
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
    WorkChanged,
    _peer_is_loopback,
    meets,
    parse_host,
    target_from_difficulty,
    target_from_nbits,
    validate_job_params,
)


class EndianSmokeTests(unittest.TestCase):
    def test_default_pool_is_offline_micro_difficulty(self) -> None:
        from fractions import Fraction

        self.assertEqual(DIFFICULTY, 1 / 2**24)
        self.assertEqual(TARGET, int(Fraction(DIFF1) / Fraction(DIFFICULTY)))
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

        extra = list(params) + ["00000000"]
        ok, error = accept_share(extranonce1, extra, soft)
        self.assertFalse(ok)
        self.assertEqual(error[0], 20)

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

    def test_cleartext_non_loopback_peer_requires_flag(self) -> None:
        from argparse import Namespace
        from stratum_smoke import Transcript, smoke

        class FakeWriter:
            def get_extra_info(self, name):
                return ("203.0.113.10", 3333) if name == "peername" else None

            def close(self):
                pass

            async def wait_closed(self):
                pass

        async def fake_open_connection(*_args, **_kwargs):
            return asyncio.StreamReader(), FakeWriter()

        async def run() -> int:
            args = Namespace(
                host_var="MINING_BRAIINS_HOST",
                user_var="MINING_BRAIINS_USER",
                password_var="MINING_BRAIINS_PASSWORD",
                port=3333,
                timeout=1.0,
                job_timeout=1.0,
                submit_share=False,
                require_accept=False,
                share_seconds=1.0,
                search="python",
                version_rolling=False,
                allow_cleartext=False,
            )
            tx = Transcript("fake")
            with patch("stratum_smoke.asyncio.open_connection", fake_open_connection):
                return await smoke(args, tx)

        env = {
            "MINING_BRAIINS_HOST": "stratum+tcp://pool.example:3333",
            "MINING_BRAIINS_USER": "worker",
        }
        with patch.dict(os.environ, env, clear=False):
            code = asyncio.run(run())
        self.assertEqual(code, 4)

    def test_validate_job_params_rejects_bad_fields(self) -> None:
        good = [
            "job-1",
            "00" * 32,
            "01",
            "02",
            ["aa" * 32],
            "20000000",
            "1c00ffff",
            "67000000",
            True,
        ]
        self.assertIsNone(validate_job_params(good))
        bad_prev = list(good)
        bad_prev[1] = "zz"
        self.assertIsNotNone(validate_job_params(bad_prev))
        bad_clean = list(good)
        bad_clean[8] = "yes"
        self.assertIsNotNone(validate_job_params(bad_clean))
        self.assertIsNotNone(validate_job_params(good[:8]))

    def test_nbits_rejects_zero_signed_and_overflow(self) -> None:
        self.assertGreater(target_from_nbits("1c00ffff"), 0)
        with self.assertRaises(ValueError):
            target_from_nbits("1c000000")  # zero mantissa
        with self.assertRaises(ValueError):
            target_from_nbits("1c800000")  # sign bit
        with self.assertRaises(ValueError):
            target_from_nbits("23000001")  # 1 << 256
        overflow_job = [
            "job-1",
            "00" * 32,
            "01",
            "02",
            [],
            "20000000",
            "23000001",
            "67000000",
            True,
        ]
        self.assertIsNotNone(validate_job_params(overflow_job))

    def test_peer_is_loopback_checks_resolved_address(self) -> None:
        class Peer:
            def __init__(self, addr):
                self._addr = addr

            def get_extra_info(self, name):
                return self._addr if name == "peername" else None

        self.assertTrue(_peer_is_loopback(Peer(("127.0.0.1", 3333))))
        self.assertTrue(_peer_is_loopback(Peer(("127.0.0.2", 3333))))
        self.assertTrue(_peer_is_loopback(Peer(("::1", 3333))))
        self.assertFalse(_peer_is_loopback(Peer(("8.8.8.8", 3333))))
        self.assertFalse(_peer_is_loopback(Peer(None)))

    def test_localhost_hostname_with_remote_peer_requires_cleartext(self) -> None:
        from argparse import Namespace
        from stratum_smoke import Transcript, smoke

        class FakeWriter:
            def get_extra_info(self, name):
                return ("203.0.113.10", 3333) if name == "peername" else None

            def close(self):
                pass

            async def wait_closed(self):
                pass

        async def fake_open_connection(*_args, **_kwargs):
            return asyncio.StreamReader(), FakeWriter()

        async def run() -> int:
            args = Namespace(
                host_var="MINING_BRAIINS_HOST",
                user_var="MINING_BRAIINS_USER",
                password_var="MINING_BRAIINS_PASSWORD",
                port=3333,
                timeout=1.0,
                job_timeout=1.0,
                submit_share=False,
                require_accept=False,
                share_seconds=1.0,
                search="python",
                version_rolling=False,
                allow_cleartext=False,
            )
            tx = Transcript("fake")
            with patch("stratum_smoke.asyncio.open_connection", fake_open_connection):
                return await smoke(args, tx)

        env = {
            "MINING_BRAIINS_HOST": "stratum+tcp://localhost:3333",
            "MINING_BRAIINS_USER": "smoke",
        }
        with patch.dict(os.environ, env, clear=False):
            code = asyncio.run(run())
        self.assertEqual(code, 4)

    def test_full_ipv4_loopback_peer_skips_cleartext_flag(self) -> None:
        from argparse import Namespace
        from stratum_smoke import Transcript, smoke

        class FakeWriter:
            def get_extra_info(self, name):
                return ("127.0.0.2", 3333) if name == "peername" else None

            def write(self, _data):
                pass

            async def drain(self):
                pass

            def close(self):
                pass

            async def wait_closed(self):
                pass

        async def fake_open_connection(*_args, **_kwargs):
            reader = asyncio.StreamReader()
            reader.feed_eof()
            return reader, FakeWriter()

        async def run():
            args = Namespace(
                host_var="MINING_BRAIINS_HOST",
                user_var="MINING_BRAIINS_USER",
                password_var="MINING_BRAIINS_PASSWORD",
                port=3333,
                timeout=0.2,
                job_timeout=0.2,
                submit_share=False,
                require_accept=False,
                share_seconds=1.0,
                search="python",
                version_rolling=False,
                allow_cleartext=False,
            )
            tx = Transcript("fake")
            with patch("stratum_smoke.asyncio.open_connection", fake_open_connection):
                code = await smoke(args, tx)
            return code, tx

        env = {
            "MINING_BRAIINS_HOST": "stratum+tcp://127.0.0.2:3333",
            "MINING_BRAIINS_USER": "smoke",
        }
        with patch.dict(os.environ, env, clear=False):
            code, tx = asyncio.run(run())
        self.assertNotEqual(code, 4)
        self.assertTrue(tx.data.get("peer_loopback"))
        self.assertTrue(any(s["step"] == "tcp_connect" and s["ok"] for s in tx.data["steps"]))


class TranscriptTests(unittest.TestCase):
    def test_write_does_not_overwrite_same_stamp(self) -> None:
        import tempfile
        from pathlib import Path
        from stratum_smoke import EVIDENCE, Transcript

        with tempfile.TemporaryDirectory() as tmp:
            with patch("stratum_smoke.EVIDENCE", Path(tmp)):
                first = Transcript("fake")
                first.stamp = "20260101T000000"
                first.data["started"] = first.stamp
                first.step("a", True, "one")
                path1 = first.write()
                second = Transcript("fake")
                second.stamp = "20260101T000000"
                second.data["started"] = second.stamp
                second.step("b", True, "two")
                path2 = second.write()
                self.assertNotEqual(path1, path2)
                self.assertTrue(path1.exists())
                self.assertTrue(path2.exists())
                self.assertIn('"one"', path1.read_text(encoding="utf-8"))
                self.assertIn('"two"', path2.read_text(encoding="utf-8"))


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

    def test_take_pending_keeps_latest_notify(self) -> None:
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
                session.stash.extend(
                    [
                        {"method": "mining.notify", "params": ["old"] + ["00"] * 7 + [True]},
                        {"method": "mining.set_difficulty", "params": [1]},
                        {"method": "mining.notify", "params": ["new"] + ["00"] * 7 + [True]},
                    ]
                )
                pending = session.take_pending("mining.notify")
                self.assertEqual([m["params"][0] for m in pending], ["old", "new"])
                self.assertEqual(session.stash[0]["method"], "mining.set_difficulty")
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

    def test_search_stops_when_work_generation_advances(self) -> None:
        from stratum_smoke import search_share

        async def scenario() -> None:
            generation = {"value": 1}
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

            async def bump():
                await asyncio.sleep(0.05)
                generation["value"] = 2

            stopper = asyncio.create_task(bump())
            with self.assertRaises(WorkChanged):
                await search_share(
                    "python",
                    job,
                    "deadbeef",
                    "00000000",
                    DIFF1,
                    deadline=time_deadline(),
                    work_generation=1,
                    get_work_generation=lambda: generation["value"],
                )
            await stopper

        def time_deadline() -> float:
            import time

            return time.monotonic() + 30.0

        asyncio.run(scenario())

    def test_notify_snapshots_difficulty_and_work_generation(self) -> None:
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
                reader.feed_data(
                    (
                        json.dumps(
                            {"id": None, "method": "mining.set_difficulty", "params": [4]}
                        )
                        + "\n"
                    ).encode()
                )
                reader.feed_data(
                    (
                        json.dumps(
                            {
                                "id": None,
                                "method": "mining.notify",
                                "params": ["snap-job"] + ["00"] * 7 + [True],
                            }
                        )
                        + "\n"
                    ).encode()
                )
                notify = await session.wait_for("mining.notify", timeout=1.0)
                self.assertEqual(notify["_difficulty"], 4)
                self.assertEqual(notify["_work_generation"], session.work_generation)
                # set_difficulty does not bump; clean_jobs=True does once.
                self.assertEqual(session.work_generation, 1)
            finally:
                session.alive.clear()
                session.pump.cancel()
                try:
                    await session.pump
                except (asyncio.CancelledError, Exception):
                    pass

        asyncio.run(scenario())

    def test_set_difficulty_and_non_clean_notify_keep_generation(self) -> None:
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
                session.phase = "search"
                session.work_generation = 3
                reader.feed_data(
                    (
                        json.dumps(
                            {"id": None, "method": "mining.set_difficulty", "params": [8]}
                        )
                        + "\n"
                    ).encode()
                )
                reader.feed_data(
                    (
                        json.dumps(
                            {
                                "id": None,
                                "method": "mining.notify",
                                "params": ["keep-job"] + ["00"] * 7 + [False],
                            }
                        )
                        + "\n"
                    ).encode()
                )
                notify = await session.wait_for("mining.notify", timeout=1.0)
                self.assertEqual(session.difficulty, 8)
                self.assertEqual(session.work_generation, 3)
                self.assertEqual(notify["_work_generation"], 3)
                self.assertFalse(notify["_clean_jobs"])
                self.assertEqual(notify["_difficulty"], 8)

                reader.feed_data(
                    (
                        json.dumps(
                            {
                                "id": None,
                                "method": "mining.notify",
                                "params": ["clean-job"] + ["00"] * 7 + [True],
                            }
                        )
                        + "\n"
                    ).encode()
                )
                clean = await session.wait_for("mining.notify", timeout=1.0)
                self.assertEqual(session.work_generation, 4)
                self.assertTrue(clean["_clean_jobs"])
            finally:
                session.alive.clear()
                session.pump.cancel()
                try:
                    await session.pump
                except (asyncio.CancelledError, Exception):
                    pass

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
