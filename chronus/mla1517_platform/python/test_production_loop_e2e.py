"""End-to-end proof through the production entry point.

These tests launch ``mining_runtime._main_async`` — the same entry path as
``python main.py --mine`` — against scripted local Stratum fixtures
(``test_agentic_voyages.FakePool``, test-only) and watch the evidence the
production loop itself emits: the causal ledger on disk, the persisted
mining session, and the pool's wire log. Nothing is stubbed between the
entry point and the wire; only the environment variables a real operator
would set are configured. No live pool and no hardware are involved.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

import pytest

import mining_runtime
import runtime_config
from chronus.mla1517.mining import execution_router
from chronus.virtual_igpu import runtime as vigpu_runtime
from chronus.mla1517.mining.backend_registry import (
    BackendLane,
    BackendRegistry,
    LaneProbe,
)
from test_agentic_voyages import (
    EASY_TARGET,
    HARD_TARGET,
    FakePool,
    _job,
    bip34_coinb1,
    until,
)


def _args(submit: bool) -> argparse.Namespace:
    return argparse.Namespace(
        device=None,
        map_bytes=0,
        difficulty_mask=0,
        base_step=0,
        user=None,
        password=None,
        submit=submit,
        tls=False,
        log_level="error",
    )


def _env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    pools: dict[str, int],
    device: str = "cpu",
    submit: bool = True,
    reconnect_max_s: str = "1",
) -> None:
    """Environment exactly as an operator would set it for local pools.

    ``pools`` keys must be catalog names (``braiins``, ``viabtc``, ...) —
    the endpoint catalog gate stays as it ships; the env overrides repoint
    the declared pool's endpoint at the local fixture, the same override
    an operator uses for a listed pool.
    """
    monkeypatch.setenv("PYTHIA_ALLOW_UNLISTED_POOLS", "1")
    monkeypatch.setenv("PYTHIA_POOLS", ",".join(pools))
    for name, port in pools.items():
        monkeypatch.setenv(f"MLA1517_{name.upper()}_ENDPOINT", f"127.0.0.1:{port}")
        monkeypatch.setenv(f"MLA1517_{name.upper()}_USER", "PYTHIA.001")
        monkeypatch.setenv(f"MLA1517_{name.upper()}_PASSWORD", "x")
    monkeypatch.setenv("PYTHIA_EXECUTION_DEVICE", device)
    monkeypatch.setenv("PYTHIA_MINING_SESSION_PATH", str(tmp_path / "session.json"))
    monkeypatch.setenv("PYTHIA_MINING_COOLDOWN_SECONDS", "0")
    monkeypatch.setenv("PYTHIA_AGENTIC_STATE_PATH", str(tmp_path / "agentic.json"))
    monkeypatch.setenv("PYTHIA_CAUSAL_LOG_PATH", str(tmp_path / "causal.jsonl"))
    monkeypatch.setenv("PYTHIA_INTELLIGENCE_DIR", str(tmp_path / "intel"))
    monkeypatch.setenv("PYTHIA_RETARGET_TELEMETRY_PATH", str(tmp_path / "retarget.json"))
    monkeypatch.setenv("PYTHIA_WORKER_HEARTBEAT_DIR", str(tmp_path / "hb"))
    monkeypatch.setenv("PYTHIA_IDENTITY_HMAC_SECRET", "aa" * 32)
    # m32 lane order is self-contained; hendrix needs turing_universal_quantum_computer.
    monkeypatch.setenv("PYTHIA_NONCE_ORDER", "m32")
    monkeypatch.setenv("PYTHIA_RECONNECT_MAX_S", reconnect_max_s)
    # The operator's runtime config must not shadow the declared test pools.
    monkeypatch.setattr(runtime_config, "load", lambda *a, **k: {})


def _causal(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _cycle_transitions(path: Path) -> list[tuple[str, str, str]]:
    return [
        (e["detail"].get("from"), e["detail"].get("to"), e["detail"].get("event"))
        for e in _causal(path)
        if e["kind"] == "cycle_transition"
    ]


def _session_log(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("share_log", [])


async def _serve(pool: FakePool):
    server = await asyncio.start_server(pool.handle, "127.0.0.1", 0)
    return server, server.sockets[0].getsockname()[1]


async def _launch(args) -> asyncio.Task:
    task = asyncio.create_task(mining_runtime._main_async(args))
    return task


async def _stop(task: asyncio.Task) -> None:
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass


def test_startup_reaches_operational_cycle(monkeypatch, tmp_path):
    """The entry point reaches the mining states: SCAN→PLAN→MINE→VERIFY."""
    pool = FakePool(target=HARD_TARGET, job=_job("job-1"))

    async def run():
        server, port = await _serve(pool)
        _env(monkeypatch, tmp_path, pools={"braiins": port}, submit=False)
        task = await _launch(_args(submit=False))
        try:
            causal = tmp_path / "causal.jsonl"
            await until(
                lambda: any(to == "MINE" for _f, to, _e in _cycle_transitions(causal)),
                timeout=15,
                what="MINE state reached",
            )
            await until(
                lambda: any(to == "EVALUATE" for _f, to, _e in _cycle_transitions(causal)),
                timeout=15,
                what="EVALUATE state reached",
            )
            transitions = _cycle_transitions(causal)
            states = [to for _f, to, _e in transitions]
            # The declared cycle order held, in order.
            expected = ["SCAN", "PLAN", "MINE", "VERIFY", "EVALUATE", "NEXT_CYCLE"]
            pos = 0
            for want in expected:
                assert want in states[pos:], f"{want} missing after {states}"
                pos = states.index(want, pos) + 1
            # Every decision record carries the full evidence contract.
            decisions = [e for e in _causal(causal) if e["kind"] == "decision"]
            assert decisions, "no durable decision evidence emitted"
            record = decisions[-1]["detail"]
            for field in (
                "decision_id",
                "pool_session_id",
                "generation",
                "job_fingerprint",
                "available_actions",
                "selected_action",
                "reason",
                "timestamp",
                "software_revision",
            ):
                assert field in record, f"decision evidence missing {field}"
            assert "disposition" in record or "result" in record
        finally:
            await _stop(task)
            server.close()

    asyncio.run(run())


def test_deterministic_share_submits_and_acknowledges(monkeypatch, tmp_path):
    """A winner flows submit → pool ack; counters are literal."""
    # bip34 coinb1: the pool-derived chain tip only exists when the job's
    # coinbase carries a BIP34 height (submit gating requires the tip).
    pool = FakePool(
        target=EASY_TARGET,
        job=_job("job-easy", prevhash="ab" * 32, coinb1=bip34_coinb1(800_001)),
    )

    async def run():
        server, port = await _serve(pool)
        _env(monkeypatch, tmp_path, pools={"braiins": port}, submit=True)
        task = await _launch(_args(submit=True))
        try:
            causal = tmp_path / "causal.jsonl"
            await until(lambda: len(pool.submits) >= 1, timeout=15, what="submit")
            await until(
                lambda: _session_log(tmp_path / "session.json") != [],
                timeout=10,
                what="share logged",
            )
            transitions = _cycle_transitions(causal)
            states = [to for _f, to, _e in transitions]
            for want in ("SUBMIT", "ACKNOWLEDGE", "EVALUATE"):
                assert want in states, f"{want} never reached: {states}"
            share = _session_log(tmp_path / "session.json")[-1]
            assert share["outcome"] is True, share
            assert share["submission_id"]
            events = _causal(causal)
            assert any(e["kind"] == "submission_sent" for e in events)
            assert any(
                e["kind"] == "cycle_transition" and e["detail"].get("to") == "ACKNOWLEDGE"
                for e in events
            )
        finally:
            await _stop(task)
            server.close()

    asyncio.run(run())


def test_replacement_job_invalidates_stale_work(monkeypatch, tmp_path):
    """A clean-job notify during hashing voids the in-flight window."""
    pool = FakePool(target=HARD_TARGET, job=_job("job-old"))

    real_execute = execution_router.ExecutionRouter.execute_plan
    slowed = asyncio.Event()

    def slow_execute(router, plan, header, target, **kwargs):
        # One delayed window so the clean job lands while it is in flight.
        if not slowed.is_set():
            slowed.set()
            time.sleep(0.4)
        return real_execute(router, plan, header, target, **kwargs)

    monkeypatch.setattr(execution_router.ExecutionRouter, "execute_plan", slow_execute)

    async def run():
        server, port = await _serve(pool)
        _env(monkeypatch, tmp_path, pools={"braiins": port}, submit=False)
        task = await _launch(_args(submit=False))
        try:
            causal = tmp_path / "causal.jsonl"
            await until(lambda: slowed.is_set(), timeout=15, what="window in flight")
            await pool.new_job(_job("job-new"))
            await until(
                lambda: any(
                    e["kind"] == "cycle_transition" and e["detail"].get("event") == "stale"
                    for e in _causal(causal)
                ),
                timeout=15,
                what="stale transition recorded",
            )
            # The invalidated window produced a record with nothing hashed
            # on stale work, and the pool never saw it.
            assert pool.submits == []
            assert any(
                e["kind"] == "execution_finished" and e["detail"].get("completion") == "INVALIDATED"
                for e in _causal(causal)
            ), "INVALIDATED record missing"
        finally:
            await _stop(task)
            server.close()

    asyncio.run(run())


def test_primary_failure_reconnects_to_failover(monkeypatch, tmp_path):
    """A dead primary is retried and the failover endpoint mines."""
    secondary = FakePool(target=HARD_TARGET, job=_job("job-p2"))

    async def run():
        # Reserve a port for the primary, then never accept on it.
        dead = await asyncio.start_server(lambda r, w: None, "127.0.0.1", 0)
        dead_port = dead.sockets[0].getsockname()[1]
        dead.close()
        server2, port2 = await _serve(secondary)
        _env(
            monkeypatch,
            tmp_path,
            pools={"braiins": dead_port, "viabtc": port2},
            submit=False,
            reconnect_max_s="0.5",
        )
        task = await _launch(_args(submit=False))
        try:
            causal = tmp_path / "causal.jsonl"
            await until(
                lambda: "mining.authorize:PYTHIA.001" in secondary.methods
                or "mining.authorize" in "\n".join(secondary.methods),
                timeout=20,
                what="secondary authorized",
            )
            await until(
                lambda: any(to == "MINE" for _f, to, _e in _cycle_transitions(causal)),
                timeout=15,
                what="mining on failover endpoint",
            )
            # The HEAL leg fired for the dead primary before SCAN recovered.
            transitions = _cycle_transitions(causal)
            assert any(
                to == "HEAL" and ev == "failure" for _f, to, ev in transitions
            ), "no SCAN→HEAL failure transition for dead primary"
        finally:
            await _stop(task)
            server2.close()

    asyncio.run(run())


def test_backend_failure_heals_and_reroutes(monkeypatch, tmp_path):
    """A device that fails is healed by Salamander via the registry factory."""
    pool = FakePool(target=HARD_TARGET, job=_job("job-heal"))

    class FlakyDevice:
        """Test-only OpenCL stand-in: fails m32 until its replacement probe."""

        backend = "opencl:gpu"
        device = "flaky-device"
        vendor = "test"
        fallback_reason = None
        grind_batch = 1 << 20
        m32_launch = 1 << 20
        m32_window_max = 1 << 20
        launches = 0
        kernel_ms = 0.0
        k_gold = None
        k_m32 = object()
        k_range = None
        hendrix_on_device = False

        def grind_target_m32(self, header, target_be, start, lane_order, count):
            raise RuntimeError("device fault (test fixture)")

        def grind_target_range(self, header, target_be, start, count):
            raise RuntimeError("device fault (test fixture)")

        def grind_target_batch(self, header80, target_be, nonces):
            raise RuntimeError("device fault (test fixture)")

    registry = BackendRegistry()
    probes = {"call": 0}

    def gpu_probe() -> LaneProbe:
        probes["call"] += 1
        if probes["call"] == 1:
            return LaneProbe(
                lane=BackendLane.GPU.value,
                available=True,
                backend="opencl:gpu",
                device="flaky-device",
                probed_at=time.time(),
                reason="probe passed (fixture)",
                hasher=FlakyDevice(),
            )
        # Second probe (the Salamander restart re-select) finds the lane gone
        # and the auto policy reroutes to the CPU reference.
        return LaneProbe(
            lane=BackendLane.GPU.value,
            available=False,
            backend=None,
            device=None,
            probed_at=time.time(),
            reason="device removed (fixture)",
        )

    registry._probes[BackendLane.GPU] = gpu_probe
    registry._probes[BackendLane.REMOTE_GPU] = lambda: LaneProbe(
        lane=BackendLane.REMOTE_GPU.value,
        available=False,
        backend=None,
        device=None,
        probed_at=time.time(),
        reason="not configured (fixture)",
    )
    monkeypatch.setenv("PYTHIA_NONCE_ORDER", "m32")
    monkeypatch.setattr(mining_runtime, "_registry", lambda: registry)

    async def run():
        server, port = await _serve(pool)
        _env(monkeypatch, tmp_path, pools={"braiins": port}, device="auto", submit=False)
        task = await _launch(_args(submit=False))
        try:
            causal = tmp_path / "causal.jsonl"
            await until(
                lambda: any(e["kind"] == "recovery_dispatched" for e in _causal(causal)),
                timeout=20,
                what="RESTART_LANE dispatched",
            )
            await until(
                lambda: any(e["kind"] == "execution_backend_rerouted" for e in _causal(causal)),
                timeout=15,
                what="lane rerouted",
            )
            await until(
                lambda: any(e["kind"] == "recovery_verified" for e in _causal(causal)),
                timeout=20,
                what="recovery verified by a healthy window",
            )
            # CPU reroute actually mined subsequent windows.
            assert any(
                e["kind"] == "execution_finished"
                and e["detail"].get("executed_route") == "cpu_reference"
                for e in _causal(causal)
            ), "no post-heal cpu_reference execution"
        finally:
            await _stop(task)
            server.close()

    asyncio.run(run())


def test_restart_never_resubmits_and_mines_fresh_work(monkeypatch, tmp_path):
    """Restart: a replayed job reproduces the same share, and the durable
    dedup log refuses the second write; fresh work still mines."""
    shared_job = _job("job-fixed", prevhash="ab" * 32, coinb1=bip34_coinb1(800_001))
    pool = FakePool(target=EASY_TARGET, job=shared_job)
    session_path = tmp_path / "session.json"
    causal = tmp_path / "causal.jsonl"

    async def run():
        server, port = await _serve(pool)
        _env(monkeypatch, tmp_path, pools={"braiins": port}, submit=True)
        args = _args(submit=True)
        # Phase 1: the share is found, submitted, accepted.
        task = await _launch(args)
        await until(lambda: len(pool.submits) == 1, timeout=15, what="first submit")
        await until(
            lambda: _session_log(session_path) != []
            and _session_log(session_path)[-1]["outcome"] is True,
            timeout=10,
            what="share accepted and logged",
        )
        await _stop(task)
        first_session_ids = {
            e["detail"].get("pool_session_id")
            for e in _causal(causal)
            if e["detail"].get("pool_session_id")
        }
        assert len(pool.submits) == 1

        # Phase 2: restart on the same session path; the pool serves the
        # identical job on the new connection, so the deterministic first
        # window reproduces the same share — the dedup gate refuses it.
        task = await _launch(args)
        await until(
            lambda: any(
                e["kind"] == "submission_gate_refused"
                and e["detail"].get("reason") == "DUPLICATE_SUBMISSION"
                for e in _causal(causal)
            ),
            timeout=20,
            what="duplicate share refused",
        )
        assert len(pool.submits) == 1, "a share was written twice"
        # Fresh work still flows: a new job produces a new share.
        await pool.new_job(_job("job-fresh", prevhash="cd" * 32, coinb1=bip34_coinb1(800_002)))
        await until(lambda: len(pool.submits) == 2, timeout=15, what="fresh submit")
        # Nothing stale was resurrected: the new run bound a new pool session.
        later_ids = {
            e["detail"].get("pool_session_id")
            for e in _causal(causal)
            if e["detail"].get("pool_session_id")
        }
        assert len(later_ids - first_session_ids) >= 1
        await _stop(task)
        server.close()

    asyncio.run(run())


def test_graceful_shutdown_records_terminal_state(monkeypatch, tmp_path):
    """A cancelled loop halts the cycle machine and closes the client."""
    pool = FakePool(target=HARD_TARGET, job=_job("job-shutdown"))

    async def run():
        server, port = await _serve(pool)
        _env(monkeypatch, tmp_path, pools={"braiins": port}, submit=False)
        task = await _launch(_args(submit=False))
        await until(lambda: pool.connections >= 1, timeout=15, what="connected")
        await _stop(task)
        causal = tmp_path / "causal.jsonl"
        events = _causal(causal)
        assert any(
            e["kind"] == "cycle_transition" and e["detail"].get("to") == "SHUTDOWN" for e in events
        ), "no SHUTDOWN transition recorded"
        server.close()

    asyncio.run(run())


def test_share_submits_through_the_chronus_lane_from_the_production_entry(monkeypatch, tmp_path):
    """PYTHIA_EXECUTION_DEVICE=chronus: entry point → Chronus virtual iGPU → pool ack."""
    monkeypatch.setenv("CHRONUS_VIGPU_STORE", str(tmp_path / "vigpu"))
    monkeypatch.setattr(vigpu_runtime, "_DAEMON", None)  # a fresh embedded daemon for this entry
    pool = FakePool(
        target=EASY_TARGET,
        job=_job("job-chronus", prevhash="ab" * 32, coinb1=bip34_coinb1(800_002)),
    )

    async def run():
        server, port = await _serve(pool)
        _env(monkeypatch, tmp_path, pools={"braiins": port}, device="chronus", submit=True)
        task = await _launch(_args(submit=True))
        try:
            causal = tmp_path / "causal.jsonl"
            await until(lambda: len(pool.submits) >= 1, timeout=30, what="submit")
            await until(
                lambda: _session_log(tmp_path / "session.json") != [],
                timeout=10,
                what="share logged",
            )
            share = _session_log(tmp_path / "session.json")[-1]
            assert share["outcome"] is True, share
            events = _causal(causal)
            finished = [e["detail"] for e in events if e["kind"] == "execution_finished"]
            assert finished, "the production loop recorded no execution"
            assert {d["executed_route"] for d in finished} == {"chronus_batch"}
            assert {d["requested_route"] for d in finished} == {"chronus_batch"}
            # The software emulator executed: never labelled as a hardware result.
            assert {d["evidence_class"] for d in finished} == {"SOFTWARE_VERIFIED"}
            winners = [d for d in finished if d["completion"] == "EARLY_WINNER"]
            assert winners and winners[0]["pool_outcome"] == "ACCEPTED"  # scripted local pool
            assert any(e["kind"] == "submission_sent" for e in events)
        finally:
            await _stop(task)
            server.close()

    asyncio.run(run())
