"""Pool-only mining (ViaBTC, NiceHash, Braiins, CKPool): no bitcoind required.

The pool's own jobs are the chain evidence, each pool is reached with its own
worker credentials, and the low-profile rule — never mine directly on our
own block — holds on pool evidence alone.
"""

from __future__ import annotations

import asyncio
import secrets
import time
from types import SimpleNamespace

import pytest

import mining_runtime
from manifold_pool_coordinator import PoolEndpoint
from mla1517.mining.coordinator import IntelligentPoolCoordinator
from mla1517.mining.pool_chain import PoolChainObserver, bip34_height
from mla1517.mining.session import MiningSession
from mla1517.mining.stratum_adapter import stratum_prevhash
from test_agentic_voyages import (
    EASY_TARGET,
    FakeChain,
    FakePool,
    _connected,
    _job,
    _served,
    bip34_coinb1,
    parent_of_current_job,
    until,
)

BLOCK_NBITS = "2100ffff"  # network target ~2^256: a share is a block candidate (p ~ 0.99998)


def _stratum_prevhash_for(display_hash: str) -> str:
    """Encode a display block hash the way a pool sends it in mining.notify."""
    return stratum_prevhash(bytes.fromhex(display_hash)[::-1].hex()).hex()


def _pool_only_coordinator(endpoints, **kwargs) -> IntelligentPoolCoordinator:
    coord = IntelligentPoolCoordinator(
        endpoints,
        username="coordinator-default",
        password="x",
        submit_enabled=True,
        mining_session=MiningSession(cooldown_seconds=0),
        **kwargs,
    )
    coord.chain_observer = PoolChainObserver(lambda: coord.client)
    return coord


async def _poll(coord) -> bool:
    coord._last_chain_poll = 0.0
    return await coord.before_hardware_poll()


# ── chain evidence from pool jobs ────────────────────────────────────── #


def test_bip34_height_from_a_real_mainnet_coinbase_prefix():
    # Height 800000 is pushed as 03 00350c; 0x4b is the script length.
    coinb1 = "01000000" + "01" + "00" * 32 + "ffffffff" + "4b" + "0300350c" + "fabe6d6d"
    assert bip34_height(coinb1) == 800_000
    assert bip34_height(bip34_coinb1(915_123)) == 915_123
    assert bip34_height("01000000") is None
    assert bip34_height("not hex") is None


def test_no_job_or_no_height_fails_closed():
    observer = PoolChainObserver(lambda: None)
    with pytest.raises(RuntimeError, match="no pool job"):
        observer.tip()


async def _pool_tip():
    pool = FakePool(target=EASY_TARGET, job=_job("job-h", coinb1=bip34_coinb1(900_001)))
    server, port = await _served(pool)
    coord = _pool_only_coordinator([PoolEndpoint("127.0.0.1", port, "braiins")])
    try:
        await _connected(coord, "job-h")
        tip = coord.chain_observer.tip()
        assert tip == {"block_hash": parent_of_current_job(coord), "height": 900_000}
        assert coord.chain_observer.confirmed_height(tip["block_hash"]) == 900_000
        assert coord.evidence_snapshot()["chain_evidence"] == "pool_stratum"
    finally:
        await coord.client.close()
        server.close()
        await server.wait_closed()


def test_pool_job_is_the_chain_tip():
    asyncio.run(_pool_tip())


# ── share mining with no bitcoind ────────────────────────────────────── #


async def _shares_without_bitcoind():
    pool = FakePool(target=EASY_TARGET, job=_job("job-s", coinb1=bip34_coinb1(900_001)))
    server, port = await _served(pool)
    coord = _pool_only_coordinator([PoolEndpoint("127.0.0.1", port, "viabtc")])
    try:
        await _connected(coord, "job-s")
        for rounds in (1, 2, 3):
            assert await _poll(coord) is True
            assert await coord.search_current_job() is True
            assert len(pool.submits) == rounds
        assert coord.session.state == "SEARCHING"
    finally:
        await coord.client.close()
        server.close()
        await server.wait_closed()


def test_pool_only_share_mining_keeps_going():
    asyncio.run(_shares_without_bitcoind())


# ── low profile: never mine directly on our own block ────────────────── #


async def _low_profile():
    height = 900_001
    pool = FakePool(
        target=EASY_TARGET,
        job=_job("job-a", coinb1=bip34_coinb1(height), nbits=BLOCK_NBITS),
    )
    server, port = await _served(pool)
    coord = _pool_only_coordinator([PoolEndpoint("127.0.0.1", port, "ckpool")])
    try:
        await _connected(coord, "job-a")
        assert await _poll(coord) is True
        assert await coord.search_current_job() is True  # our block candidate, accepted
        our_block = coord.session.last_block_hash
        assert our_block is not None and coord.session.state == "WAITING_EXTERNAL"

        # The pool now builds on OUR block: the miner must stay dark.
        await pool.new_job(
            _job(
                "job-on-ours",
                prevhash=_stratum_prevhash_for(our_block),
                coinb1=bip34_coinb1(height + 1),
                nbits=BLOCK_NBITS,
            )
        )
        await until(lambda: coord.client.proof_adapter.current_job.job_id == "job-on-ours")
        assert await _poll(coord) is False
        assert await coord.search_current_job() is False
        assert len(pool.submits) == 1

        # Someone else's block lands on top: mining resumes on it.
        await pool.new_job(
            _job(
                "job-on-theirs",
                prevhash=secrets.token_hex(32),
                coinb1=bip34_coinb1(height + 2),
                nbits=BLOCK_NBITS,
            )
        )
        await until(lambda: coord.client.proof_adapter.current_job.job_id == "job-on-theirs")
        assert await _poll(coord) is True
        assert coord.session.state == "SEARCHING"
        assert await coord.search_current_job() is True
        assert len(pool.submits) == 2 and pool.submits[1][1] == "job-on-theirs"
    finally:
        await coord.client.close()
        server.close()
        await server.wait_closed()


def test_low_profile_rule_holds_on_pool_evidence_alone():
    asyncio.run(_low_profile())


# ── per-pool credentials through failover ────────────────────────────── #


async def _credentials():
    braiins = FakePool(target=EASY_TARGET, job=_job("job-b"), worker="account.rig1")
    ckpool = FakePool(target=EASY_TARGET, job=_job("job-c"), worker="bc1qexampleaddress")
    server_b, port_b = await _served(braiins)
    server_c, port_c = await _served(ckpool)
    chain = FakeChain()
    coord = IntelligentPoolCoordinator(
        [
            PoolEndpoint("127.0.0.1", port_b, "braiins", username="account.rig1"),
            PoolEndpoint("127.0.0.1", port_c, "ckpool", username="bc1qexampleaddress"),
        ],
        username="coordinator-default",
        password="x",
        submit_enabled=True,
        mining_session=MiningSession(cooldown_seconds=0),
        chain_observer=chain,
    )
    try:
        await _connected(coord, "job-b")
        chain.block_hash = parent_of_current_job(coord)
        assert await coord.search_current_job() is True
        assert braiins.submits[-1][0] == "account.rig1"

        assert await coord.force_failover("secondary")
        await _connected(coord, "job-c")
        chain.block_hash = parent_of_current_job(coord)
        assert await coord.search_current_job() is True
        assert ckpool.submits[-1][0] == "bc1qexampleaddress"
        assert "mining.authorize:coordinator-default" not in braiins.methods + ckpool.methods
    finally:
        if coord.client:
            await coord.client.close()
        for server in (server_b, server_c):
            server.close()
            await server.wait_closed()


def test_each_pool_is_used_with_its_own_worker():
    asyncio.run(_credentials())


def test_endpoint_password_never_appears_in_repr():
    endpoint = PoolEndpoint("h", 1, "n", username="u", password="s3cret")
    assert "s3cret" not in repr(endpoint)


# ── client.reconnect and extranonce subscription ─────────────────────── #


async def _reconnect():
    pool = FakePool(target=EASY_TARGET, job=_job("job-r"))
    server, port = await _served(pool)
    coord = _pool_only_coordinator([PoolEndpoint("127.0.0.1", port, "nicehash")])
    try:
        await _connected(coord, "job-r")
        await pool.push("client.reconnect", ["elsewhere.invalid", 3333, 0])
        await until(lambda: not coord.client.connected, what="session end")
        await coord.client.close()
        coord.client = None
        await _connected(coord, "job-r")
        assert pool.connections == 2
        assert (coord.client.endpoint.host, coord.client.endpoint.port) == ("127.0.0.1", port)
    finally:
        await coord.client.close()
        server.close()
        await server.wait_closed()


def test_client_reconnect_returns_to_the_configured_pool_only():
    asyncio.run(_reconnect())


async def _extranonce(flag: bool, answer: bool) -> tuple[list[str], float]:
    pool = FakePool(target=EASY_TARGET, job=_job("job-x"))
    pool.answer_extranonce_subscribe = answer
    server, port = await _served(pool)
    coord = _pool_only_coordinator(
        [PoolEndpoint("127.0.0.1", port, "nicehash", extranonce_subscribe=flag)]
    )
    started = time.monotonic()
    try:
        await _connected(coord, "job-x")
        return list(pool.methods), time.monotonic() - started
    finally:
        await coord.client.close()
        server.close()
        await server.wait_closed()


def test_extranonce_subscribe_only_where_configured_and_never_blocks():
    methods, _ = asyncio.run(_extranonce(True, True))
    assert "mining.extranonce.subscribe" in methods
    methods, _ = asyncio.run(_extranonce(False, True))
    assert "mining.extranonce.subscribe" not in methods
    methods, elapsed = asyncio.run(_extranonce(True, False))
    assert "mining.extranonce.subscribe" in methods and elapsed < 10


# ── runtime pool catalog ─────────────────────────────────────────────── #

ARGS = SimpleNamespace(user="cli.worker", password="x", tls=False)


def test_operator_config_drives_primary_failover_and_credentials():
    config = {
        "pools": [
            {"endpoint": "btc.viabtc.io:3333", "worker": "acct.v1", "password": "p1"},
            {
                "endpoint": "test.nicehash.com:9200",
                "worker": "bc1qnicehash.rig",
                "password": "p2",
                "enabled": True,
            },
        ]
    }
    first, second = mining_runtime.pool_endpoints(ARGS, config)
    assert (first.name, first.username, first.extranonce_subscribe) == (
        "nicehash",
        "bc1qnicehash.rig",
        True,
    )
    assert (second.name, second.username, second.extranonce_subscribe) == (
        "viabtc",
        "acct.v1",
        False,
    )


def test_unlisted_pools_are_refused_unless_overridden(monkeypatch):
    config = {"pools": [{"endpoint": "pool.example.org:3333", "worker": "w", "password": "x"}]}
    with pytest.raises(SystemExit, match="not one of the configured mining pools"):
        mining_runtime.pool_endpoints(ARGS, config)
    monkeypatch.setenv("PYTHIA_ALLOW_UNLISTED_POOLS", "1")
    assert mining_runtime.pool_endpoints(ARGS, config)[0].host == "pool.example.org"


def test_environment_catalog_for_the_four_pools(monkeypatch):
    for name in ("BRAIINS", "VIABTC", "NICEHASH", "CKPOOL"):
        for suffix in ("ENDPOINT", "USER", "PASSWORD"):
            monkeypatch.delenv(f"MLA1517_{name}_{suffix}", raising=False)
    monkeypatch.setenv("PYTHIA_POOLS", "braiins,ckpool")
    monkeypatch.setenv("PYTHIA_POOL_PROFILE", "ckpool")
    monkeypatch.setenv("MLA1517_CKPOOL_USER", "bc1qsolo")
    ckpool, braiins = mining_runtime.pool_endpoints(ARGS, {"pools": []})
    assert (ckpool.host, ckpool.port, ckpool.username) == ("solo.ckpool.org", 3333, "bc1qsolo")
    assert (braiins.host, braiins.username) == ("stratum.braiins.com", "cli.worker")
    monkeypatch.setenv("PYTHIA_POOLS", "nicehash")
    with pytest.raises(SystemExit, match="MLA1517_NICEHASH_ENDPOINT"):
        mining_runtime.pool_endpoints(ARGS, {"pools": []})


# ── device-sized windows (pool difficulty needs the throughput) ──────── #


class _FakeDevice:
    backend = "opencl:gpu"
    device = "fake"
    vendor = None
    grind_batch = 1_048_575
    m32_launch = 16_777_152
    m32_window_max = 134_217_600
    launches = 0
    kernel_ms = 0.0
    k_gold = k_range = k_m32 = object()
    fallback_reason = None


def test_gpu_windows_are_the_largest_lucas_number_that_fits_a_launch():
    from lucas.core import lucas

    gpu = _pool_only_coordinator([PoolEndpoint("h", 1, "braiins")], execution_hasher=_FakeDevice())
    window = gpu._next_window()
    assert window % 32 == 0 and window <= _FakeDevice.m32_launch
    assert window == lucas(34) - lucas(34) % 32  # L34 = 12,752,043 <= 16,777,152 < L35
    cpu = _pool_only_coordinator([PoolEndpoint("h", 1, "braiins")])
    assert cpu._next_window() == lucas(cpu.session.rung) - lucas(cpu.session.rung) % 32


def test_device_sized_plan_falls_back_to_cpu_without_breaking_the_rung_gate():

    from mla1517.mining.search_plan import SearchPlan

    device = _FakeDevice()
    device.k_m32 = None  # kernel missing: the router falls back to the CPU sweep
    coord = _pool_only_coordinator([PoolEndpoint("h", 1, "braiins")], execution_hasher=device)
    plan = SearchPlan(
        job_fingerprint="fp",
        pool_session_id="s",
        generation=1,
        base_step=0,
        window=32 * 64,
        extranonce2="00",
        lane_order=tuple(range(32)),
        preferred_face=0,
        dispatch_breadth=1,
        executor_route="opencl_m32",
        policy_id="p",
        evidence_refs={},
        created_at=1.0,
    )
    record, candidate = coord._router_for(plan).execute_plan(
        plan, bytes(80), (1).to_bytes(32, "little")
    )
    assert record.executed_route == "cpu_reference" and candidate is None
    assert record.hash_count == plan.window == record.completed_work_items
