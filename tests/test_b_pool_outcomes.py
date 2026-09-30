"""Owner-B pool lifecycle: reject/timeout/accept land in distinct counters.

Drives the real StratumClient over loopback TCP against scripted pool
servers so ``counters`` in the published stratum snapshot are evidence, not
mocks. A request timeout must resolve OUTCOME_UNKNOWN (never an invented
acknowledgement), distinct from a literal pool reject.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

PY_DIR = Path(__file__).resolve().parents[1] / "mla1517_platform_v3.4" / "python"
sys.path.insert(0, str(PY_DIR))

import pytest

from manifold_pool_coordinator import PoolEndpoint, StratumClient

NOTIFY = ["job-early", "ab" * 32, "aa", "bb", [], "00000001", "1a0bb4f4", "5f3f2a1e", True]


def _server_for(submit_result, *, hang_on_submit: bool = False):
    """A fake pool that performs the handshake then answers mining.submit."""

    async def handler(reader, writer):
        try:
            while line := await reader.readline():
                request = json.loads(line)
                method = request["method"]
                if method == "mining.subscribe":
                    writer.write(
                        json.dumps({"id": request["id"], "result": [[], "00", 4]}).encode() + b"\n"
                    )
                    writer.write(
                        json.dumps(
                            {"id": None, "method": "mining.notify", "params": NOTIFY}
                        ).encode()
                        + b"\n"
                    )
                elif method == "mining.authorize":
                    writer.write(json.dumps({"id": request["id"], "result": True}).encode() + b"\n")
                    writer.write(
                        json.dumps(
                            {"id": None, "method": "mining.set_target", "params": ["ff" * 32]}
                        ).encode()
                        + b"\n"
                    )
                elif method == "mining.submit":
                    if hang_on_submit:
                        await asyncio.sleep(30)  # pool never answers
                        continue
                    writer.write(
                        json.dumps({"id": request["id"], "result": submit_result}).encode() + b"\n"
                    )
                await writer.drain()
        finally:
            writer.close()

    return handler


async def _connected_client(submit_result, *, hang_on_submit: bool = False, timeout: float = 5.0):
    server = await asyncio.start_server(
        _server_for(submit_result, hang_on_submit=hang_on_submit), "127.0.0.1", 0
    )
    endpoint = PoolEndpoint("127.0.0.1", server.sockets[0].getsockname()[1], "t")
    client = StratumClient(endpoint, username="w", password="x", request_timeout=timeout)
    try:
        await asyncio.wait_for(client.connect(), 5)
        for _ in range(200):
            if client.runtime_state.ready:
                break
            await asyncio.sleep(0.01)
        assert client.runtime_state.ready
    except Exception:
        server.close()
        await server.wait_closed()
        raise
    return client, server


def _submit_params() -> list:
    return ["worker.1", "job-early", "00000000", "5f3f2a1e", "00000001"]


def test_pool_accept_and_reject_are_distinct_counters():
    async def run() -> None:
        client, server = await _connected_client(True)
        try:
            result = await client.submit(_submit_params())
            assert result is True
            counters = client.runtime_state.snapshot()["counters"]
            assert counters["accepted"] == 1
            assert counters["rejected"] == 0
            assert counters["unknown"] == 0
            assert counters["submitted"] == 1
        finally:
            await client.close()
            server.close()
            await server.wait_closed()

        client, server = await _connected_client(False)
        try:
            result = await client.submit(_submit_params())
            assert result is False
            counters = client.runtime_state.snapshot()["counters"]
            assert counters["accepted"] == 0
            assert counters["rejected"] == 1
            assert counters["unknown"] == 0
        finally:
            await client.close()
            server.close()
            await server.wait_closed()

    asyncio.run(run())


def test_pool_timeout_is_outcome_unknown_not_invented_ack():
    async def run() -> None:
        client, server = await _connected_client(None, hang_on_submit=True, timeout=0.3)
        try:
            with pytest.raises(TimeoutError):
                await client.submit(_submit_params())
            snapshot = client.runtime_state.snapshot()
            counters = snapshot["counters"]
            # The honest outcome: submitted but no verdict -> unknown,
            # never counted as accepted or rejected.
            assert counters["submitted"] == 1
            assert counters["accepted"] == 0
            assert counters["rejected"] == 0
            assert counters["unknown"] == 1
            assert snapshot["submission"]["state"] == "OUTCOME_UNKNOWN"
        finally:
            await client.close()
            server.close()
            await server.wait_closed()

    asyncio.run(run())


def test_submit_without_active_job_is_refused():
    async def run() -> None:
        server = await asyncio.start_server(_server_for(True), "127.0.0.1", 0)
        endpoint = PoolEndpoint("127.0.0.1", server.sockets[0].getsockname()[1], "t")
        client = StratumClient(endpoint, username="w", password="x", request_timeout=1.0)
        try:
            # Never connected: submit must fail closed, no counters move.
            with pytest.raises(RuntimeError):
                await client.submit(_submit_params())
            counters = client.runtime_state.snapshot()["counters"]
            assert counters == {
                "jobs_received": 0,
                "jobs_invalidated": 0,
                "disconnects": 0,
                "submitted": 0,
                "accepted": 0,
                "rejected": 0,
                "unknown": 0,
            }
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run())
