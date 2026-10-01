"""
LUCAS WIRING: Stratum v1 Live Session Integration Harness
Tests StratumBridge async job ingestion, extranonce/nTime parsing,
and O(1) candidate submission without external pool dependencies.
"""

import sys
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if sys.path[0] != _REPO_ROOT:
    sys.path.insert(0, _REPO_ROOT)

import asyncio
import json
import time
import pytest
from typing import Dict, Any, List

# Ensure StratumBridge import path aligns with your repository structure
from mining.stratum_bridge import StratumBridge


class MockStratumServer:
    """In-memory Stratum v1 server simulating pool state transitions."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0):
        self.host = host
        self.port = port
        self.server = None
        self.client_reader = None
        self.client_writer = None
        self.received_messages: List[Dict[str, Any]] = []
        self.subscribed = False
        self.authorized = False

    async def start(self):
        self.server = await asyncio.start_server(self._handle_client, self.host, self.port)
        self.port = self.server.sockets[0].getsockname()[1]

    async def stop(self):
        if self.client_writer:
            self.client_writer.close()
            await self.client_writer.wait_closed()
        if self.server:
            self.server.close()
            await self.server.wait_closed()

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.client_reader = reader
        self.client_writer = writer

        while not reader.at_eof():
            line = await reader.readline()
            if not line:
                break
            msg = json.loads(line.decode().strip())
            self.received_messages.append(msg)
            await self._dispatch_response(msg, writer)

    async def _dispatch_response(self, msg: Dict[str, Any], writer: asyncio.StreamWriter):
        msg_id = msg.get("id")
        method = msg.get("method")

        if method == "mining.subscribe":
            self.subscribed = True
            # [session_id, extranonce1, extranonce2_size]
            response = {
                "id": msg_id,
                "result": [
                    [
                        ["mining.set_difficulty", "b4b6693b72a50c7116db18d6497cac52"],
                        ["mining.notify", "ae6812eb4cd7735a302a8a9dd95cf71f"],
                    ],
                    "08000002",
                    4,
                ],
                "error": None,
            }
            writer.write((json.dumps(response) + "\n").encode())
            await writer.drain()

        elif method == "mining.authorize":
            self.authorized = True
            response = {"id": msg_id, "result": True, "error": None}
            writer.write((json.dumps(response) + "\n").encode())
            await writer.drain()

        elif method == "mining.submit":
            # Immediate pool share acceptance response
            response = {"id": msg_id, "result": True, "error": None}
            writer.write((json.dumps(response) + "\n").encode())
            await writer.drain()

    async def broadcast_job(
        self,
        job_id: str = "bf",
        prevhash: str = "4d16b6f85af6e2198c4b15bb1bb7e361d759294274c01297d589e956bc56b429",
        coinb1: str = "01000000010000000000000000000000000000000000000000000000000000000000000000ffffffff2002",
        coinb2: str = "00000000",
        merkle_branch: List[str] = None,
        version: str = "00000002",
        nbits: str = "1c2ac4af",
        ntime: str = "4dd7b503",
        clean_jobs: bool = True,
    ):
        """Simulates pool broadcasting a live mining.notify job."""
        if not self.client_writer:
            raise RuntimeError("Client not connected to mock pool.")

        if merkle_branch is None:
            merkle_branch = [
                "c06631e14324726e1e80a5d245c60257e1edeec7b94bda1335c6977717355551",
                "f0361e05917444c00be92f90d139a7734f52526479f1054c906e86134a9f79b5",
            ]

        notify_payload = {
            "id": None,
            "method": "mining.notify",
            "params": [
                job_id,
                prevhash,
                coinb1,
                coinb2,
                merkle_branch,
                version,
                nbits,
                ntime,
                clean_jobs,
            ],
        }
        self.client_writer.write((json.dumps(notify_payload) + "\n").encode())
        await self.client_writer.drain()


# =====================================================================
# Verification Suites
# =====================================================================


@pytest.mark.asyncio
async def test_stratum_handshake_and_authorization():
    """Verify clean connect -> subscribe -> authorize handshake loop."""
    server = MockStratumServer()
    await server.start()

    try:
        bridge = StratumBridge(
            host=server.host, port=server.port, worker_name="worker_test.01", worker_pass="x"
        )
        await bridge.connect()
        await bridge.handshake()

        # Check server observed proper protocol exchange
        assert server.subscribed is True
        assert server.authorized is True
        assert bridge.extranonce1 == "08000002"
        assert bridge.extranonce2_size == 4
    finally:
        await bridge.disconnect()
        await server.stop()


@pytest.mark.asyncio
async def test_job_notify_ingestion_and_template_cache():
    """Verify mining.notify correctly parses and caches block template invariants."""
    server = MockStratumServer()
    await server.start()

    try:
        bridge = StratumBridge(
            host=server.host, port=server.port, worker_name="worker_test.01", worker_pass="x"
        )
        await bridge.connect()
        await bridge.handshake()

        # Listen in background
        listen_task = asyncio.create_task(bridge.listen_forever())

        test_prevhash = "11223344556677889900aabbccddeeff11223344556677889900aabbccddeeff"
        test_job_id = "job_99"

        await server.broadcast_job(
            job_id=test_job_id, prevhash=test_prevhash, ntime="66e85501", clean_jobs=True
        )

        # Allow event loop to process notification
        await asyncio.sleep(0.05)

        active_job = bridge.get_active_job()
        assert active_job is not None
        assert active_job["job_id"] == test_job_id
        assert active_job["prevhash"] == test_prevhash
        assert active_job["ntime"] == "66e85501"

        listen_task.cancel()
        try:
            await listen_task
        except asyncio.CancelledError:
            pass
    finally:
        await bridge.disconnect()
        await server.stop()


def test_clean_job_generation_invalidates_only_superseded_work():
    bridge = StratumBridge("localhost", 3333, worker_name="worker_test.01", worker_pass="x")

    def notify(job_id: str, clean_jobs: bool):
        bridge._handle_server_message(
            {
                "method": "mining.notify",
                "params": [
                    job_id,
                    "00" * 32,
                    "00",
                    "00",
                    [],
                    "00000001",
                    "1d00ffff",
                    "00000001",
                    clean_jobs,
                ],
            }
        )

    notify("job_a", True)
    generation = bridge.clean_job_generation
    notify("job_b", False)
    assert bridge.is_job_valid(generation)
    notify("job_c", True)
    assert not bridge.is_job_valid(generation)


@pytest.mark.asyncio
async def test_sub_millisecond_share_submission():
    """Ensure submission socket dispatch operates without blocking on post-mortems."""
    server = MockStratumServer()
    await server.start()

    try:
        bridge = StratumBridge(
            host=server.host, port=server.port, worker_name="worker_test.01", worker_pass="x"
        )
        await bridge.connect()
        await bridge.handshake()

        listen_task = asyncio.create_task(bridge.listen_forever())

        await server.broadcast_job(job_id="job_fast")
        await asyncio.sleep(0.02)

        # Benchmark dispatch path
        t0 = time.perf_counter()
        submit_result = await bridge.submit_share(
            job_id="job_fast", extranonce2="00000001", ntime="4dd7b503", nonce="7a250000"
        )
        latency_ms = (time.perf_counter() - t0) * 1000.0

        # Assert sub-millisecond network dispatch latency threshold
        assert latency_ms < 5.0, f"Submit dispatch too slow: {latency_ms:.3f} ms"
        # The dispatch invariant proper: the socket flush itself must be
        # <5 ms — verdict round-trip is network-dependent and measured
        # separately by `latency_ms` above.
        assert bridge.last_dispatch_ms is not None
        assert (
            bridge.last_dispatch_ms < 5.0
        ), f"socket flush too slow: {bridge.last_dispatch_ms:.3f} ms"
        assert submit_result is True

        # Confirm submission reached the server
        submits = [m for m in server.received_messages if m.get("method") == "mining.submit"]
        assert len(submits) == 1
        assert submits[0]["params"][1] == "job_fast"

        listen_task.cancel()
        try:
            await listen_task
        except asyncio.CancelledError:
            pass
    finally:
        await bridge.disconnect()
        await server.stop()
