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
    handshake_probe,
)
from hyba_mine.vectors import GENESIS

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


if __name__ == "__main__":
    unittest.main()
