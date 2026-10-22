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

from chronus.mla1517.mining.closed_loop import ClosedLoopOptimizer
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
)
from chronus.mla1517.mining.exact_search import (
    precompute_exact_search as precompute_pythia_search, exact_reference_nonces, exact_face_order,
)
from chronus.mla1517.mining.search_plan import (
    CompletionState,
    EvidenceClass,
    ExecutionRoute,
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

def _expected_nonces(header, base, window, *, precompute, preferred_face):
    # Independent exact reference, not the prohibited FP64 legacy itinerary.
    assert precompute.digest == precompute_pythia_search().digest
    return exact_reference_nonces(header, base, window, preferred_face=preferred_face)


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


def _plan(route: str = "chronus_batch", *, target=bytes(32), window=WINDOW, plan_id="plan-chronus-600") -> SearchPlan:
    from chronus.mla1517.mining.resident_search import compile_hendrix_plan
    state = precompute_pythia_search()
    lanes = exact_face_order(HEADER, state)
    plan = SearchPlan(
        job_fingerprint="fp-chronus-600",
        pool_session_id="session-chronus-600",
        generation=1,
        base_step=BASE,
        window=window,
        extranonce2="00000000",
        lane_order=lanes,
        preferred_face=lanes[0],
        dispatch_breadth=window,
        executor_route=route,
        policy_id="canonical-600",
        evidence_refs={"search_architecture": SEARCH_ARCHITECTURE_ID, "search_precompute_digest": state.digest},
        created_at=time.monotonic(),
        plan_id=plan_id,
        nonce_order=NONCE_ORDER_HENDRIX,
    )

    artifact = compile_hendrix_plan(plan, HEADER, target, state)
    return replace(plan, evidence_refs={**plan.evidence_refs, "resident_hendrix": artifact.as_dict()})


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

    expected = _expected_nonces(
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


def test_reference_only_h4_promoter_cannot_issue_production_execution():
    worker = _FabricScheduler()
    hasher = promote_execution_hasher(
        SuperAsicHasher(HybridCoordinator(worker), [worker])
    )
    precompute = precompute_pythia_search()
    plan = _plan(window=24, plan_id="plan-chronus-h4-seam")
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

    # The legacy H4 promoter is now explicitly reference-only. A production
    # router must refuse it, not manufacture a physical/native execution
    # receipt. Exact resident Chronus execution is covered by the other tests.
    assert candidate is None
    assert record.completion_state is CompletionState.DEVICE_ERROR
    assert "ReferenceUnavailable" in record.device_error
    assert record.hash_count == 0
    assert worker.dispatched == []
    evidence = hasher.last_batch_evidence
    assert evidence["completion_state"] == "DEVICE_ERROR"
    assert evidence["completed_work_items"] == 0
    assert evidence["physical_fanout_observed"] is False
    assert evidence["full_600_shard_dispatch_observed"] is False


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
    assert visited == _expected_nonces(
        HEADER,
        BASE,
        WINDOW,
        precompute=precompute,
        preferred_face=plan.preferred_face,
    )


def test_coordinator_bound_plan_requests_chronus_batch_and_falls_back_end_to_end():
    """A plan bound by the real coordinator requests ``chronus_batch`` even
    when the bound hasher cannot execute it.

    The fallback contract is owned by the router, not by plan construction:
    when ``grind_target_batch`` is unbound the record must carry
    ``requested_route=chronus_batch``, ``executed_route=cpu_reference`` and
    ``CHRONUS_BATCH_UNAVAILABLE`` end-to-end, instead of the plan silently
    requesting cpu_reference.
    """
    coordinator = PythiaProductionMiningCoordinator.__new__(
        PythiaProductionMiningCoordinator
    )
    coordinator._nonce_order = NONCE_ORDER_HENDRIX
    coordinator.geodesic_enabled = True
    coordinator.last_mining_decision = None
    coordinator.execution_hasher = _NoBatchHasher()
    coordinator._chronus_fabric_state = chronus_fabric_state_for(
        coordinator.execution_hasher
    )
    coordinator.pythia_search_precompute = precompute_pythia_search()
    from types import SimpleNamespace
    coordinator.client = SimpleNamespace(proof_adapter=SimpleNamespace(
        current_job=SimpleNamespace(job_id="fixture", ntime="00000000", target=0),
        build_header=lambda *args: HEADER,
    ))

    plan = coordinator._bind_plan_execution_intent(_plan("cpu_reference"))

    assert plan.executor_route == "chronus_batch"

    visited: list[int] = []

    def cpu_nonces(_header, _target, nonces):
        batch = [int(nonce) for nonce in nonces]
        visited.extend(batch)
        return None, None, len(batch)

    router = ProductionExecutionRouter(
        coordinator.execution_hasher,
        lambda _header, _target, _start, count: (None, None, count),
        cpu_nonce_executor=cpu_nonces,
        pythia_precompute=coordinator.pythia_search_precompute,
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
    assert visited == _expected_nonces(
        HEADER,
        BASE,
        WINDOW,
        precompute=coordinator.pythia_search_precompute,
        preferred_face=plan.preferred_face,
    )


def test_coordinator_bound_plan_executes_chronus_batch_when_capability_bound():
    """With a batch-capable Chronus lane bound, the same plan executes
    ``chronus_batch`` end-to-end: ``requested_route==executed_route`` with
    real backend provenance, Hendrix order preserved, work items counted.

    The Chronus virtual iGPU is the box-available capability-bound lane:
    its ``grind_target_batch`` submits real computed SHA256d batches whose
    hits are re-verified host-side, and its device string names the actual
    adapter — virtual-device execution, declared, never physical hardware.
    """
    from chronus.virtual_igpu.mining_hasher import ChronusVirtualIGPUHasher

    hasher = ChronusVirtualIGPUHasher()
    coordinator = PythiaProductionMiningCoordinator.__new__(
        PythiaProductionMiningCoordinator
    )
    coordinator._nonce_order = NONCE_ORDER_HENDRIX
    coordinator.geodesic_enabled = True
    coordinator.last_mining_decision = None
    coordinator.execution_hasher = hasher
    coordinator._chronus_fabric_state = chronus_fabric_state_for(hasher)
    coordinator.pythia_search_precompute = precompute_pythia_search()
    from types import SimpleNamespace
    coordinator.client = SimpleNamespace(proof_adapter=SimpleNamespace(
        current_job=SimpleNamespace(job_id="fixture", ntime="00000000", target=(1 << 256) - 1),
        build_header=lambda *args: HEADER,
    ))

    plan = coordinator._bind_plan_execution_intent(_plan("cpu_reference"))
    assert plan.executor_route == "chronus_batch"

    router = ProductionExecutionRouter(
        hasher,
        lambda _header, _target, _start, count: (None, None, count),
        pythia_precompute=coordinator.pythia_search_precompute,
    )
    record, candidate = router.execute_plan(
        plan,
        HEADER,
        b"\xff" * 32,  # every Hendrix nonce meets this target
        lease=_lease(plan),
    )

    order = _expected_nonces(
        HEADER,
        BASE,
        WINDOW,
        precompute=coordinator.pythia_search_precompute,
        preferred_face=plan.preferred_face,
    )
    assert candidate is not None
    assert candidate["nonce"] == order[0]
    assert candidate["independently_rechecked"] is True
    assert record.requested_route == "chronus_batch"
    assert record.executed_route == "chronus_batch"
    assert record.fallback_reason is None
    assert record.device_backend == "chronus_vigpu"
    assert record.kernel_identity == (
        f"chronus_ordered_batch_v1:{SEARCH_ARCHITECTURE_ID}"
    )
    assert record.completed_work_items > 0
    assert record.executed_nonce_order == NONCE_ORDER_HENDRIX


def test_chronus_requested_fallback_observations_feed_executed_route_model():
    """A chronus_batch request that falls back to cpu_reference must feed the
    executed route's measured window model.

    The closed-loop optimizer keys baselines/trials by route: the coordinator
    calls ``select`` with the capability route the plan executes under, so
    observations must land under ``executed_route`` — not ``requested_route``.
    Filing fallback records under chronus_batch starves the cpu_reference
    baseline (``route_matched`` stays False by design: a fallback must not
    contaminate the requested route's rate model), ``select`` can never start
    a bounded trial, and the mining window pins at its minimum forever. This
    pinned the canonical loopback at 96 nonces/window so no share was ever
    found.
    """
    optimizer = ClosedLoopOptimizer(
        evidence_source="completed production ExecutionRecord"
    )
    requested = ExecutionRoute.chronus_batch.value
    executed = "cpu_reference"
    # select() runs every cycle and adopts the first proposed window as the
    # active one; observe() only counts samples at the active window.
    assert optimizer.select(route=executed, proposed_window=96) == 96
    # Same argument contract as MiningCoordinator._record_execution.
    for _ in range(optimizer.min_samples):
        optimizer.observe(
            route=executed or requested,
            executed_route=executed,
            planned_window=96,
            completed_work=96,
            elapsed_seconds=1.0,
            completion_state=CompletionState.FALLBACK_COMPLETE.value,
            device_error=None,
        )
    key = optimizer._key(executed, 96)
    assert len(optimizer.samples[key]) == optimizer.min_samples
    assert requested not in {
        route_key.split(":", 1)[0] for route_key in optimizer.samples
    }
    # With an eligible baseline a bounded trial may scale the window up;
    # before the executed-route keying it stayed pinned at 96.
    assert optimizer.select(route=executed, proposed_window=192) == 192
    assert optimizer.trial is not None
    assert optimizer.trial["route"] == executed
    assert optimizer.trial["candidate"] == 192


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
    from types import SimpleNamespace
    coordinator.client = SimpleNamespace(proof_adapter=SimpleNamespace(
        current_job=SimpleNamespace(job_id="fixture", ntime="00000000", target=0),
        build_header=lambda *args: HEADER,
    ))
    coordinator._chronus_fabric_state = {
        "schema": "pythia.chronus_search_fabric/2",
        "state": "NOT_BOUND",
        "logical_vertices": 600,
    }

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
