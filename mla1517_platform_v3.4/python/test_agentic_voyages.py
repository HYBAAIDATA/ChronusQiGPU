"""Production voyages: the real coordinator and Stratum client over TCP.

A scripted local pool stands in for the network and a fake chain observer
for bitcoind. Everything else is production code: StratumClient, proof
adapter, StratumRuntimeState, MiningSession, IntelligentPoolCoordinator,
AgenticMiningController, the lease ledger and the SHA256d solver.
No hardware and no live pool are involved; nothing here is hardware evidence.
"""

from __future__ import annotations

import asyncio
import json
import secrets

import pytest

from manifold_pool_coordinator import PoolEndpoint
from mla1517.mining.coordinator import IntelligentPoolCoordinator
from mla1517.mining.session import MiningSession
from mla1517.mining.search_plan import LeaseState, PlanSource, PoolOutcome
from mla1517.mining.tuning_gate import TuningGate

EASY_TARGET = "ff" * 32  # every nonce meets it: a share on the first hash
HARD_TARGET = "00" * 31 + "01"  # no nonce in any test window meets it


def _job(
    job_id: str,
    *,
    clean: bool = True,
    prevhash: str | None = None,
    coinb1: str = "01000000",
    nbits: str = "1d00ffff",
) -> list:
    return [
        job_id,
        prevhash or secrets.token_hex(32),
        coinb1,
        "ffffffff",
        [],
        "20000000",
        nbits,
        "65abcdef",
        clean,
    ]


def bip34_coinb1(height: int) -> str:
    """Legacy coinbase prefix up to the extranonce, carrying a BIP34 height."""
    push = height.to_bytes(3, "little")
    script_prefix = bytes([len(push)]) + push
    return (
        "02000000"
        + "01"
        + "00" * 32
        + "ffffffff"
        + f"{len(script_prefix) + 8:02x}"
        + script_prefix.hex()
    )


def _line(payload: dict) -> bytes:
    return (json.dumps(payload, separators=(",", ":")) + "\n").encode()


class FakePool:
    """Scripted Stratum V1 pool; responses are literal and never inferred."""

    def __init__(self, *, target: str, job: list, worker: str | None = None) -> None:
        self.target = target
        self.job = job
        self.worker = worker  # when set, only this worker is authorized
        self.submit_policy = "accept"  # accept | reject | drop
        self.answer_extranonce_subscribe = True
        self.submits: list[list] = []
        self.methods: list[str] = []
        self.connections = 0
        self._writer: asyncio.StreamWriter | None = None

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.connections += 1
        self._writer = writer
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
            self.methods.append("mining.authorize:" + str(authorize["params"][0]))
            allowed = self.worker is None or authorize["params"][0] == self.worker
            writer.write(_line({"id": authorize["id"], "result": allowed, "error": None}))
            if not allowed:
                await writer.drain()
                return
            writer.write(
                _line({"id": None, "method": "mining.set_target", "params": [self.target]})
            )
            writer.write(_line({"id": None, "method": "mining.notify", "params": self.job}))
            await writer.drain()
            while line := await reader.readline():
                message = json.loads(line)
                self.methods.append(str(message.get("method")))
                if message.get("method") == "mining.extranonce.subscribe":
                    if self.answer_extranonce_subscribe:
                        writer.write(_line({"id": message["id"], "result": True, "error": None}))
                        await writer.drain()
                    continue
                if message.get("method") != "mining.submit":
                    continue
                self.submits.append(message["params"])
                if self.submit_policy == "drop":
                    return
                accepted = self.submit_policy == "accept"
                writer.write(_line({"id": message["id"], "result": accepted, "error": None}))
                await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        finally:
            writer.close()

    async def push(self, method: str, params: list) -> None:
        assert self._writer is not None
        self._writer.write(_line({"id": None, "method": method, "params": params}))
        await self._writer.drain()

    async def new_job(self, job: list, *, target: str | None = None) -> None:
        self.job = job
        if target is not None:
            self.target = target
            await self.push("mining.set_target", [target])
        await self.push("mining.notify", job)


class FakeChain:
    """Verified-tip stand-in for BitcoinChainObserver."""

    def __init__(self) -> None:
        self.block_hash = "00" * 32
        self.height = 800_000
        self.known: dict[str, int] = {}

    def advance_to(self, block_hash: str) -> None:
        self.height += 1
        self.block_hash = block_hash
        self.known[block_hash] = self.height

    def tip(self) -> dict:
        return {"block_hash": self.block_hash, "height": self.height}

    def confirmed_height(self, block_hash: str) -> int | None:
        return self.known.get(block_hash)


class FakeBridge:
    """MMIO stand-in for run_hardware_loop; it never produces vault records."""

    def __init__(self) -> None:
        self.running = False

    def set_difficulty_mask(self, mask: int) -> None: ...

    def set_base_step(self, step: int) -> None: ...

    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

    def last_error(self) -> int:
        return 0

    def poll_vault(self, poll_ms: int):
        import time

        time.sleep(poll_ms / 1000)
        return None


async def until(predicate, *, timeout: float = 5.0, what: str = "condition") -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not predicate():
        if loop.time() > deadline:
            raise AssertionError(f"timed out waiting for {what}")
        await asyncio.sleep(0.01)


def parent_of_current_job(coord: IntelligentPoolCoordinator) -> str:
    adapter = coord.client.proof_adapter
    job = adapter.current_job
    return adapter.build_header(job.job_id, "00000000", job.ntime, 0)[4:36][::-1].hex()


def coordinator(port: int, chain: FakeChain, session: MiningSession | None = None):
    return IntelligentPoolCoordinator(
        [PoolEndpoint("127.0.0.1", port, "fake-pool")],
        username="PYTHIA.001",
        password="x",
        submit_enabled=True,
        mining_session=session or MiningSession(cooldown_seconds=0),
        chain_observer=chain,
    )


async def _served(pool: FakePool):
    server = await asyncio.start_server(pool.handle, "127.0.0.1", 0)
    return server, server.sockets[0].getsockname()[1]


async def _connected(coord: IntelligentPoolCoordinator, job_id: str) -> None:
    await coord.connect_with_failover()
    await until(
        lambda: coord._resolve_work_identity()[0] is not None
        and coord._resolve_work_identity()[0].job_id == job_id,
        what=f"Stratum identity for {job_id}",
    )


async def _advance_chain_and_resume(coord, pool: FakePool, chain: FakeChain, job_id: str) -> None:
    """A new block: the pool issues a clean job on it and the chain tip moves."""
    await pool.new_job(_job(job_id))
    await until(lambda: coord.client.proof_adapter.current_job.job_id == job_id, what=job_id)
    chain.advance_to(parent_of_current_job(coord))
    coord._last_chain_poll = 0.0
    for _ in range(3):
        await coord.before_hardware_poll()
        coord._last_chain_poll = 0.0


# ── Voyage A — normal mining continuity ──────────────────────────────── #


async def _voyage_a():
    pool = FakePool(target=HARD_TARGET, job=_job("job-a"))
    server, port = await _served(pool)
    chain = FakeChain()
    coord = coordinator(port, chain)
    try:
        await _connected(coord, "job-a")
        work_a = coord.agentic.current_identity()
        assert work_a.clean_jobs and work_a.generation >= 1

        assert coord._fill_precompute_queue() == 2
        a1, a2 = list(coord.agentic._queue.queue)
        assert {a1.generation, a2.generation} == {work_a.generation}
        assert a1.base_step + 32 * -(-a1.window // 32) <= a2.base_step  # disjoint leases

        assert await coord.search_current_job() is False  # hard target: no share
        executed = coord.last_execution
        assert executed["plan_source"] == PlanSource.AGENTIC_PRECOMPUTED.value
        assert executed["plan_id"] == a1.plan_id
        assert executed["pool_outcome"] == PoolOutcome.NO_CANDIDATE.value
        assert coord.agentic._leases.get(a1.plan_id).state is LeaseState.COMPLETE
        assert pool.submits == []

        await pool.new_job(_job("job-b"), target=None)
        await until(lambda: coord.agentic.current_identity().job_id == "job-b", what="job-b")
        assert coord.agentic._leases.get(a2.plan_id).state is LeaseState.INVALIDATED
        assert all(p.job_fingerprint != a2.job_fingerprint for p in coord.agentic._queue.queue)
        assert coord.agentic.submit_plan(a2) is False
        assert coord.agentic.telemetry.clean_job_invalidations >= 2

        await pool.push("mining.set_target", [EASY_TARGET])
        await until(
            lambda: coord.agentic.current_identity().target_generation > work_a.target_generation,
            what="easy target",
        )
        chain.block_hash = parent_of_current_job(coord)
        coord._fill_precompute_queue()
        b1 = list(coord.agentic._queue.queue)[0]
        assert b1.generation == coord.agentic.current_identity().generation

        assert await coord.search_current_job() is True
        record = coord.agentic.telemetry.last_outcome
        assert record["plan_id"] == b1.plan_id
        assert record["plan_source"] == PlanSource.AGENTIC_PRECOMPUTED.value
        assert record["pool_outcome"] == PoolOutcome.ACCEPTED.value
        assert record["pool_accepted"] == 1
        assert len(pool.submits) == 1 and pool.submits[0][1] == "job-b"
        assert coord.agentic.telemetry.learning_update_applied
        assert list(coord.mining_intelligence.history)[-1]["accepted"] is True
        assert coord.client.status_snapshot()["counters"]["accepted"] == 1

        # Continuity: one accepted share does not park the miner.
        assert coord.session.state == "SEARCHING"
        assert await coord.before_hardware_poll() is True
        assert await coord.search_current_job() is True
        assert len(pool.submits) == 2
        assert pool.submits[0][1:] != pool.submits[1][1:]  # distinct leased work

        # And it keeps mining across the next block's clean job.
        await _advance_chain_and_resume(coord, pool, chain, "job-c")
        assert coord.session.state == "SEARCHING"
        assert await coord.search_current_job() is True
        assert coord.last_execution["generation"] == coord.agentic.current_identity().generation
        assert len(pool.submits) == 3 and pool.submits[2][1] == "job-c"
        return coord
    finally:
        await coord.client.close() if coord.client else None
        server.close()
        await server.wait_closed()


def test_voyage_a_normal_mining_continuity():
    asyncio.run(_voyage_a())


async def _share_then_keep_mining(policy: str):
    pool = FakePool(target=EASY_TARGET, job=_job("job-a"))
    pool.submit_policy = policy
    server, port = await _served(pool)
    chain = FakeChain()
    coord = coordinator(port, chain)
    bridge = FakeBridge()
    bridge.running = True
    coord._bridge = bridge
    expected = PoolOutcome.ACCEPTED if policy == "accept" else PoolOutcome.REJECTED
    try:
        await _connected(coord, "job-a")
        chain.block_hash = parent_of_current_job(coord)
        for round_number in (1, 2, 3):
            await coord.search_current_job()
            execution = coord.last_execution
            assert execution["pool_outcome"] == expected.value
            assert coord.session.state == "SEARCHING"
            assert bridge.running, "device paused for the submit must be resumed"
            assert await coord.before_hardware_poll() is True
            assert len(pool.submits) == round_number
            # Correlation spine: the durable share record names this execution's submission.
            assert coord.session.last_share["submission_id"] == execution["submission_id"]
            assert coord.session.last_share["outcome"] is (policy == "accept")
            assert execution["candidate_id"] and execution["execution_id"]
        assert coord.session.cycles == 0 and coord.session.history == ["SEARCHING"]
        assert len({tuple(p[1:]) for p in pool.submits}) == 3
        assert list(coord.mining_intelligence.history)[-1]["accepted"] is (policy == "accept")
    finally:
        await coord.client.close()
        server.close()
        await server.wait_closed()


@pytest.mark.parametrize("policy", ["accept", "reject"])
def test_voyage_a_resolved_share_does_not_park_miner(policy):
    asyncio.run(_share_then_keep_mining(policy))


# ── Voyage B — unknown submission ────────────────────────────────────── #


async def _voyage_b(tmp_path):
    pool = FakePool(target=EASY_TARGET, job=_job("job-a"))
    pool.submit_policy = "drop"
    server, port = await _served(pool)
    chain = FakeChain()
    session = MiningSession(tmp_path / "session.json", cooldown_seconds=0)
    coord = coordinator(port, chain, session)
    try:
        await _connected(coord, "job-a")
        chain.block_hash = parent_of_current_job(coord)
        old_client = coord.client
        old_session_id = coord.agentic.current_identity().pool_session_id
        chooser_history = len(coord.mining_intelligence.history)

        with pytest.raises(ConnectionError):
            await coord.search_current_job()

        assert len(pool.submits) == 1
        record = coord.agentic.telemetry.last_outcome
        assert record["pool_outcome"] == PoolOutcome.OUTCOME_UNKNOWN.value
        assert record["pool_accepted"] == 0 and record["pool_rejected"] == 0
        assert not coord.agentic.telemetry.learning_update_applied
        assert len(coord.mining_intelligence.history) == chooser_history
        assert old_client.status_snapshot()["submission"]["state"] == "OUTCOME_UNKNOWN"
        assert coord.agentic.current_identity() is None  # dead session is not work

        # The share is logged as unknown, durably, and the miner is not parked.
        lost = coord.last_execution
        durable = json.loads((tmp_path / "session.json").read_text())
        assert durable["state"] == "SEARCHING" and durable["pending"] is None
        assert durable["share_log"][-1]["outcome"] is None
        assert durable["share_log"][-1]["submission_id"] == lost["submission_id"]
        assert coord.session.cycles == 0

        # Recovery: reconnect exactly as the hardware loop does.
        await old_client.close()
        coord.client = None
        pool.submit_policy = "accept"
        await _connected(coord, "job-a")
        chain.block_hash = parent_of_current_job(coord)
        assert coord.agentic.current_identity().pool_session_id != old_session_id

        # Never blindly re-submit the lost share, not even after a reconnect.
        _worker, job_id, extranonce2, ntime, nonce = pool.submits[0]
        assert (
            await coord.submit_candidate(
                job_id=job_id, extranonce2=extranonce2, ntime=ntime, nonce=nonce
            )
            is False
        )
        assert len(pool.submits) == 1

        # Mining continues and new, distinct shares reach the pool.
        accepted = [await coord.search_current_job() for _ in range(3)]
        assert accepted.count(True) >= 2
        assert len(pool.submits) == 1 + accepted.count(True)
        assert len({tuple(p[1:]) for p in pool.submits}) == len(pool.submits)
        coord.session.close()
        reopened = MiningSession(tmp_path / "session.json")
        assert reopened.state == "SEARCHING"
        assert any(entry["outcome"] is None for entry in reopened.share_log)
        assert reopened.already_submitted(durable["share_log"][0]["block_hash"])
        reopened.close()
    finally:
        if coord.client:
            await coord.client.close()
        server.close()
        await server.wait_closed()


def test_voyage_b_unknown_submission(tmp_path):
    asyncio.run(_voyage_b(tmp_path))


# ── Voyage C — recovery while precomputing ───────────────────────────── #


async def _voyage_c():
    pool = FakePool(target=HARD_TARGET, job=_job("job-a"))
    server, port = await _served(pool)
    coord = coordinator(port, FakeChain())
    coord.agentic = type(coord.agentic)(queue_depth=4, initial_lookahead=3)
    coord.tuning = TuningGate(
        latency_bound_ms=10_000.0,
        thermal_limit_c=85.0,
        temperature_probe=lambda: 40.0,
        power_probe=lambda: 5.0,
    )
    try:
        await _connected(coord, "job-a")
        assert coord._fill_precompute_queue() == 3
        a1 = coord.agentic.consume_plan()
        lease_a1 = coord.agentic.begin_execution(a1)
        a2, a3 = list(coord.agentic._queue.queue)

        coord.apply_salamander_mode("RECOVERING")
        assert coord.agentic.queue_depth() == 0
        for queued in (a2, a3):
            assert coord.agentic._leases.get(queued.plan_id).state is LeaseState.INVALIDATED
        assert coord.agentic._leases.get(a1.plan_id).state is LeaseState.EXECUTING
        assert coord._fill_precompute_queue() == 0
        assert coord.agentic.submit_plan(a2) is False

        healer_view = coord.tuning.evaluate(
            current_window=40,
            max_window=199,
            kernel_latency_ms=1.0,
            hashes_computed=40,
            elapsed_seconds=0.001,
            new_job_observed=False,
            stratum_state="READY",
            recovery_active=coord.agentic.is_recovery_active(),
        )
        assert healer_view.action == "HOLD" and "recovery" in healer_view.reason

        assert coord.agentic.finish_execution(lease_a1.lease_id, scanned=True)

        # Actuator ACK + healthy post-observation are Salamander's; it then reports NORMAL.
        coord.apply_salamander_mode("NORMAL")
        assert coord.agentic.admission_block_reason() == "REVALIDATION_REQUIRED"
        assert coord.agentic.plans_needed() == 0
        resumed = coord._fill_precompute_queue()
        assert resumed > 0
        assert coord.agentic.admission_block_reason() is None
        fresh = list(coord.agentic._queue.queue)
        assert all(p.base_step >= a3.base_step + a3.window for p in fresh)

        optimiser_view = coord.tuning.evaluate(
            current_window=40,
            max_window=199,
            kernel_latency_ms=1.0,
            hashes_computed=40,
            elapsed_seconds=0.001,
            new_job_observed=False,
            stratum_state="READY",
            recovery_active=coord.agentic.is_recovery_active(),
        )
        assert optimiser_view.action == "SCALE_UP"
        assert optimiser_view.workgroup == {
            "requested": optimiser_view.workgroup["requested"],
            "supported": False,
            "executed": False,
        }
        assert optimiser_view.improvement_claimed is False

        assert await coord.search_current_job() is False
        assert coord.last_execution["plan_source"] == PlanSource.AGENTIC_PRECOMPUTED.value
    finally:
        await coord.client.close()
        server.close()
        await server.wait_closed()


def test_voyage_c_recovery_while_precomputing():
    asyncio.run(_voyage_c())


def test_backpressure_and_salamander_both_hold_the_gate():
    coord = coordinator(1, FakeChain())
    coord._recovery_backpressure = True
    coord.apply_salamander_mode("NORMAL")
    assert coord.agentic.is_recovery_active()
    coord._recovery_backpressure = False
    coord.apply_salamander_mode("FREEZE_SPECULATION")
    assert coord.agentic.is_recovery_active()
    coord.apply_salamander_mode("DE_RATE")
    assert not coord.agentic.is_recovery_active()
    with pytest.raises(ValueError):
        coord.apply_salamander_mode("PANIC")


def test_missing_measurements_hold_the_tuner():
    decision = TuningGate().evaluate(
        current_window=40,
        max_window=199,
        kernel_latency_ms=1.0,
        hashes_computed=40,
        elapsed_seconds=0.001,
        new_job_observed=False,
        stratum_state="READY",
        recovery_active=False,
    )
    assert decision.action == "HOLD"
    assert set(decision.missing) >= {"kernel_latency_bound_ms", "temperature_c", "power_w"}
    assert decision.next_window == 40


# ── Voyage D — restart ───────────────────────────────────────────────── #


async def _run_loop(coord: IntelligentPoolCoordinator) -> asyncio.Task:
    return asyncio.create_task(
        coord.run_hardware_loop(FakeBridge(), difficulty_mask=0x3F, base_step=0, poll_ms=5)
    )


async def _stop(task: asyncio.Task) -> None:
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def _voyage_d(tmp_path):
    state_path = str(tmp_path / "agentic_policy.json")
    session_path = tmp_path / "session.json"
    pool = FakePool(target=EASY_TARGET, job=_job("job-a"))
    server, port = await _served(pool)
    chain = FakeChain()
    try:
        # --- run 1: learn from a literal pool outcome, then shut down ---
        first = coordinator(port, chain, MiningSession(session_path, cooldown_seconds=0))
        first.set_agentic_state_path(state_path)
        task = await _run_loop(first)
        await until(lambda: first._resolve_work_identity()[0] is not None, what="run-1 work")
        chain.block_hash = parent_of_current_job(first)
        first._fill_precompute_queue()
        assert await first.search_current_job() is True
        old_session = first.agentic.current_identity().pool_session_id
        old_plans = list(first.agentic._queue.queue)
        old_ids = [p.plan_id for p in old_plans] + [first.last_execution["plan_id"]]
        await _stop(task)
        first.session.close()
        saved = open(state_path, encoding="utf-8").read()
        assert "true" in saved
        for secret in [old_session, *old_ids]:
            assert secret not in saved

        # --- run 2: restart restores learning, never work ---
        second = coordinator(port, chain, MiningSession(session_path, cooldown_seconds=0))
        second.set_agentic_state_path(state_path)
        assert second.agentic._lead_history == {}
        task = await _run_loop(second)
        await until(lambda: second.agentic._lead_history, what="history restored")
        assert list(second.agentic._lead_history.values())[0][-1] is True
        await until(lambda: second.agentic.current_identity() is not None, what="fresh identity")
        fresh = second.agentic.current_identity()
        assert fresh.pool_session_id != old_session
        for plan in old_plans:
            assert not plan.is_valid_for(fresh)
            assert second.agentic.submit_plan(plan) is False
        for lease_id in old_ids:
            assert second.agentic._leases.get(lease_id) is None or (
                second.agentic._leases.get(lease_id).state is LeaseState.INVALIDATED
            )
        # The resolved share from run 1 survived restart as durable evidence only.
        assert second.session.state == "SEARCHING"
        assert second.session.last_share["outcome"] is True
        await _advance_chain_and_resume(second, pool, chain, "job-after-restart")
        await until(lambda: second.session.state == "SEARCHING", what="lifecycle resume")
        assert await second.search_current_job() is True
        assert second.last_execution["generation"] == second.agentic.current_identity().generation
        await _stop(task)
        second.session.close()

        # --- run 3: corrupted policy state → clean baseline, still mines ---
        with open(state_path, "w", encoding="utf-8") as stream:
            stream.write('{"schema_version": 2, "body": {"historical_epoch": 9')
        third = coordinator(port, chain)
        third.set_agentic_state_path(state_path)
        task = await _run_loop(third)
        await until(lambda: third.agentic.current_identity() is not None, what="run-3 identity")
        assert third.agentic._lead_history == {}
        assert third.agentic.snapshot()["historical_binding_epoch"] == 0
        chain.block_hash = parent_of_current_job(third)
        assert await third.search_current_job() is True
        await _stop(task)
    finally:
        server.close()
        await server.wait_closed()


def test_voyage_d_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("MLA1517_COORDINATOR_CONTROL_SOCKET", str(tmp_path / "ctl.sock"))
    monkeypatch.delenv("MLA1517_TELEMETRY_PATH", raising=False)
    monkeypatch.delenv("MLA1517_PRIME_DB_RING", raising=False)
    asyncio.run(_voyage_d(tmp_path))
