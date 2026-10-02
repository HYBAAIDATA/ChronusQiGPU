"""Bridge-free mining: the real coordinator and Stratum client over TCP.

``run_execution_loop`` drives the canonical path (Stratum identity -> leased
SearchPlan -> exact dispatch certificate -> Execution Router -> host recheck)
from the pool's jobs, with no MMIO bridge. A scripted local pool stands in for
the network; the CPU reference hasher executes. Nothing here is live-pool or
hardware evidence.
"""

from __future__ import annotations

import asyncio
import contextlib
import socket

import pytest

import mining_runtime
from manifold_pool_coordinator import PoolEndpoint
from chronus.mla1517.mining.coordinator import IntelligentPoolCoordinator
from chronus.mla1517.mining.session import MiningSession
from test_agentic_voyages import HARD_TARGET, FakePool, _job, until


def _coordinator(endpoints, tmp_path, **kwargs):
    coord = IntelligentPoolCoordinator(
        endpoints,
        username="PYTHIA.001",
        password="x",
        submit_enabled=False,
        mining_session=MiningSession(cooldown_seconds=0),
        **kwargs,
    )
    coord.control_socket_path = str(tmp_path / "coordinator.sock")
    return coord


async def _stop(task: asyncio.Task) -> None:
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


def _dead_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


async def _mines_reports_and_reconnects(tmp_path):
    pool = FakePool(target=HARD_TARGET, job=_job("job-x"))
    server = await asyncio.start_server(pool.handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    snapshots: list[dict] = []
    metrics: list[dict] = []
    coord = _coordinator(
        [PoolEndpoint("127.0.0.1", port, "fake-pool")],
        tmp_path,
        stratum_status_sink=snapshots.append,
        reconnect_delay=0.05,
    )
    coord.set_metrics_sink(metrics.append)
    task = asyncio.create_task(coord.run_execution_loop(idle_s=0.01))
    try:
        await until(lambda: coord._executions_total >= 2, timeout=60, what="two executions")
        assert snapshots[-1]["primary"]["authorized"] is True
        assert snapshots[-1]["job"]["job_id"] == "job-x"
        assert metrics[-1]["hashrate_hs"] > 0
        assert metrics[-1]["hashes_total"] >= metrics[-1]["executions_total"] >= 2
        cert = coord.evidence_snapshot()["dispatch_algebra"]
        assert cert["ok"], cert["refusal"]
        assert cert["job_id"] == "job-x"
        assert all(cert["lucas"]["checks"].values())
        assert cert["counts"]["refused"] == 0 and cert["counts"]["certified"] >= 2
        assert coord.last_execution["executed"] is True
        # Closed-loop optimisation is registered by the real production
        # coordinator and consumes these completed ExecutionRecords without a
        # direct test-only invocation.
        optimisation = coord.evidence_snapshot()["optimization"]
        assert optimisation["status"] in {"MONITORING", "TRIAL"}
        assert optimisation["last_observation"] != "Unavailable"
        assert optimisation["evidence_source"] == "completed production ExecutionRecord"

        # The pool drops the session: the loop reconnects and keeps mining.
        connections = pool.connections
        pool._writer.close()
        await until(
            lambda: pool.connections > connections
            and coord.client is not None
            and coord.client.connected,
            timeout=30,
            what="reconnect",
        )
        executed = coord._executions_total
        await until(lambda: coord._executions_total > executed, timeout=60, what="resume")
        assert not task.done()
    finally:
        await _stop(task)
        server.close()
        await server.wait_closed()


def test_bridge_free_loop_mines_reports_and_reconnects(tmp_path):
    asyncio.run(_mines_reports_and_reconnects(tmp_path))


async def _fails_over_to_the_secondary(tmp_path):
    pool = FakePool(target=HARD_TARGET, job=_job("job-f"))
    server = await asyncio.start_server(pool.handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    coord = _coordinator(
        [
            PoolEndpoint("127.0.0.1", _dead_port(), "braiins"),
            PoolEndpoint("127.0.0.1", port, "viabtc"),
        ],
        tmp_path,
        reconnect_delay=0.05,
    )
    task = asyncio.create_task(coord.run_execution_loop(idle_s=0.01))
    try:
        await until(lambda: coord._executions_total >= 1, timeout=60, what="failover execution")
        assert coord.client.endpoint.name == "viabtc"
    finally:
        await _stop(task)
        server.close()
        await server.wait_closed()


def test_bridge_free_loop_fails_over_to_the_secondary(tmp_path):
    asyncio.run(_fails_over_to_the_secondary(tmp_path))


async def _survives_refused_authorization(tmp_path):
    pool = FakePool(target=HARD_TARGET, job=_job("job-r"), worker="someone.else")
    server = await asyncio.start_server(pool.handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    snapshots: list[dict] = []
    coord = _coordinator(
        [PoolEndpoint("127.0.0.1", port, "fake-pool")],
        tmp_path,
        stratum_status_sink=snapshots.append,
        reconnect_delay=0.02,
    )
    task = asyncio.create_task(coord.run_execution_loop(idle_s=0.01, max_backoff_s=0.1))
    try:
        await until(lambda: pool.connections >= 3, timeout=20, what="authorization retries")
        assert not task.done()
        assert coord._executions_total == 0
        assert any(s["state"] == "AUTH_FAILED" for s in snapshots)
    finally:
        await _stop(task)
        server.close()
        await server.wait_closed()


def test_bridge_free_loop_survives_refused_authorization(tmp_path):
    asyncio.run(_survives_refused_authorization(tmp_path))


def test_execution_device_is_declared_not_guessed(monkeypatch):
    monkeypatch.delenv("PYTHIA_EXECUTION_DEVICE", raising=False)
    assert mining_runtime.execution_device() is None
    monkeypatch.setenv("PYTHIA_EXECUTION_DEVICE", " OpenCL ")
    assert mining_runtime.execution_device() == "opencl"
    monkeypatch.setenv("PYTHIA_EXECUTION_DEVICE", "fpga")
    with pytest.raises(SystemExit):
        mining_runtime.execution_device()
