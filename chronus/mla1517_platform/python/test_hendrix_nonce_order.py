"""Hendrix coprime-stride nonce order on the canonical execution router."""

from __future__ import annotations

import hashlib
import os

import pytest

from chronus.mla1517.mining import hendrix_order
from chronus.mla1517.mining.coordinator import resolve_nonce_order
from chronus.mla1517.mining.execution_router import (
    NONCE_ORDER_HENDRIX,
    NONCE_ORDER_M32,
    NONCE_ORDER_SEQUENTIAL,
    ExecutionRouter,
    NonceOrderUnavailable,
    sha256d_scan,
)
from chronus.mla1517.mining.hendrix_order import hendrix_schedule, worker_nonces
from chronus.mla1517.mining.search_plan import CompletionState, NonceLease, SearchPlan
from test_governance_causality import LANES, RecordingHasher, _plan

WINDOWS = (1, 2, 3, 7, 31, 32, 96, 100, 997, 1024)
BASE = 0x7FFF_0000
HEADER = bytes(range(80))


class CpuHasher:
    backend = "cpu"
    device = None
    vendor = None
    launches = 0
    kernel_ms = 0.0

    def __init__(self, grind_batch: int = 7) -> None:
        self.grind_batch = grind_batch


def _sha256d(nonce: int) -> bytes:
    blob = HEADER[:76] + nonce.to_bytes(4, "little")
    return hashlib.sha256(hashlib.sha256(blob).digest()).digest()


def _leased(route: str, window: int, base: int = BASE) -> tuple[SearchPlan, NonceLease]:
    plan = _plan(route, base_step=base, window=window, dispatch_breadth=window)
    return plan, NonceLease("l", plan.generation, plan.plan_id, base, window)


def _hendrix_router(hasher, visited=None, contiguous=None):
    def cpu_nonces(header, target, nonces):
        nonces = list(nonces)
        if visited is not None:
            visited.extend(nonces)
        return sha256d_scan(header, target, nonces)

    def cpu(header, target, start, count):
        if contiguous is not None:
            contiguous.append((start, count))
        return None, None, count

    return ExecutionRouter(
        hasher, cpu, nonce_order=lambda _p: NONCE_ORDER_HENDRIX, cpu_nonce_executor=cpu_nonces
    )


@pytest.mark.parametrize("window", WINDOWS)
def test_leased_window_is_visited_exactly_once_and_stays_inside_the_lease(window):
    visited: list[int] = []
    plan, lease = _leased("cpu_reference", window)
    rec, cand = _hendrix_router(CpuHasher(), visited).execute_plan(
        plan, HEADER, bytes(32), lease=lease
    )
    assert cand is None and rec.completion_state is CompletionState.COMPLETE
    assert len(visited) == window == rec.completed_work_items == rec.hash_count
    assert sorted(visited) == list(range(BASE, BASE + window))
    assert all(lease.start <= n < lease.start + lease.count for n in visited)
    schedule = hendrix_schedule(window)
    assert visited == [BASE + schedule.nonce_at(i) for i in range(window)]
    assert rec.chunk_count == -(-window // 7)


def test_order_is_a_stride_permutation_not_the_sequential_sweep():
    visited: list[int] = []
    plan, lease = _leased("cpu_reference", 96)
    _hendrix_router(CpuHasher(), visited).execute_plan(plan, HEADER, bytes(32), lease=lease)
    stride = hendrix_schedule(96).stride
    assert stride != 1 and visited[:2] == [BASE, BASE + stride]


@pytest.mark.parametrize("window", (1, 3, 100, 997))
def test_planted_nonce_is_found_and_verifies_against_the_target(window):
    nonces = range(BASE, BASE + window)
    planted = min(nonces, key=lambda n: int.from_bytes(_sha256d(n), "little"))
    target = _sha256d(planted)  # the unique minimum: only `planted` meets it
    plan, lease = _leased("cpu_reference", window)
    rec, cand = _hendrix_router(CpuHasher()).execute_plan(plan, HEADER, target, lease=lease)
    assert cand is not None and cand["nonce"] == planted
    assert cand["independently_rechecked"] is True
    digest = _sha256d(cand["nonce"])
    assert cand["digest"] == digest
    assert int.from_bytes(digest, "little") <= int.from_bytes(target, "little")
    assert rec.completion_state is CompletionState.EARLY_WINNER
    assert rec.locally_valid_shares == 1
    position = hendrix_schedule(window).nonce_at
    probes = next(i for i in range(window) if BASE + position(i) == planted) + 1
    assert rec.completed_work_items == probes


def test_cpu_route_records_hendrix_requested_and_executed():
    plan, lease = _leased("cpu_reference", 64)
    rec, _ = _hendrix_router(CpuHasher()).execute_plan(plan, HEADER, bytes(32), lease=lease)
    assert rec.requested_nonce_order == NONCE_ORDER_HENDRIX
    assert rec.executed_nonce_order == NONCE_ORDER_HENDRIX


def test_device_m32_window_is_recorded_as_m32_not_hendrix():
    hasher = RecordingHasher()
    contiguous: list = []
    plan, lease = _leased("opencl_m32", 96, base=4096)
    rec, _ = _hendrix_router(hasher, contiguous=contiguous).execute_plan(
        plan, HEADER, bytes(32), lease=lease
    )
    assert [c[:3:2] for c in hasher.calls] == [("m32", 4096)] and hasher.calls[0][4] == 96
    assert rec.requested_nonce_order == NONCE_ORDER_HENDRIX
    assert rec.executed_nonce_order == NONCE_ORDER_M32


def test_a_device_with_the_hendrix_kernel_runs_hendrix_itself():
    hasher = RecordingHasher()
    hasher.hendrix_on_device = True
    runs: list = []

    def grind_target_hendrix(header, target_be, base, window, stride, position, count):
        runs.append((base, window, stride, position, count))
        return None, None, count

    hasher.grind_target_hendrix = grind_target_hendrix
    plan, lease = _leased("opencl_m32", 96, base=4096)
    rec, _ = _hendrix_router(hasher).execute_plan(plan, HEADER, bytes(32), lease=lease)
    stride = hendrix_schedule(96).stride
    positions = [(r[3], r[4]) for r in runs]
    assert all(r[:3] == (4096, 96, stride) for r in runs) and hasher.calls == []
    assert positions[0][0] == 0 and sum(c for _, c in positions) == 96
    assert all(a + n == b for (a, n), (b, _) in zip(positions, positions[1:]))
    assert rec.executed_route == "opencl_m32"
    assert rec.executed_nonce_order == NONCE_ORDER_HENDRIX


def test_device_range_window_is_recorded_as_sequential():
    plan, lease = _leased("opencl_range", 96, base=4096)
    rec, _ = _hendrix_router(RecordingHasher()).execute_plan(plan, HEADER, bytes(32), lease=lease)
    assert rec.executed_nonce_order == NONCE_ORDER_SEQUENTIAL


def test_kernel_fallback_to_cpu_executes_hendrix():
    hasher = RecordingHasher()
    hasher.k_m32 = None
    visited: list[int] = []
    plan, lease = _leased("opencl_m32", 96, base=4096)
    rec, _ = _hendrix_router(hasher, visited).execute_plan(plan, HEADER, bytes(32), lease=lease)
    assert rec.executed_route == "cpu_reference" and hasher.calls == []
    assert sorted(visited) == list(range(4096, 4096 + 96))
    assert rec.executed_nonce_order == NONCE_ORDER_HENDRIX


def test_hendrix_does_not_lift_the_golden_stride_lease_refusal():
    hasher = RecordingHasher()
    plan, lease = _leased("opencl_gold", 96, base=4096)
    rec, cand = _hendrix_router(hasher).execute_plan(plan, HEADER, bytes(32), lease=lease)
    assert rec.completion_state is CompletionState.REFUSED
    assert cand is None and hasher.calls == []


@pytest.mark.parametrize("window,workers", [(1, 1), (7, 3), (96, 4), (100, 7), (997, 8)])
def test_worker_arms_are_disjoint_and_cover_the_window(window, workers):
    schedule = hendrix_schedule(window, workers)
    arms = [list(worker_nonces(BASE, schedule, w)) for w in range(schedule.workers)]
    flat = [n for arm in arms for n in arm]
    assert len(flat) == len(set(flat)) == window
    assert set(flat) == set(range(BASE, BASE + window))


def test_unavailable_schedule_fails_loudly(monkeypatch):
    monkeypatch.setattr(hendrix_order, "load_hendrix", lambda: (None, "ImportError: gone"))
    hendrix_order.hendrix_schedule.cache_clear()
    try:
        plan, lease = _leased("cpu_reference", 5)
        with pytest.raises(NonceOrderUnavailable, match="gone"):
            _hendrix_router(CpuHasher()).execute_plan(plan, HEADER, bytes(32), lease=lease)
    finally:
        hendrix_order.hendrix_schedule.cache_clear()


def test_coordinator_nonce_order_configuration(monkeypatch):
    assert resolve_nonce_order("m32") == NONCE_ORDER_M32
    assert resolve_nonce_order(" Hendrix ") == NONCE_ORDER_HENDRIX
    with pytest.raises(ValueError):
        resolve_nonce_order("golden")
    import chronus.mla1517.mining.coordinator as coordinator

    monkeypatch.setattr(coordinator, "load_hendrix", lambda: (None, "ImportError: gone"))
    with pytest.raises(NonceOrderUnavailable):
        resolve_nonce_order("hendrix")


def test_coordinator_runs_hendrix_when_configured(monkeypatch):
    from manifold_pool_coordinator import PoolEndpoint
    from test_pool_only_mining import _pool_only_coordinator

    monkeypatch.setenv("PYTHIA_NONCE_ORDER", "hendrix")
    coord = _pool_only_coordinator([PoolEndpoint("h", 1, "braiins")])
    window = 100
    planted = min(range(BASE, BASE + window), key=lambda n: int.from_bytes(_sha256d(n), "little"))
    plan, lease = _leased(coord._execution_route(), window)
    rec, cand = coord._router_for(plan).execute_plan(plan, HEADER, _sha256d(planted), lease=lease)
    assert cand is not None and cand["nonce"] == planted
    assert rec.requested_nonce_order == rec.executed_nonce_order == NONCE_ORDER_HENDRIX


def test_hendrix_is_the_coordinators_default_order(monkeypatch):
    from manifold_pool_coordinator import PoolEndpoint
    from test_pool_only_mining import _pool_only_coordinator

    monkeypatch.delenv("PYTHIA_NONCE_ORDER", raising=False)
    assert "PYTHIA_NONCE_ORDER" not in os.environ
    coord = _pool_only_coordinator([PoolEndpoint("h", 1, "braiins")])
    plan = _plan(coord._execution_route(), lane_order=LANES)
    rec, _ = coord._router_for(plan).execute_plan(plan, HEADER, (1).to_bytes(32, "little"))
    assert rec.requested_nonce_order == rec.executed_nonce_order == NONCE_ORDER_HENDRIX
    monkeypatch.setenv("PYTHIA_NONCE_ORDER", "m32")  # the Turing lane order stays selectable
    coord = _pool_only_coordinator([PoolEndpoint("h", 1, "braiins")])
    rec, _ = coord._router_for(plan).execute_plan(plan, HEADER, (1).to_bytes(32, "little"))
    assert rec.requested_nonce_order == rec.executed_nonce_order == NONCE_ORDER_M32
