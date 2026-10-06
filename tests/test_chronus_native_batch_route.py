"""Regression gates for the canonical Chronus 600-way production route.

These are software-contract tests. They prove that the canonical PYTHIA
600-vertex itinerary is handed to a first-class Chronus ordered-batch route
without relabelling Chronus as CUDA/OpenCL/Metal, and that the 10 EH/s value is
a governed configuration ceiling rather than fabricated measured telemetry.
"""

from __future__ import annotations

import importlib.util
import time
from dataclasses import replace
from pathlib import Path

from chronus.mla1517.mining.execution_router import NONCE_ORDER_HENDRIX
from chronus.mla1517.mining.geodesic_support import (
    PythiaProductionMiningCoordinator,
    ProductionExecutionRouter,
    chronus_fabric_execution_state_for,
    chronus_fabric_state_for,
)
from chronus.mla1517.mining.h4_600_execution import promote_execution_hasher
from chronus.mla1517.mining.pythia_search import (
    SEARCH_ARCHITECTURE_ID,
    precompute_pythia_search,
    pythia_hendrix_nonces,
)
from chronus.mla1517.mining.search_plan import (
    CompletionState,
    EvidenceClass,
    NonceLease,
    SearchPlan,
)
from hyba.hybrid.coordinator import HybridCoordinator
from hyba.hybrid.nonce_scheduler import (
    DeviceCapability,
    DispatchHandle,
    next_handle_id,
)
from hyba.hybrid.super_asic import SuperAsicHasher

HEADER = bytes(range(80))
BASE = 0x0020_0000
WINDOW = 1200


class _ChronusBatchHasher:
    vendor = "test"
    device = "chronus-contract-device"
    grind_batch = 320
    kernel_ms = 0.0
    launches = 0

    def __init__(self, backend: str = "cuda") -> None:
        self.backend = backend
        self.seen: list[int] = []
        self.kernel_ms = 0.0
        self.launches = 0

    def grind_target_batch(self, _header, _target_be, nonces):
        batch = [int(nonce) for nonce in nonces]
        self.seen.extend(batch)
        self.launches += 1
        self.kernel_ms += 0.01
        return None, None, len(batch)


class _NoBatchHasher:
    backend = "cuda"
    vendor = "test"
    device = "chronus-contract-device"
    grind_batch = 320
    kernel_ms = 0.0
    launches = 0


class _FabricScheduler:
    def __init__(self) -> None:
        self._cap = DeviceCapability(
            device_id="chronus-fabric-test",
            device_class="gpu",
            measured_hashes_per_sec=1.0,
            supported=True,
        )
        self._pending: dict[int, DispatchHandle] = {}
        self._done: dict[int, int] = {}
        self.dispatched = []

    def capability(self):
        return self._cap

    def prepare(self, _job_id, header80):
        assert len(header80) == 80

    def dispatch(self, window):
        self.dispatched.append(window)
        handle = DispatchHandle(
            handle_id=next_handle_id(),
            device_id=self._cap.device_id,
            window=window,
            dispatched_ns=1,
        )
        self._pending[handle.handle_id] = handle
        return handle

    def poll(self, handle):
        pending = self._pending.pop(handle.handle_id, None)
        if pending is not None:
            self._done[handle.handle_id] = handle.window.span
        return None

    def is_done(self, handle):
        return handle.handle_id in self._done

    def hashed_count(self, handle):
        return self._done.get(handle.handle_id, 0)

    def cancel(self, handle, reason="cancelled"):
        del reason
        self._pending.pop(handle.handle_id, None)
        self._done.setdefault(handle.handle_id, 0)


def _plan(route: str = "chronus_batch") -> SearchPlan:
    return SearchPlan(
        job_fingerprint="fp-chronus-600",
        pool_session_id="session-chronus-600",
        generation=1,
        base_step=BASE,
        window=WINDOW,
        extranonce2="00000000",
        lane_order=tuple(range(32)),
        preferred_face=0,
        dispatch_breadth=WINDOW,
        executor_route=route,
        policy_id="canonical-600",
        evidence_refs={"search_architecture": SEARCH_ARCHITECTURE_ID},
        created_at=time.monotonic(),
        plan_id="plan-chronus-600",
        nonce_order=NONCE_ORDER_HENDRIX,
    )


def _lease(plan: SearchPlan) -> NonceLease:
    return NonceLease(
        lease_id=plan.plan_id,
        generation=plan.generation,
        plan_id=plan.plan_id,
        start=plan.base_step,
        count=plan.window,
    )


def _runtime_config_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "chronus"
        / "mla1517_platform"
        / "python"
        / "runtime_config.py"
    )
    spec = importlib.util.spec_from_file_location("chronus_runtime_config_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_coordinator_selects_vendor_neutral_chronus_batch_for_canonical_search():
    coordinator = PythiaProductionMiningCoordinator.__new__(
        PythiaProductionMiningCoordinator
    )
    coordinator.execution_hasher = _ChronusBatchHasher("cuda")

    assert coordinator._pythia_batch_route() == "chronus_batch"


def test_chronus_batch_executes_exact_600_vertex_itinerary_without_vendor_route_name():
    hasher = _ChronusBatchHasher("cuda")
    precompute = precompute_pythia_search()
    plan = _plan()
    router = ProductionExecutionRouter(
        hasher,
        lambda _header, _target, _start, count: (None, None, count),
        pythia_precompute=precompute,
    )

    record, candidate = router.execute_plan(
        plan,
        HEADER,
        bytes(32),
        lease=_lease(plan),
    )

    expected = pythia_hendrix_nonces(
        HEADER,
        BASE,
        WINDOW,
        precompute=precompute,
        preferred_face=plan.preferred_face,
    )
    assert candidate is None
    assert record.completion_state is CompletionState.COMPLETE
    assert record.requested_route == "chronus_batch"
    assert record.executed_route == "chronus_batch"
    assert record.requested_nonce_order == NONCE_ORDER_HENDRIX
    assert record.executed_nonce_order == NONCE_ORDER_HENDRIX
    assert record.device_backend == "cuda"
    assert record.evidence_class is EvidenceClass.HARDWARE_EXECUTED
    assert record.kernel_identity == f"chronus_ordered_batch_v1:{SEARCH_ARCHITECTURE_ID}"
    assert record.hash_count == WINDOW
    assert record.completed_work_items == WINDOW
    assert hasher.seen == expected
    assert sorted(hasher.seen) == list(range(BASE, BASE + WINDOW))


def test_pythia_router_reaches_promoted_h4_fabric_and_preserves_ordered_membership():
    worker = _FabricScheduler()
    hasher = promote_execution_hasher(
        SuperAsicHasher(HybridCoordinator(worker), [worker])
    )
    precompute = precompute_pythia_search()
    plan = replace(
        _plan(),
        window=24,
        dispatch_breadth=24,
        plan_id="plan-chronus-h4-seam",
    )
    router = ProductionExecutionRouter(
        hasher,
        lambda _header, _target, _start, count: (None, None, count),
        pythia_precompute=precompute,
    )

    record, candidate = router.execute_plan(
        plan,
        HEADER,
        bytes(32),
        lease=_lease(plan),
    )

    expected = pythia_hendrix_nonces(
        HEADER,
        BASE,
        plan.window,
        precompute=precompute,
        preferred_face=plan.preferred_face,
    )
    dispatched = []
    for window in worker.dispatched:
        dispatched.extend(range(window.base_nonce, window.base_nonce + window.span))

    assert candidate is None
    assert record.completion_state is CompletionState.COMPLETE
    assert record.executed_route == "chronus_batch"
    assert record.hash_count == plan.window
    assert dispatched == expected

    evidence = hasher.last_batch_evidence
    assert evidence is not None
    assert evidence["h4_topology_observed"] is True
    assert evidence["completed_work_items"] == plan.window
    assert evidence["physical_fanout_observed"] is False

    fabric = chronus_fabric_execution_state_for(hasher)
    assert fabric["capability_bound"] is True
    assert fabric["physical_fanout"] is False
    assert fabric["execution_evidence"]["ordered_nonce_count"] == plan.window


def test_refused_plan_clears_prior_h4_execution_evidence():
    worker = _FabricScheduler()
    hasher = promote_execution_hasher(
        SuperAsicHasher(HybridCoordinator(worker), [worker])
    )
    hasher.last_batch_evidence = {
        "schema": "chronus.h4_600_ordered_batch/1",
        "physical_fanout_observed": True,
        "completion_state": "COMPLETE",
    }
    precompute = precompute_pythia_search()
    plan = _plan()
    invalid_lease = NonceLease(
        lease_id="wrong-lease",
        generation=plan.generation,
        plan_id="wrong-plan",
        start=plan.base_step,
        count=plan.window,
    )
    router = ProductionExecutionRouter(
        hasher,
        lambda _header, _target, _start, count: (None, None, count),
        pythia_precompute=precompute,
    )

    record, candidate = router.execute_plan(
        plan,
        HEADER,
        bytes(32),
        lease=invalid_lease,
    )

    assert candidate is None
    assert record.completion_state is CompletionState.REFUSED
    assert hasher.last_batch_evidence is None
    fabric = chronus_fabric_execution_state_for(hasher)
    assert fabric["physical_fanout"] is False
    assert fabric["physical_fanout_observed"] is False
    assert fabric["execution_evidence"] == "Unavailable"


def test_missing_batch_contract_falls_back_explicitly_without_relabelling():
    visited: list[int] = []
    plan = _plan()
    precompute = precompute_pythia_search()

    def cpu_nonces(_header, _target, nonces):
        batch = [int(nonce) for nonce in nonces]
        visited.extend(batch)
        return None, None, len(batch)

    router = ProductionExecutionRouter(
        _NoBatchHasher(),
        lambda _header, _target, _start, count: (None, None, count),
        cpu_nonce_executor=cpu_nonces,
        pythia_precompute=precompute,
    )
    record, candidate = router.execute_plan(
        plan,
        HEADER,
        bytes(32),
        lease=_lease(plan),
    )

    assert candidate is None
    assert record.completion_state is CompletionState.FALLBACK_COMPLETE
    assert record.requested_route == "chronus_batch"
    assert record.executed_route == "cpu_reference"
    assert record.fallback_reason == "CHRONUS_BATCH_UNAVAILABLE"
    assert record.evidence_class is EvidenceClass.SOFTWARE_VERIFIED
    assert visited == pythia_hendrix_nonces(
        HEADER,
        BASE,
        WINDOW,
        precompute=precompute,
        preferred_face=plan.preferred_face,
    )


def test_plan_binding_declares_chronus_authority_not_vendor_runtime():
    coordinator = PythiaProductionMiningCoordinator.__new__(
        PythiaProductionMiningCoordinator
    )
    coordinator._nonce_order = NONCE_ORDER_HENDRIX
    coordinator.geodesic_enabled = True
    coordinator.last_mining_decision = None
    coordinator._chronus_fabric_state = {
        "schema": "pythia.chronus_search_fabric/3",
        "state": "NOT_BOUND",
        "logical_vertices": 600,
    }
    coordinator.execution_hasher = _ChronusBatchHasher("metal")
    coordinator._chronus_fabric_state = chronus_fabric_state_for(
        coordinator.execution_hasher
    )
    coordinator.pythia_search_precompute = precompute_pythia_search()

    plan = coordinator._bind_plan_execution_intent(_plan("cpu_reference"))

    assert plan.executor_route == "chronus_batch"
    intent = plan.evidence_refs["technology_intent"]
    assert intent["composition_root"] == "PYTHIA"
    assert intent["execution_authority"] == "CHRONUS"
    assert intent["execution_contract"] == "chronus_batch"
    assert intent["dual_vertices"] == 600
    assert "cuda" not in intent["execution_contract"].lower()
    assert "opencl" not in intent["execution_contract"].lower()
    assert "metal" not in intent["execution_contract"].lower()


def test_runtime_configuration_accepts_10_eh_target_but_not_above_it():
    runtime_config = _runtime_config_module()
    assert runtime_config.HASHRATE_CEILING_HS == 1e19

    cfg = runtime_config.default_config()
    cfg["hashrate"]["target_hs"] = 1e19
    accepted = runtime_config.validate(cfg)
    assert accepted["hashrate"]["target_hs"] == 1e19
    assert accepted["hashrate"]["ceiling_hs"] == 1e19

    cfg = runtime_config.default_config()
    cfg["hashrate"]["target_hs"] = 1e19 + 1e18
    try:
        runtime_config.validate(cfg)
    except ValueError as exc:
        assert "10 EH/s ceiling" in str(exc)
    else:
        raise AssertionError("target above the governed 10 EH/s ceiling was accepted")
