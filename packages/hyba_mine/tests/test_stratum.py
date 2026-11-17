# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Stratum V1 client against an in-process pool that verifies every share."""

import asyncio
import shutil
import ssl
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

import _support
from _support import GENESIS_EN2, GENESIS_NONCE, SENTINEL_PASSWORD, SENTINEL_USER, VerifyingPool

from hyba_mine.credentials import PoolLogin
from hyba_mine.pools import get_pool
from hyba_mine.stratum import (
    AuthorizationRejected,
    ConnectionLost,
    HandshakeFailed,
    PoolSession,
    StratumConnection,
    VersionMaskMismatch,
    handshake_probe,
)
from hyba_mine.vectors import GENESIS
from hyba_mine.work import VERSION_ROLLING_MIN_BITS, make_unit, sha256d, share_target

LOGIN = PoolLogin(SENTINEL_USER, SENTINEL_PASSWORD)


def _session(pool: VerifyingPool, records: list, **kwargs) -> PoolSession:
    return PoolSession(
        get_pool("viabtc"), kwargs.pop("login", LOGIN),
        record=lambda kind, data: records.append((kind, data)),
        endpoints=(pool.endpoint(),), backoff=(0.05,), **kwargs,
    )


async def _connected(session: PoolSession, timeout: float = 10.0):
    job = await session.wait_for_job(timeout=timeout)
    assert job is not None, "no job from the pool"
    return job


class TestHandshakeAndShares(unittest.TestCase):
    def test_handshake_job_and_genesis_known_answer_share_is_accepted(self):
        self.assertTrue(_support.genesis_job_check())

        async def scenario():
            pool = VerifyingPool(difficulty=1)
            await pool.start()
            records = []
            session = _session(pool, records)
            task = asyncio.create_task(session.run())
            try:
                job = await _connected(session)
                self.assertEqual(job.job_id, "genesis")
                self.assertEqual(job.difficulty, Fraction(1))
                self.assertEqual(job.header_prefix(GENESIS_EN2), GENESIS.prefix)
                sub = await session.submit(job, GENESIS_EN2, GENESIS_NONCE)
                reply = await asyncio.wait_for(sub.future, 5)
                self.assertEqual(reply, {"id": sub.request_id, "result": True, "error": None})
                self.assertEqual(len(pool.accepted), 1)
                again = await session.submit(job, GENESIS_EN2, GENESIS_NONCE)
                reply = await asyncio.wait_for(again.future, 5)
                self.assertEqual(reply["error"], [22, "Duplicate share", None])
                wrong = await session.submit(job, GENESIS_EN2, GENESIS_NONCE + 1)
                reply = await asyncio.wait_for(wrong.future, 5)
                self.assertIsNone(reply["result"])
                self.assertEqual(reply["error"], [23, "Low difficulty share", None])
            finally:
                session.stop()
                await session.disconnect()
                await task
                await pool.stop()
            kinds = [kind for kind, _ in records]
            self.assertIn("pool_connected", kinds)
            self.assertIn("difficulty", kinds)
            self.assertIn("job", kinds)

        _support.run(scenario())

    def test_pool_replies_to_pings_and_rejected_login_is_fatal_without_retry(self):
        async def scenario():
            pool = VerifyingPool()
            await pool.start()
            records = []
            session = _session(pool, records, login=PoolLogin(SENTINEL_USER, "wrong-password-xyz"))
            await asyncio.wait_for(session.run(), 10)
            self.assertIsInstance(session.fatal, AuthorizationRejected)
            self.assertEqual([k for k, _ in records].count("pool_auth_rejected"), 1)
            self.assertEqual(pool.authorized, 0)
            await pool.stop()

        _support.run(scenario())


class TestStaleAndReconnect(unittest.TestCase):
    def test_clean_jobs_makes_earlier_jobs_stale_and_the_pool_agrees(self):
        async def scenario():
            pool = VerifyingPool(difficulty=Fraction(1, 10 ** 7))
            await pool.start()
            records = []
            session = _session(pool, records)
            task = asyncio.create_task(session.run())
            try:
                old = await _connected(session)
                await pool.push_job("job-2", "495fab2a", clean=True)
                for _ in range(100):
                    if session.current is not None and session.current.job_id == "job-2":
                        break
                    await asyncio.sleep(0.02)
                self.assertFalse(session.is_valid(old))
                self.assertTrue(session.is_valid(session.current))
                with self.assertRaises(ConnectionLost):
                    await session.submit(old, GENESIS_EN2, GENESIS_NONCE)
                conn = session._conn
                _, future = await conn.request("mining.submit", [SENTINEL_USER, "genesis", "00000001", old.job.ntime,
                                                                f"{GENESIS_NONCE:08x}"])
                reply = await asyncio.wait_for(future, 5)
                self.assertEqual(reply["error"], [21, "Job not found", None])
            finally:
                session.stop()
                await session.disconnect()
                await task
                await pool.stop()

        _support.run(scenario())

    def test_reconnect_after_the_pool_drops_the_connection(self):
        async def scenario():
            pool = VerifyingPool()
            await pool.start()
            records = []
            session = _session(pool, records)
            task = asyncio.create_task(session.run())
            try:
                first = await _connected(session)
                self.assertEqual(session.generation, 1)
                await pool.drop_connections()
                for _ in range(200):
                    if session.generation == 2 and session.current_job() is not None:
                        break
                    await asyncio.sleep(0.02)
                self.assertEqual(session.generation, 2)
                self.assertFalse(session.is_valid(first))
                self.assertTrue(session.is_valid(session.current_job()))
            finally:
                session.stop()
                await session.disconnect()
                await task
                await pool.stop()
            kinds = [kind for kind, _ in records]
            self.assertEqual(kinds.count("pool_connected"), 2)
            self.assertIn("pool_disconnected", kinds)

        _support.run(scenario())

    def test_silent_pool_connection_is_replaced(self):
        async def scenario():
            pool = VerifyingPool()
            await pool.start()
            records = []
            session = _session(pool, records, idle_timeout=0.5)
            task = asyncio.create_task(session.run())
            try:
                first = await _connected(session)
                for _ in range(200):
                    if session.generation >= 2 and session.current_job() is not None:
                        break
                    await asyncio.sleep(0.02)
                self.assertGreaterEqual(session.generation, 2)
                self.assertFalse(session.is_valid(first))
            finally:
                session.stop()
                await session.disconnect()
                await task
                await pool.stop()
            reasons = [data.get("reason", "") for kind, data in records if kind == "pool_disconnected"]
            self.assertTrue(any(reason.startswith("no message from the pool") for reason in reasons), reasons)

        _support.run(scenario())

    def test_pool_that_hangs_up_after_login_backs_off(self):
        async def scenario():
            pool = VerifyingPool(send_notify=False)
            await pool.start()
            records = []
            session = PoolSession(
                get_pool("viabtc"), LOGIN, record=lambda kind, data: records.append((kind, data)),
                endpoints=(pool.endpoint(),), backoff=(0.05, 0.4, 5.0), idle_timeout=0.1,
            )
            task = asyncio.create_task(session.run())
            try:
                await asyncio.sleep(1.2)
            finally:
                session.stop()
                await session.disconnect()
                await task
                await pool.stop()
            connects = sum(1 for kind, _ in records if kind == "pool_connected")
            self.assertGreaterEqual(connects, 2)
            self.assertLessEqual(connects, 4)

        _support.run(scenario())

    def test_set_extranonce_invalidates_jobs_until_the_next_notify(self):
        async def scenario():
            pool = VerifyingPool()
            await pool.start()
            records = []
            session = _session(pool, records)
            task = asyncio.create_task(session.run())
            try:
                job = await _connected(session)
                await pool.broadcast({"id": None, "method": "mining.set_extranonce", "params": ["0a0b", 4]})
                for _ in range(100):
                    if session.epoch == 1:
                        break
                    await asyncio.sleep(0.02)
                self.assertEqual(session.extranonce1, bytes.fromhex("0a0b"))
                self.assertFalse(session.is_valid(job))
                self.assertIsNone(session.current_job())
                await pool.push_job("job-3", "495fab2b", clean=True)
                fresh = await _connected(session)
                self.assertEqual((fresh.job_id, fresh.epoch, fresh.extranonce1), ("job-3", 1, bytes.fromhex("0a0b")))
            finally:
                session.stop()
                await session.disconnect()
                await task
                await pool.stop()

        _support.run(scenario())

    def test_client_answers_mining_ping(self):
        async def scenario():
            pool = VerifyingPool()
            await pool.start()
            session = _session(pool, [])
            task = asyncio.create_task(session.run())
            try:
                await _connected(session)
                await pool.broadcast({"id": 99, "method": "mining.ping", "params": []})
                for _ in range(100):
                    if pool.pings:
                        break
                    await asyncio.sleep(0.02)
                self.assertEqual(pool.pings, [{"id": 99, "result": "pong", "error": None}])
            finally:
                session.stop()
                await session.disconnect()
                await task
                await pool.stop()

        _support.run(scenario())


class TestTLS(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="hyba-mine-tls-"))
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.cert, self.key = _support.self_signed_cert(self.dir)

    def test_stratum_ssl_handshake_with_verified_certificate(self):
        async def scenario():
            pool = VerifyingPool(tls=(self.cert, self.key))
            await pool.start()
            context = ssl.create_default_context(cafile=self.cert)
            report = await handshake_probe(get_pool("viabtc"), LOGIN, ssl_context=context,
                                           endpoints=(pool.endpoint(),), timeout=10)
            self.assertTrue(report["endpoint"].startswith("stratum+ssl://127.0.0.1:"))
            self.assertTrue(report["tls"])
            self.assertEqual(report["first_job_id"], "genesis")
            await pool.stop()

        _support.run(scenario())

    def test_untrusted_certificate_fails_closed(self):
        async def scenario():
            pool = VerifyingPool(tls=(self.cert, self.key))
            await pool.start()
            with self.assertRaises(HandshakeFailed) as caught:
                await handshake_probe(get_pool("viabtc"), LOGIN, endpoints=(pool.endpoint(),), timeout=5)
            self.assertIn("stratum+ssl", str(caught.exception))
            self.assertEqual(pool.authorized, 0)
            await pool.stop()

        _support.run(scenario())


class TestConnectionEdges(unittest.TestCase):
    def test_request_after_close_raises_connection_lost(self):
        async def scenario():
            pool = VerifyingPool()
            await pool.start()
            conn = StratumConnection(pool.endpoint())
            await conn.open()
            await conn.close()
            with self.assertRaises(ConnectionLost):
                await conn.request("mining.subscribe", ["x"])
            await pool.stop()

        _support.run(scenario())

    def test_wrong_login_in_probe_raises_authorization_rejected(self):
        async def scenario():
            pool = VerifyingPool()
            await pool.start()
            with self.assertRaises(AuthorizationRejected):
                await handshake_probe(get_pool("braiins"), PoolLogin(SENTINEL_USER, "not-the-password"),
                                      endpoints=(pool.endpoint(),), timeout=5)
            await pool.stop()

        _support.run(scenario())

    def test_unreachable_endpoint_is_reported(self):
        async def scenario():
            pool = VerifyingPool()
            await pool.start()
            endpoint = pool.endpoint()
            await pool.stop()
            pool.server.close()
            await pool.server.wait_closed()
            with self.assertRaises(HandshakeFailed):
                await handshake_probe(get_pool("ckpool"), LOGIN, endpoints=(endpoint,), timeout=3)

        _support.run(scenario())


def _first_share(unit, difficulty) -> int:
    """A nonce of ``unit`` (in plan order) whose SHA-256d meets ``difficulty``, found on the host."""
    target = share_target(difficulty)
    for position in range(unit.start, unit.start + unit.count):
        nonce = unit.plan.nonce_at(position)
        if int.from_bytes(sha256d(unit.header_prefix + nonce.to_bytes(4, "little")), "little") <= target:
            return nonce
    raise AssertionError("no share in the unit")


def _records_of(records: list, kind: str) -> list:
    return [data for k, data in records if k == kind]


async def _until(predicate, timeout: float = 5.0) -> None:
    for _ in range(int(timeout / 0.02)):
        if predicate():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("condition not reached")


class TestVersionRolling(unittest.TestCase):
    def _with_session(self, pool_kwargs: dict, body, **session_kwargs):
        async def scenario():
            pool = VerifyingPool(**pool_kwargs)
            await pool.start()
            records = []
            session = _session(pool, records, **session_kwargs)
            task = asyncio.create_task(session.run())
            try:
                job = await _connected(session)
                await body(pool, session, job, records)
            finally:
                session.stop()
                await session.disconnect()
                await task
                await pool.stop()
            return pool, records

        return _support.run(scenario())

    def test_configure_is_sent_first_and_only_the_granted_mask_is_adopted(self):
        async def body(pool, session, job, records):
            self.assertEqual(pool.methods[:2], ["mining.configure", "mining.subscribe"])
            self.assertEqual(pool.configure_params, [[["version-rolling"],
                                                      {"version-rolling.mask": "1fffe000",
                                                       "version-rolling.min-bit-count": VERSION_ROLLING_MIN_BITS}]])
            self.assertTrue(session.version_rolling)
            self.assertEqual(session.version_mask, 0x00FFE000)

        _pool, records = self._with_session({"version_rolling": "00ffe000"}, body)
        connected = _records_of(records, "pool_connected")[0]
        self.assertTrue(connected["version_rolling"])
        self.assertEqual(connected["version_mask"], "00ffe000")
        self.assertEqual(connected["version_negotiation"]["outcome"], "granted")
        self.assertEqual(connected["version_negotiation"]["granted_mask"], "00ffe000")
        self.assertNotIn("dropped_pool_bits", connected["version_negotiation"])

    def test_pool_mask_bits_we_did_not_request_are_not_rolled(self):
        async def body(pool, session, job, records):
            self.assertTrue(session.version_rolling)
            self.assertEqual(session.version_mask, 0x1FFFE000)
            self.assertEqual(session.pool_version_mask, 0xFFFFFFFF)

        reply = {"version-rolling": True, "version-rolling.mask": "ffffffff"}
        _pool, records = self._with_session({"configure_reply": reply}, body)
        connected = _records_of(records, "pool_connected")[0]
        negotiation = connected["version_negotiation"]
        self.assertEqual(negotiation["pool_mask"], "ffffffff")
        self.assertEqual(negotiation["granted_mask"], "1fffe000")
        self.assertEqual(negotiation["pool_bits_not_rolled"], "e0001fff")
        self.assertEqual(connected["pool_version_mask"], "ffffffff")

    def test_shares_are_accepted_when_the_pool_mask_is_wider_than_the_rolled_mask(self):
        # The pool rebuilds nVersion with ITS mask. The job version (00000001) has a bit
        # inside the pool's mask but outside 1fffe000, so the 6th param must carry it.
        difficulty = Fraction(1, 10 ** 7)

        async def body(pool, session, job, records):
            self.assertEqual(job.base_version, 0x00000001)
            sub = await session.submit(job, GENESIS_EN2, GENESIS_NONCE, version=job.base_version, version_bits=0)
            reply = await asyncio.wait_for(sub.future, 5)
            self.assertEqual(reply["result"], True, reply)
            self.assertEqual(sub.version_bits, "00000001")
            unit = make_unit(job, 0, 0, 1 << 16, difficulty, 20, version_mask=session.version_mask, version_index=5)
            nonce = _first_share(unit, difficulty)
            self.assertTrue(session.version_compatible(job, unit.version, unit.version_bits))
            sub = await session.submit(job, unit.en2, nonce, version=unit.version, version_bits=unit.version_bits)
            reply = await asyncio.wait_for(sub.future, 5)
            self.assertEqual(reply["result"], True, reply)
            self.assertEqual(sub.version_bits, f"{unit.version:08x}")
            self.assertEqual(pool.rejected, [])
            self.assertEqual(len(pool.accepted), 2)

        for mask in ("ffffffff", "3fffe001"):
            with self.subTest(mask=mask):
                reply = {"version-rolling": True, "version-rolling.mask": mask}
                self._with_session({"difficulty": difficulty, "configure_reply": reply}, body)

    def test_a_wider_mask_from_set_version_mask_is_used_for_submits(self):
        async def body(pool, session, job, records):
            await pool.push_version_mask("ffffffff")
            await _until(lambda: session.pool_version_mask == 0xFFFFFFFF)
            self.assertEqual(session.version_mask, 0x1FFFE000)
            sub = await session.submit(job, GENESIS_EN2, GENESIS_NONCE, version=job.base_version, version_bits=0)
            reply = await asyncio.wait_for(sub.future, 5)
            self.assertEqual(reply["result"], True, reply)
            self.assertEqual(sub.version_bits, "00000001")
            # A narrower pool mask that no longer covers a rolled bit makes the unit unsendable.
            moved = make_unit(job, 0, 0, 4096, Fraction(1), 20, version_mask=0x1FFFE000, version_index=16)
            self.assertTrue(session.version_compatible(job, moved.version, moved.version_bits))
            await pool.push_version_mask("0000e001")
            await _until(lambda: session.pool_version_mask == 0x0000E001)
            self.assertFalse(session.version_compatible(job, moved.version, moved.version_bits))

        self._with_session({"difficulty": 1, "version_rolling": "1fffe000"}, body)

    def test_a_malformed_set_version_mask_keeps_the_pool_mask_for_submits(self):
        async def body(pool, session, job, records):
            await pool.push_version_mask("ffffffff")
            await _until(lambda: session.pool_version_mask == 0xFFFFFFFF)
            hashed = make_unit(job, 0, 0, 4096, Fraction(1), 20, version_mask=0x1FFFE000, version_index=16)
            await pool.push_version_mask("xyz")
            await _until(lambda: session.version_mask == 0)
            # Rolling is paused, but the pool still rebuilds nVersion with the mask it last sent.
            self.assertEqual(session.pool_version_mask, 0xFFFFFFFF)
            self.assertTrue(session.version_compatible(job, hashed.version, hashed.version_bits))
            sub = await session.submit(job, GENESIS_EN2, GENESIS_NONCE)
            self.assertEqual(sub.version_bits, f"{job.base_version:08x}")
            reply = await asyncio.wait_for(sub.future, 5)
            self.assertEqual(reply["result"], True, reply)

        self._with_session({"difficulty": 1, "version_rolling": "1fffe000"}, body)

    def test_pool_that_hangs_up_on_configure_is_mined_unrolled(self):
        async def body(pool, session, job, records):
            self.assertFalse(session.version_rolling)
            sub = await session.submit(job, GENESIS_EN2, GENESIS_NONCE)
            reply = await asyncio.wait_for(sub.future, 5)
            self.assertEqual(reply["result"], True, reply)
            self.assertIsNone(sub.version_bits)

        pool, records = self._with_session({"difficulty": 1, "configure_hangup": True}, body)
        # One configure (the pool hung up), then a connection without it.
        self.assertEqual(pool.methods.count("mining.configure"), 1)
        self.assertEqual(len(_records_of(records, "pool_connect_failed")), 1)
        warning = _records_of(records, "pool_protocol_warning")
        self.assertEqual([w["method"] for w in warning], ["mining.configure"])
        connected = _records_of(records, "pool_connected")
        self.assertEqual(len(connected), 1)
        self.assertFalse(connected[0]["version_rolling"])
        self.assertEqual(connected[0]["version_negotiation"]["outcome"], "configure_dropped")
        self.assertEqual(len(pool.accepted), 1)
        self.assertEqual(len(pool.accepted[0][0]), 5)

    def test_a_grant_below_the_minimum_bit_count_is_not_used(self):
        async def body(pool, session, job, records):
            self.assertFalse(session.version_rolling)
            self.assertEqual(session.version_mask, 0)

        _pool, records = self._with_session({"version_rolling": "00002000"}, body)
        self.assertEqual(_records_of(records, "pool_connected")[0]["version_negotiation"]["outcome"], "below_min_bits")

    def test_without_bip310_the_session_runs_unrolled_with_five_param_submits(self):
        cases = (
            ("unsupported", {}, {}),
            ("declined", {"configure_reply": {"version-rolling": False}}, {}),
            ("malformed", {"configure_reply": {"version-rolling": True, "version-rolling.mask": "xyz"}}, {}),
            ("no_reply", {"configure_silent": True}, {"configure_timeout": 0.3}),
            ("disabled", {"version_rolling": "1fffe000"}, {"version_rolling": False}),
        )
        for outcome, pool_kwargs, session_kwargs in cases:
            with self.subTest(outcome=outcome):
                async def body(pool, session, job, records):
                    self.assertFalse(session.version_rolling)
                    self.assertEqual(session.version_mask, 0)
                    sub = await session.submit(job, GENESIS_EN2, GENESIS_NONCE)
                    reply = await asyncio.wait_for(sub.future, 5)
                    self.assertEqual(reply["result"], True)
                    self.assertIsNone(sub.version_bits)

                pool, records = self._with_session({"difficulty": 1, **pool_kwargs}, body, **session_kwargs)
                negotiation = _records_of(records, "pool_connected")[0]["version_negotiation"]
                self.assertEqual(negotiation["outcome"], outcome)
                self.assertEqual(len(pool.accepted), 1)
                self.assertEqual(len(pool.accepted[0][0]), 5)
                if outcome == "disabled":
                    self.assertNotIn("mining.configure", pool.methods)

    def test_six_param_submit_is_verified_by_the_pool(self):
        difficulty = Fraction(1, 10 ** 7)

        async def body(pool, session, job, records):
            unit = make_unit(job, 0, 0, 1 << 16, difficulty, 20, version_mask=session.version_mask, version_index=5)
            self.assertNotEqual(unit.version_bits, 0)
            nonce = _first_share(unit, difficulty)
            sub = await session.submit(job, unit.en2, nonce, version=unit.version, version_bits=unit.version_bits)
            reply = await asyncio.wait_for(sub.future, 5)
            self.assertEqual(reply["result"], True, reply)
            self.assertEqual(sub.version_bits, f"{unit.version_bits:08x}")
            params = pool.accepted[-1][0]
            self.assertEqual(len(params), 6)
            self.assertEqual(params[5], f"{unit.version_bits:08x}")
            sent = len(pool.methods)
            with self.assertRaises(VersionMaskMismatch):
                await session.submit(job, unit.en2, nonce, version=job.base_version ^ 1, version_bits=0x00000001)
            await asyncio.sleep(0.1)
            self.assertEqual(len(pool.methods), sent)
            self.assertEqual(pool.rejected, [])

        self._with_session({"difficulty": difficulty, "version_rolling": "1fffe000"}, body)

    def test_set_version_mask_updates_the_mask_without_invalidating_jobs(self):
        async def body(pool, session, job, records):
            self.assertEqual(session.version_mask, 0x1FFFE000)
            moved = make_unit(job, 0, 0, 4096, Fraction(1), 20, version_mask=0x1FFFE000, version_index=16)
            kept = make_unit(job, 0, 0, 4096, Fraction(1), 20, version_mask=0x1FFFE000, version_index=0)
            self.assertIsNone(session.stale_reason(job, moved.version, moved.version_bits))
            await pool.push_version_mask("0000e000")
            await _until(lambda: session.version_mask == 0x0000E000)
            self.assertTrue(session.is_valid(job))
            self.assertTrue(session.version_rolling)
            self.assertEqual(moved.version_bits, 0x00020000)
            self.assertFalse(session.version_compatible(job, moved.version, moved.version_bits))
            self.assertTrue(session.version_compatible(job, kept.version, kept.version_bits))
            self.assertEqual(session.stale_reason(job, moved.version, moved.version_bits), "version_mask_changed")
            self.assertIsNone(session.stale_reason(job, kept.version, kept.version_bits))
            with self.assertRaises(VersionMaskMismatch):
                await session.submit(job, moved.en2, 0, version=moved.version, version_bits=moved.version_bits)

        _pool, records = self._with_session({"version_rolling": "1fffe000"}, body)
        change = _records_of(records, "version_mask")
        self.assertEqual(len(change), 1)
        self.assertEqual((change[0]["previous_mask"], change[0]["granted_mask"]), ("1fffe000", "0000e000"))

    def test_set_version_mask_without_negotiation_is_ignored(self):
        async def body(pool, session, job, records):
            await pool.push_version_mask("1fffe000")
            await _until(lambda: any(k == "pool_protocol_warning" for k, _ in records))
            self.assertEqual(session.version_mask, 0)
            self.assertFalse(session.version_rolling)

        _pool, records = self._with_session({}, body)
        warning = _records_of(records, "pool_protocol_warning")[0]
        self.assertEqual(warning["method"], "mining.set_version_mask")
        self.assertEqual(_records_of(records, "version_mask"), [])

    def test_reconnect_renegotiates_version_rolling(self):
        async def body(pool, session, job, records):
            await pool.push_version_mask("0000e000")
            await _until(lambda: session.version_mask == 0x0000E000)
            await pool.drop_connections()
            await _until(lambda: session.generation == 2 and session.current_job() is not None)
            self.assertEqual(session.version_mask, 0x1FFFE000)

        pool, records = self._with_session({"version_rolling": "1fffe000"}, body)
        self.assertEqual(pool.methods.count("mining.configure"), 2)
        connected = _records_of(records, "pool_connected")
        self.assertEqual(len(connected), 2)
        self.assertTrue(all(c["version_negotiation"]["outcome"] == "granted" for c in connected))
        self.assertTrue(all(c["version_mask"] == "1fffe000" for c in connected))

    def test_probe_reports_the_negotiated_version_rolling(self):
        async def scenario():
            pool = VerifyingPool(version_rolling="1fffe000")
            await pool.start()
            report = await handshake_probe(get_pool("viabtc"), LOGIN, endpoints=(pool.endpoint(),), timeout=10)
            await pool.stop()
            return report

        report = _support.run(scenario())
        self.assertTrue(report["version_rolling"])
        self.assertEqual(report["version_mask"], "1fffe000")
        self.assertEqual(report["version_negotiation"]["outcome"], "granted")


if __name__ == "__main__":
    unittest.main()
