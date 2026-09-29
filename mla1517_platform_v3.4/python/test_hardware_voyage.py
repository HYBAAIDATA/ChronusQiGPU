"""Hardware voyage: SearchPlan → lease → Execution Router → real OpenCL → pool.

Runs on the host's actual OpenCL device (here an Intel UHD 620) and skips with
NOT_RUN when none binds. The pool is the scripted local TCP pool; a live pool
is not contacted. Every hardware claim below is read from the router's
ExecutionRecord (kernel launches, device clock), never inferred from a mock.
"""

from __future__ import annotations

import asyncio

import pytest

import mining_runtime
from manifold_pool_coordinator import PoolEndpoint
from mla1517.mining.coordinator import IntelligentPoolCoordinator
from mla1517.mining.session import MiningSession
from test_agentic_voyages import (
    EASY_TARGET,
    HARD_TARGET,
    FakeChain,
    FakePool,
    _connected,
    _job,
    _served,
    parent_of_current_job,
    until,
)


@pytest.fixture(scope="module")
def device_hasher():
    hasher = mining_runtime._execution_hasher("auto")
    if not str(hasher.backend).startswith("opencl"):
        pytest.skip(f"NOT_RUN: no OpenCL device ({hasher.fallback_reason})")
    if getattr(hasher, "k_m32", None) is None:
        pytest.skip("NOT_RUN: OpenCL device bound without the M32 kernel")
    return hasher


def _coordinator(port: int, chain: FakeChain, hasher) -> IntelligentPoolCoordinator:
    return IntelligentPoolCoordinator(
        [PoolEndpoint("127.0.0.1", port, "fake-pool")],
        username="PYTHIA.001",
        password="x",
        submit_enabled=True,
        mining_session=MiningSession(cooldown_seconds=0),
        chain_observer=chain,
        execution_hasher=hasher,
    )


async def _voyage(hasher) -> None:
    pool = FakePool(target=HARD_TARGET, job=_job("job-hw"))
    server, port = await _served(pool)
    chain = FakeChain()
    coord = _coordinator(port, chain, hasher)
    try:
        await _connected(coord, "job-hw")
        assert coord._fill_precompute_queue() >= 1
        plan = list(coord.agentic._queue.queue)[0]
        assert plan.executor_route == "opencl_m32"

        launches_before = hasher.launches
        assert await coord.search_current_job() is False
        full = coord.last_execution
        assert full["plan_id"] == plan.plan_id
        assert full["executed_route"] == "opencl_m32"
        assert full["evidence_class"] == "HARDWARE_EXECUTED"
        assert full["completion_state"] == "COMPLETE"
        assert full["attempts"] == plan.window
        assert full["kernel_launch_count"] >= 1 and hasher.launches > launches_before
        assert full["kernel_ms"] > 0
        assert full["device_name"] == hasher.device
        # Device-sized Lucas windows: the GPU is fed, not idled by tiny launches.
        assert plan.window >= 1_000_000
        assert plan.evidence_refs["window_basis"] == "device_launch_lucas"
        rate = full["attempts"] / (full["kernel_ms"] / 1000.0)
        assert rate > 5_000_000, f"device rate {rate / 1e6:.1f} MH/s"
        print(f"UHD kernel rate {rate / 1e6:.1f} MH/s over {plan.window} nonces")

        await pool.push("mining.set_target", [EASY_TARGET])
        await until(lambda: coord.client.proof_adapter.target == int(EASY_TARGET, 16))
        chain.block_hash = parent_of_current_job(coord)
        assert await coord.search_current_job() is True
        share = coord.last_execution
        assert share["executed_route"] == "opencl_m32"
        assert share["evidence_class"] == "HARDWARE_EXECUTED"
        assert share["completion_state"] == "EARLY_WINNER"
        assert share["pool_outcome"] == "ACCEPTED"
        assert len(pool.submits) == 1

        trace = coord.causal.trace(submission_id=share["submission_id"])
        kinds = [event.kind for event in trace]
        for kind in ("identity_bound", "execution_started", "candidate_found", "submission_sent"):
            assert kind in kinds
        finished = [e for e in coord.causal.events() if e.kind == "execution_finished"]
        assert finished[-1].detail["evidence_class"] == "HARDWARE_EXECUTED"
        quality = coord.agentic.snapshot()["quality"]
        executed = sum(
            q["execution"]["evidence_classes"].get("HARDWARE_EXECUTED", 0) for q in quality.values()
        )
        assert executed >= 2
    finally:
        await coord.client.close()
        server.close()
        await server.wait_closed()


def test_hardware_voyage_on_real_opencl(device_hasher):
    asyncio.run(_voyage(device_hasher))


@pytest.mark.parametrize("target_bits", [252, 1])
def test_gpu_m32_and_cpu_reference_agree_exactly(device_hasher, target_bits):
    """Same plan, same header: identical first winner in probe order.

    Hash counts are physical work and legitimately differ on a hit: the kernel
    hashes its whole launch before atomic_min picks the earliest winner, while
    the serial CPU sweep stops at it. Without a hit both cover the window.
    """
    from dataclasses import replace

    from mla1517.mining.search_plan import SearchPlan

    coord = _coordinator(1, FakeChain(), device_hasher)
    lanes = tuple((7 * i) % 32 for i in range(32))
    gpu_plan = SearchPlan(
        job_fingerprint="fp",
        pool_session_id="s",
        generation=1,
        base_step=32 * 1000,
        window=96,
        extranonce2="00",
        lane_order=lanes,
        preferred_face=0,
        dispatch_breadth=96,
        executor_route="opencl_m32",
        policy_id="parity",
        evidence_refs={},
        created_at=1.0,
    )
    cpu_plan = replace(gpu_plan, executor_route="cpu_reference")
    header = bytes(range(80))
    target = (1 << target_bits).to_bytes(32, "little")
    gpu_rec, gpu_cand = coord._router_for(gpu_plan).execute_plan(gpu_plan, header, target)
    cpu_rec, cpu_cand = coord._router_for(cpu_plan).execute_plan(cpu_plan, header, target)
    assert gpu_rec.evidence_class.value == "HARDWARE_EXECUTED"
    assert cpu_rec.executed_route == "cpu_reference"
    assert (gpu_cand or {}).get("nonce") == (cpu_cand or {}).get("nonce")
    if target_bits == 252:
        assert gpu_cand is not None and gpu_cand["independently_rechecked"]
        assert gpu_rec.hash_count == gpu_plan.window >= cpu_rec.hash_count
    else:
        assert gpu_cand is None
        assert gpu_rec.hash_count == cpu_rec.hash_count == gpu_plan.window
