"""Canonical Poincare-golden 11D order on the production coordinator."""

from __future__ import annotations

import hashlib
import json
import os
import time

import pytest
from chronos_one_igpu.reference_contract import reference_execution

from chronus.mla1517.mining import poincare_11d_order
from chronus.mla1517.mining.coordinator import resolve_nonce_order
from chronus.mla1517.mining.execution_router import (
    DEVICE_RESULT_MISMATCH,
    NONCE_ORDER_M32,
    NONCE_ORDER_POINCARE_11D,
    ExecutionRouter,
    NonceOrderUnavailable,
    sha256d_scan,
)
from chronus.mla1517.mining.poincare_11d_order import poincare_11d_nonces
from chronus.mla1517.mining.nonce_lease import LeaseRecord
from chronus.mla1517.mining.search_plan import (
    CompletionState,
    LeaseState,
    NonceLease,
    WorkIdentity,
)
from chronus.mla1517.mining.solver import M32SearchSolver
from test_governance_causality import RecordingHasher, _plan


@pytest.fixture(scope="module", autouse=True)
def reference_scope(tmp_path_factory):
    """The 11D order is reference-only: production context refuses it.

    These tests verify the reference order itself, so they run inside an
    explicit, scoped, expiring operator approval -- the only way the
    capability is reachable -- never in production context.
    """
    record = {
        "schema": "chronos.reference_approvals/1",
        "approvals": {
            "qc-local": {
                "approved": True,
                "approved_by": "local-test-operator",
                "purpose": "poincare 11D reference-order verification, not production evidence",
                "mode": "reference",
                "expires_unix": time.time() + 600,
                "capabilities": ["poincare_11d_order"],
            }
        },
    }
    path = tmp_path_factory.mktemp("reference-approvals") / "approvals.json"
    path.write_text(json.dumps(record))
    previous = os.environ.get("CHRONOS_REFERENCE_APPROVALS_FILE")
    os.environ["CHRONOS_REFERENCE_APPROVALS_FILE"] = str(path)
    try:
        with reference_execution("qc-local"):
            yield
    finally:
        if previous is None:
            os.environ.pop("CHRONOS_REFERENCE_APPROVALS_FILE", None)
        else:
            os.environ["CHRONOS_REFERENCE_APPROVALS_FILE"] = previous


BASE = 0x0010_0000
HEADER = bytes(range(80))


class CpuHasher:
    backend = "cpu"
    device = None
    vendor = None
    launches = 0
    kernel_ms = 0.0

    def __init__(self, grind_batch: int = 29) -> None:
        self.grind_batch = grind_batch


def _sha256d(nonce: int) -> bytes:
    blob = HEADER[:76] + nonce.to_bytes(4, "little")
    return hashlib.sha256(hashlib.sha256(blob).digest()).digest()


def _leased(route: str, window: int, base: int = BASE):
    plan = _plan(route, base_step=base, window=window, dispatch_breadth=window)
    return plan, NonceLease("l", plan.generation, plan.plan_id, base, window)


def _router(hasher, visited=None, cpu_nonce_executor=sha256d_scan):
    def cpu_nonces(header, target, nonces):
        nonces = list(nonces)
        if visited is not None:
            visited.extend(nonces)
        return cpu_nonce_executor(header, target, nonces)

    return ExecutionRouter(
        hasher,
        lambda _header, _target, _start, count: (None, None, count),
        nonce_order=lambda _plan: NONCE_ORDER_POINCARE_11D,
        cpu_nonce_executor=cpu_nonces,
    )


def test_order_is_deterministic_unique_complete_and_not_m32():
    window = 997
    first = poincare_11d_nonces(HEADER, BASE, window)
    second = poincare_11d_nonces(HEADER, BASE, window)
    m32 = [nonce for nonce, _lane in M32SearchSolver().candidates(BASE, window)]
    assert first == second
    assert len(first) == len(set(first)) == window
    assert sorted(first) == list(range(BASE, BASE + window))
    assert first != m32


@pytest.mark.parametrize("alias", ("11d", "poincare11d", "poincare", "manifold"))
def test_coordinator_accepts_only_declared_11d_aliases(alias):
    assert resolve_nonce_order(alias) == NONCE_ORDER_POINCARE_11D


@pytest.mark.parametrize("value", ("poincare_11d", "11-d", "golden", "crystal"))
def test_coordinator_rejects_undeclared_aliases(value):
    with pytest.raises(ValueError):
        resolve_nonce_order(value)


def test_missing_11d_dependency_fails_explicitly(monkeypatch):
    import chronus.mla1517.mining.coordinator as coordinator

    monkeypatch.setattr(
        coordinator, "load_poincare_11d", lambda: (None, "ImportError: gone")
    )
    with pytest.raises(NonceOrderUnavailable, match="ImportError: gone"):
        resolve_nonce_order("11d")

    monkeypatch.setattr(
        poincare_11d_order, "load_poincare_11d", lambda: (None, "ImportError: gone")
    )
    with pytest.raises(NonceOrderUnavailable, match="ImportError: gone"):
        poincare_11d_nonces(HEADER, BASE, 32)


def test_router_executes_full_11d_order_and_records_it():
    visited: list[int] = []
    plan, lease = _leased("cpu_reference", 257)
    record, candidate = _router(CpuHasher(), visited).execute_plan(
        plan, HEADER, bytes(32), lease=lease
    )
    assert candidate is None
    assert record.completion_state is CompletionState.COMPLETE
    assert record.requested_nonce_order == NONCE_ORDER_POINCARE_11D
    assert record.executed_nonce_order == NONCE_ORDER_POINCARE_11D
    assert visited == poincare_11d_nonces(HEADER, BASE, 257)
    assert sorted(visited) == list(range(BASE, BASE + 257))


def test_production_coordinator_routes_11d_through_cpu_reference(monkeypatch):
    from manifold_pool_coordinator import PoolEndpoint
    from test_pool_only_mining import _pool_only_coordinator

    monkeypatch.setenv("PYTHIA_NONCE_ORDER", "11d")
    coordinator = _pool_only_coordinator([PoolEndpoint("h", 1, "braiins")])

    class _DeviceStandIn:
        backend = "opencl:stand-in"
        k_m32 = object()

    # The default CPU hasher is already cpu_reference, so only a device-shaped hasher shows
    # that the 11D rule (and not the hasher) is what keeps 11D off the M32 device kernel.
    real_hasher = coordinator.execution_hasher
    coordinator.execution_hasher = _DeviceStandIn()
    try:
        assert coordinator._execution_route() == "cpu_reference"
        monkeypatch.setattr(coordinator, "_nonce_order", NONCE_ORDER_M32)
        assert coordinator._execution_route() == "opencl_m32"
    finally:
        coordinator.execution_hasher = real_hasher
        monkeypatch.setattr(coordinator, "_nonce_order", NONCE_ORDER_POINCARE_11D)
    assert coordinator._execution_route() == "cpu_reference"
    window = 96
    identity = WorkIdentity("s", 1, "j", "fp", 0, False, 1.0)
    leased = LeaseRecord("l", identity.key, 1, "00", BASE, window, LeaseState.RESERVED)
    plan = coordinator._baseline_plan(identity, leased, window, "test")
    lease = leased.contract()
    assert plan.nonce_order == NONCE_ORDER_POINCARE_11D
    assert plan.executor_route == "cpu_reference"
    record, candidate = coordinator._router_for(plan).execute_plan(
        plan, HEADER, bytes(32), lease=lease
    )
    assert candidate is None
    assert record.requested_nonce_order == NONCE_ORDER_POINCARE_11D
    assert record.executed_nonce_order == NONCE_ORDER_POINCARE_11D

    monkeypatch.setenv("PYTHIA_NONCE_ORDER", "m32")
    monkeypatch.setattr(coordinator, "_nonce_order", NONCE_ORDER_M32)
    record, candidate = coordinator._router_for(plan).execute_plan(
        plan, HEADER, bytes(32), lease=lease
    )
    assert candidate is None
    assert record.requested_nonce_order == NONCE_ORDER_POINCARE_11D
    assert record.executed_nonce_order == NONCE_ORDER_POINCARE_11D


def test_opencl_m32_request_falls_back_to_cpu_instead_of_relabelling_order():
    hasher = RecordingHasher()
    visited: list[int] = []
    plan, lease = _leased("opencl_m32", 96)
    record, candidate = _router(hasher, visited).execute_plan(
        plan, HEADER, bytes(32), lease=lease
    )
    assert candidate is None and hasher.calls == []
    assert record.requested_route == "opencl_m32"
    assert record.executed_route == "cpu_reference"
    assert record.requested_nonce_order == NONCE_ORDER_POINCARE_11D
    assert record.executed_nonce_order == NONCE_ORDER_POINCARE_11D
    assert sorted(visited) == list(range(BASE, BASE + 96))


def test_sha256d_and_target_remain_the_only_acceptance_authority():
    window = 257
    planted = min(
        range(BASE, BASE + window),
        key=lambda nonce: int.from_bytes(_sha256d(nonce), "little"),
    )
    plan, lease = _leased("cpu_reference", window)
    record, candidate = _router(CpuHasher()).execute_plan(
        plan, HEADER, _sha256d(planted), lease=lease
    )
    assert candidate is not None and candidate["nonce"] == planted
    assert candidate["digest"] == _sha256d(planted)
    assert candidate["independently_rechecked"] is True
    assert record.locally_valid_shares == 1

    def fabricated(_header, _target, nonces):
        return list(nonces)[0], bytes(32), 1

    record, candidate = _router(
        CpuHasher(), cpu_nonce_executor=fabricated
    ).execute_plan(plan, HEADER, bytes(32), lease=lease)
    assert candidate is None
    assert record.completion_state is CompletionState.DEVICE_ERROR
    assert record.device_error == DEVICE_RESULT_MISMATCH
    assert record.locally_valid_shares == 0
