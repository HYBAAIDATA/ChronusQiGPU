from __future__ import annotations

import asyncio
import json

import pytest

from mining.production_miner import (
    ProductionMiner,
    PoolEndpoint,
    StratumV1Client,
    difficulty_target,
    parse_endpoint,
    target_from_hex,
)
from mining.bitcoin_hasher import BitcoinHasher


def test_endpoint_parsing_and_tls():
    assert parse_endpoint("stratum+ssl://example.test:443").tls is True
    assert parse_endpoint("example.test:3333").tls is False


def test_target_decoding_is_exact():
    assert difficulty_target(1) == 0x00000000FFFF0000000000000000000000000000000000000000000000000000
    assert target_from_hex("00" * 31 + "01") == 1


def test_auth_job_search_submit_accepts_against_mock_pool():
    async def _run():
        received: list[dict] = []

        async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
            try:
                while line := await reader.readline():
                    message = json.loads(line)
                    received.append(message)
                    method = message.get("method")
                    if method == "mining.subscribe":
                        response = {"id": message["id"], "result": [[], "01020304", 4], "error": None}
                        writer.write((json.dumps(response) + "\n").encode())
                        await writer.drain()
                    elif method == "mining.authorize":
                        response = {"id": message["id"], "result": True, "error": None}
                        writer.write((json.dumps(response) + "\n").encode())
                        writer.write((json.dumps({"id": None, "method": "mining.set_target", "params": ["ff" * 32]}) + "\n").encode())
                        writer.write((json.dumps({"id": None, "method": "mining.notify", "params": [
                            "job-1", "00" * 32, "", "", [], "01000000", "ffff001d", "29ab5f49", True
                        ]}) + "\n").encode())
                        await writer.drain()
                    elif method == "mining.submit":
                        response = {"id": message["id"], "result": True, "error": None}
                        writer.write((json.dumps(response) + "\n").encode())
                        await writer.drain()
                        break
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        client = StratumV1Client(PoolEndpoint("127.0.0.1", port, False), "worker", "x", timeout=2)
        try:
            await client.connect_and_authorize()
            miner = ProductionMiner(client, BitcoinHasher(backend="cpu"), window=1, submit_enabled=True)
            assert await asyncio.wait_for(miner.run_session(max_runtime=5, max_shares=1), 5)
            assert client.accepted == 1
            assert [m["method"] for m in received] == ["mining.subscribe", "mining.authorize", "mining.submit"]
        finally:
            await client.close()
            server.close()
            await server.wait_closed()

    asyncio.run(_run())
