"""TCP Stratum session: handshake, header, submit, drop, reconnect."""

from __future__ import annotations

import asyncio
import json
import unittest

from manifold_pool_coordinator import (
    ManifoldPoolCoordinator,
    PoolEndpoint,
    StratumAuthorizationError,
    StratumClient,
    StratumProtocolError,
)
from chronus.mla1517.mining.stratum_adapter import StaleJobError, sha256d

NOTIFY = [
    "job-tcp",
    "4d16b6f85af6e2198f44ae2a6de67f78487ae5611b77c6c0440b921e00000000",
    "01000000",
    "ffffffff",
    [],
    "20000000",
    "1d00ffff",
    "65abcdef",
    True,
]


def _line(payload: dict) -> bytes:
    return (json.dumps(payload, separators=(",", ":")) + "\n").encode()


class _Pool:
    def __init__(self) -> None:
        self.submits: list[list] = []
        self.connections = 0
        self.reject_next_authorize = False
        self.drop_submit_response = False

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.connections += 1
        reject = self.reject_next_authorize
        self.reject_next_authorize = False
        try:
            subscribe = json.loads(await reader.readline())
            writer.write(
                _line(
                    {
                        "id": subscribe["id"],
                        "result": [[["mining.notify", "ae"]], "01020304", 4],
                        "error": None,
                    }
                )
            )
            authorize = json.loads(await reader.readline())
            writer.write(_line({"id": authorize["id"], "result": not reject, "error": None}))
            await writer.drain()
            if reject:
                return
            writer.write(_line({"id": None, "method": "mining.set_target", "params": ["ff" * 32]}))
            writer.write(_line({"id": None, "method": "mining.notify", "params": NOTIFY}))
            await writer.drain()
            submit = json.loads(await reader.readline())
            self.submits.append(submit["params"])
            if self.drop_submit_response:
                return
            writer.write(_line({"id": submit["id"], "result": True, "error": None}))
            await writer.drain()
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass


class StratumSessionTests(unittest.TestCase):
    def test_handshake_submit_drop_and_reconnect(self) -> None:
        asyncio.run(self._run())

    async def _run(self) -> None:
        pool = _Pool()
        server = await asyncio.start_server(pool.handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        snapshots: list[dict] = []
        client = StratumClient(
            PoolEndpoint("127.0.0.1", port, "local"),
            username="PYTHIA.001",
            password="x",
            request_timeout=2.0,
            status_sink=snapshots.append,
        )
        try:
            await client.connect()
            self.assertEqual(client.proof_adapter.subscription.extranonce1, "01020304")
            job = client.proof_adapter.current_job
            self.assertIsNotNone(job)
            self.assertEqual(job.job_id, "job-tcp")
            header = client.proof_adapter.build_header("job-tcp", "00000000", "65abcdef", 1)
            self.assertEqual(len(header), 80)
            self.assertEqual(header[4:8], bytes.fromhex("f8b6164d"))
            proof = client.proof_adapter.validate_candidate(
                job_id="job-tcp", extranonce2="00000000", ntime="65abcdef", nonce=1
            )
            self.assertEqual(proof.digest, sha256d(header))
            accepted = await client.submit(["PYTHIA.001", *proof.submission_params])
            self.assertIs(accepted, True)
            self.assertEqual(pool.submits[0][0], "PYTHIA.001")
            self.assertEqual(pool.submits[0][1], "job-tcp")
            self.assertTrue(
                any(
                    snapshot["connected"] and not snapshot["primary"]["authorized"]
                    for snapshot in snapshots
                )
            )
            self.assertTrue(any(snapshot["state"] == "READY" for snapshot in snapshots))
            self.assertTrue(
                any(snapshot["submission"]["state"] == "ACCEPTED" for snapshot in snapshots)
            )
            deadline = asyncio.get_running_loop().time() + 1.0
            while (
                client.proof_adapter.subscription is not None
                and asyncio.get_running_loop().time() < deadline
            ):
                await asyncio.sleep(0.01)
            self.assertIsNone(client.proof_adapter.subscription)
            with self.assertRaises(StaleJobError):
                client.proof_adapter.build_header("job-tcp", "00000000", "65abcdef", 1)
            await client.connect()
            self.assertEqual(client.proof_adapter.current_job.job_id, "job-tcp")
            self.assertEqual(pool.connections, 2)
        finally:
            await client.close()
            server.close()
            await server.wait_closed()

    def test_lost_submit_response_is_outcome_unknown(self) -> None:
        asyncio.run(self._unknown_submit())

    async def _unknown_submit(self) -> None:
        pool = _Pool()
        pool.drop_submit_response = True
        server = await asyncio.start_server(pool.handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        client = StratumClient(
            PoolEndpoint("127.0.0.1", port, "local"),
            username="PYTHIA.001",
            password="x",
            request_timeout=2.0,
        )
        try:
            await client.connect()
            with self.assertRaises(ConnectionError):
                await client.submit(["PYTHIA.001", "job-tcp", "00000000", "65abcdef", "00000001"])
            snapshot = client.status_snapshot()
            self.assertEqual(snapshot["submission"]["state"], "OUTCOME_UNKNOWN")
            self.assertEqual(snapshot["counters"]["unknown"], 1)
        finally:
            await client.close()
            server.close()
            await server.wait_closed()

    def test_rejected_authorize_does_not_count_as_connected(self) -> None:
        asyncio.run(self._reject())

    async def _reject(self) -> None:
        pool = _Pool()
        pool.reject_next_authorize = True
        server = await asyncio.start_server(pool.handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        client = StratumClient(
            PoolEndpoint("127.0.0.1", port, "local"),
            username="PYTHIA.001",
            password="x",
            request_timeout=2.0,
        )
        try:
            with self.assertRaises(StratumProtocolError):
                await client.connect()
            self.assertIsNone(client.proof_adapter.subscription)
            self.assertFalse(client.connected)
        finally:
            await client.close()
            server.close()
            await server.wait_closed()

    def test_all_authorization_failures_raise_hard_fault(self) -> None:
        asyncio.run(self._all_auth_failures())

    async def _all_auth_failures(self) -> None:
        pools = [_Pool(), _Pool()]
        for pool in pools:
            pool.reject_next_authorize = True
        servers = [await asyncio.start_server(pool.handle, "127.0.0.1", 0) for pool in pools]
        endpoints = [
            PoolEndpoint("127.0.0.1", server.sockets[0].getsockname()[1], f"local-{index}")
            for index, server in enumerate(servers)
        ]
        coordinator = ManifoldPoolCoordinator(
            endpoints,
            username="PYTHIA.001",
            password="x",
        )
        try:
            with self.assertRaises(StratumAuthorizationError):
                await coordinator.connect_with_failover()
            self.assertEqual([pool.connections for pool in pools], [1, 1])
        finally:
            for server in servers:
                server.close()
                await server.wait_closed()


if __name__ == "__main__":
    unittest.main()
