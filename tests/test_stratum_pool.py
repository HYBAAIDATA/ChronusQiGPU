"""Stratum V1 pool client tests: header assembly, difficulty, and a fake pool.

Header construction is validated against the Bitcoin genesis block, and the
full client lifecycle (subscribe/authorize/notify/submit) runs against an
in-process fake Stratum pool over a real socket.
"""

import asyncio
import hashlib
import json

import pytest

from chronus.execution.stratum import (
    DIFF1_TARGET,
    StratumError,
    StratumJob,
    StratumSession,
    StratumV1Client,
    build_coinbase,
    build_header,
    build_header_prefix,
    difficulty_to_target,
    merkle_root,
    sha256d,
)

# Bitcoin genesis block (block 0) reference data.
GENESIS_COINBASE_HEX = (
    "010000000100000000000000000000000000000000000000000000000000000000"
    "00000000ffffffff4d04ffff001d0104455468652054696d65732030332f4a616e2f"
    "32303039204368616e63656c6c6f72206f6e206272696e6b206f66207365636f6e64"
    "206261696c6f757420666f722062616e6b73ffffffff0100f2052a01000000434104"
    "678afdb0fe5548271967f1a67130b7105cd6a828e03909a67962e0ea1f61deb649f6"
    "bc3f4cef38c4f35504e51ec112de5c384df7ba0b8d578a4c702b6bf11d5fac00000000"
)
GENESIS_TXID_INTERNAL = "3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a"
GENESIS_BLOCK_HASH = "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"
GENESIS_NONCE = 2083236893
GENESIS_JOB = StratumJob(
    job_id="genesis",
    prevhash="00" * 32,
    coinb1=GENESIS_COINBASE_HEX,
    coinb2="",
    merkle_branch=(),
    version="00000001",
    nbits="1d00ffff",
    ntime="495fab29",
    clean_jobs=True,
)
GENESIS_SESSION = StratumSession(extranonce1=b"", extranonce2_size=0)


# ---------------------------------------------------------------------------
# Difficulty conversion
# ---------------------------------------------------------------------------


def test_difficulty_one_is_diff1_target():
    assert difficulty_to_target(1) == DIFF1_TARGET
    assert difficulty_to_target(1) == 0xFFFF << 208


def test_difficulty_scales_inverse():
    assert difficulty_to_target(2) == DIFF1_TARGET // 2
    assert difficulty_to_target(0.5) == DIFF1_TARGET * 2


def test_difficulty_rejects_non_positive():
    for bad in (0, -1, 0.0, float("nan") if False else -0.5):
        with pytest.raises(ValueError):
            difficulty_to_target(bad)


def test_difficulty_tiny_caps_at_uint256_max():
    assert difficulty_to_target(1e-30) == (1 << 256) - 1


# ---------------------------------------------------------------------------
# Header / merkle / coinbase assembly against genesis
# ---------------------------------------------------------------------------


def test_genesis_coinbase_hashes_to_txid():
    coinbase = build_coinbase(GENESIS_JOB, b"", GENESIS_SESSION)
    assert sha256d(coinbase).hex() == GENESIS_TXID_INTERNAL


def test_genesis_header_prefix_and_block_hash():
    prefix = build_header_prefix(GENESIS_JOB, b"", GENESIS_SESSION)
    assert len(prefix) == 76
    header = prefix + GENESIS_NONCE.to_bytes(4, "little")
    assert sha256d(header)[::-1].hex() == GENESIS_BLOCK_HASH


def test_genesis_block_satisfies_genesis_target():
    header = build_header(GENESIS_JOB, b"", GENESIS_SESSION, GENESIS_NONCE)
    digest = sha256d(header)
    assert int.from_bytes(digest, "little") <= DIFF1_TARGET


def test_merkle_root_with_branch():
    """Two-leaf tree: root = sha256d(h0 + h1)."""
    h0 = sha256d(b"tx-zero")
    h1 = sha256d(b"tx-one")
    assert merkle_root(h0, (h1.hex(),)) == sha256d(h0 + h1)


def test_coinbase_rejects_wrong_extranonce2_size():
    session = StratumSession(extranonce1=b"\x01", extranonce2_size=4)
    with pytest.raises(ValueError):
        build_coinbase(GENESIS_JOB, b"\x00" * 3, session)


def test_build_header_rejects_out_of_range_nonce():
    with pytest.raises(ValueError):
        build_header(GENESIS_JOB, b"", GENESIS_SESSION, 1 << 32)
    with pytest.raises(ValueError):
        build_header(GENESIS_JOB, b"", GENESIS_SESSION, -1)


def test_notify_requires_nine_params():
    with pytest.raises(ValueError):
        StratumJob.from_notify(["only", "three", "params"])


def test_prevhash_word_swap_matches_header_order():
    """Non-trivial prevhash must be per-word reversed into header order."""
    job = StratumJob(
        job_id="j",
        prevhash="00000000000000000024fb33264fbf933d77c94a16188a5b6027bf59bbfae3b7",
        coinb1="ff",
        coinb2="",
        merkle_branch=(),
        version="20000000",
        nbits="17034219",
        ntime="5f8a9b0c",
    )
    session = StratumSession(extranonce1=b"", extranonce2_size=0)
    prefix = build_header_prefix(job, b"", session)
    # Header bytes 4..36 = prevhash with each 4-byte word reversed
    raw = bytes.fromhex(job.prevhash)
    expected = b"".join(raw[i : i + 4][::-1] for i in range(0, 32, 4))
    assert prefix[4:36] == expected
    assert prefix[:4] == bytes.fromhex("20000000")[::-1]
    assert prefix[72:76] == bytes.fromhex("17034219")[::-1]


# ---------------------------------------------------------------------------
# Genesis nonce discovery through the existing CPU pipeline
# ---------------------------------------------------------------------------


def test_genesis_header_mined_by_existing_cpu_engine():
    """The pool-style header must be minable by chronus.execution.mining."""
    from chronus.execution.mining import search_nonce_range

    header = build_header(GENESIS_JOB, b"", GENESIS_SESSION, 0)
    result = search_nonce_range(
        header,
        GENESIS_NONCE - 500,
        GENESIS_NONCE + 500,
        DIFF1_TARGET,
        workers=1,
    )
    assert result["match_count"] >= 1
    found_nonces = {m["nonce"] for m in result["matches"]}
    assert GENESIS_NONCE in found_nonces


# ---------------------------------------------------------------------------
# Full client lifecycle against a fake in-process pool
# ---------------------------------------------------------------------------

_FAKE_NOTIFY = {
    "id": None,
    "method": "mining.notify",
    "params": [
        "job-7",
        "00" * 32,
        GENESIS_COINBASE_HEX,
        "",
        [],
        "00000001",
        "1d00ffff",
        "495fab29",
        True,
    ],
}


def _run_fake_pool_scenario():
    """Run client + fake pool in one event loop; returns captured submissions."""
    submissions = []

    async def scenario():
        async def handle(reader, writer):
            async for raw in reader:
                try:
                    message = json.loads(raw.decode().strip())
                except json.JSONDecodeError:
                    continue
                method = message.get("method")
                if method == "mining.subscribe":
                    response = {
                        "id": message["id"],
                        "result": [
                            [["mining.set_difficulty", "d"], ["mining.notify", "n"]],
                            "01020304",
                            4,
                        ],
                        "error": None,
                    }
                    writer.write((json.dumps(response) + "\n").encode())
                    writer.write(
                        b'{"id":null,"method":"mining.set_difficulty","params":[1e-12]}\n'
                    )
                    writer.write((json.dumps(_FAKE_NOTIFY) + "\n").encode())
                elif method == "mining.authorize":
                    ok = message["params"][0] == "user.worker"
                    writer.write(
                        (json.dumps({"id": message["id"], "result": ok, "error": None}) + "\n").encode()
                    )
                elif method == "mining.submit":
                    submissions.append(message["params"])
                    writer.write(
                        (json.dumps({"id": message["id"], "result": True, "error": None}) + "\n").encode()
                    )
                await writer.drain()

        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]

        client = StratumV1Client("127.0.0.1", port, "user.worker", "x")
        session = await client.connect()
        assert session.extranonce1 == bytes.fromhex("01020304")
        assert session.extranonce2_size == 4

        job, difficulty = await client.next_job()
        assert job.job_id == "job-7"
        assert difficulty == pytest.approx(1e-12)
        # Difficulty 1e-12 makes the target effectively unbounded: any
        # nonce is a valid share.
        target = difficulty_to_target(difficulty)
        assert target == (1 << 256) - 1

        extranonce2 = b"\x00" * session.extranonce2_size
        header = build_header(job, extranonce2, session, nonce=0)
        assert int.from_bytes(sha256d(header), "little") <= target

        accepted = await client.submit(job, extranonce2, nonce=0)
        assert accepted is True
        await client.close()
        # NB: not "async with server": on 3.12+ wait_closed() blocks until
        # the handler's own read finishes; asyncio.run teardown handles it.
        server.close()

    asyncio.run(scenario())
    return submissions


def test_stratum_client_full_lifecycle_against_fake_pool():
    submissions = _run_fake_pool_scenario()
    assert len(submissions) == 1
    username, job_id, en2, ntime, nonce_hex = submissions[0]
    assert username == "user.worker"
    assert job_id == "job-7"
    assert en2 == "00000000"
    assert ntime == "495fab29"
    assert nonce_hex == "00000000"


def test_stratum_client_rejects_bad_authorization():
    async def scenario():
        async def handle(reader, writer):
            async for raw in reader:
                message = json.loads(raw.decode().strip())
                if message.get("method") == "mining.subscribe":
                    writer.write(
                        b'{"id":%d,"result":[[],"aa",4],"error":null}\n' % message["id"]
                    )
                elif message.get("method") == "mining.authorize":
                    writer.write(
                        b'{"id":%d,"result":false,"error":null}\n' % message["id"]
                    )
                await writer.drain()

        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        client = StratumV1Client("127.0.0.1", port, "bad.user", "x")
        with pytest.raises(StratumError, match="authorize"):
            await client.connect()
        server.close()

    asyncio.run(scenario())


def test_stratum_client_constructor_validation():
    with pytest.raises(ValueError):
        StratumV1Client("", 3333, "u", "p")
    with pytest.raises(ValueError):
        StratumV1Client("pool.example.com", 0, "u", "p")
    with pytest.raises(ValueError):
        StratumV1Client("pool.example.com", 70000, "u", "p")
