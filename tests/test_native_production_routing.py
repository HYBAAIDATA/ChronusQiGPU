"""Production routing proofs for native CUDA/Metal mining lanes.

These are software-contract tests. They prove that a capability-proven native
hasher reaches its real M32 method through the canonical production router,
that its physical backend remains labelled ``cuda``/``metal``, and that the
production router executes plan-bound intent. They do not claim physical GPU
deployment evidence; the fake native hasher only exercises the software
contract.
"""

from __future__ import annotations

import hashlib
import time

import pytest

from chronus.mla1517.mining.execution_router import (
    NONCE_ORDER_HENDRIX,
    NONCE_ORDER_M32,
)
from chronus.mla1517.mining.geodesic_support import (
    PythiaProductionMiningCoordinator,
    ProductionExecutionRouter,
)
from chronus.mla1517.mining.pythia_search import (
    SEARCH_ARCHITECTURE_ID,
    precompute_pythia_search,
)
from chronus.mla1517.mining.search_plan import (
    CompletionState,
    EvidenceClass,
    NonceLease,
    SearchPlan,
)


def _sha256d(header: bytes, nonce: int) -> bytes:
    blob = header[:76] + int(nonce).to_bytes(4, "little")
    return hashlib.sha256(hashlib.sha256(blob).digest()).digest()


class _NativeHasher:
    vendor = "test"
    device = "contract-device"
    grind_batch = 64
    m32_window_max = 64
    kernel_ms = 0.0
    launches = 0
    hendrix_on_device = False

    def __init__(self, backend: str) -> None:
        self.backend = backend
        self.calls = []
        self.kernel_ms = 0.0
        self.launches = 0

    def grind_target_m32(self, header, target_be, base_nonce, lane_order, count):
        self.calls.append(("m32", base_nonce, count, tuple(lane_order)))
        self.launches += 1
        self.kernel_ms += 0.25
        nonce = (int(base_nonce) + int(lane_order[0])) & 0xFFFFFFFF
        return nonce, _sha256d(header, nonce), int(count)

    def grind_target_range(self, header, target_be, base_nonce, count):
        self.calls.append(("range", base_nonce, count))
        self.launches += 1
        self.kernel_ms += 0.25
        nonce = int(base_nonce) & 0xFFFFFFFF
        return nonce, _sha256d(header, nonce), int(count)

    def grind_target_gold(self, header, target_be, count, seed=None):
        raise AssertionError("gold route is not expected in this proof")


def _plan(
    route: str = "opencl_m32",
    *,
    nonce_order: str = NONCE_ORDER_M32,
    evidence_refs=None,
) -> SearchPlan:
    return SearchPlan(
        job_fingerprint="fp-native-production",
        pool_session_id="session-native-production",
        generation=1,
        base_step=0,
        window=32,
        extranonce2="00000000",
        lane_order=tuple(range(32)),
        preferred_face=0,
        dispatch_breadth=32,
        executor_route=route,
        policy_id="native-production-proof",
        evidence_refs={} if evidence_refs is None else evidence_refs,
        created_at=time.monotonic(),
        plan_id="plan-native-production",
        nonce_order=nonce_order,
    )


def _lease(plan: SearchPlan) -> NonceLease:
    return NonceLease(
        lease_id=plan.plan_id,
        generation=plan.generation,
        plan_id=plan.plan_id,
        start=plan.base_step,
        count=plan.window,
    )


@pytest.mark.parametrize("backend", ["cuda", "metal"])
def test_canonical_coordinator_classifies_native_backend_as_device_route(backend):
    coordinator = PythiaProductionMiningCoordinator.__new__(
        PythiaProductionMiningCoordinator
    )
    coordinator.execution_hasher = _NativeHasher(backend)
    coordinator._nonce_order = NONCE_ORDER_M32

    assert coordinator._execution_route() == "opencl_m32"


@pytest.mark.parametrize("backend", ["cuda", "metal"])
def test_native_m32_executes_on_native_hasher_without_cpu_substitution(backend):
    hasher = _NativeHasher(backend)

    def forbidden_cpu(*_args):
        raise AssertionError("native route silently substituted CPU execution")

    plan = _plan()
    router = ProductionExecutionRouter(hasher, forbidden_cpu)
    record, candidate = router.execute_plan(
        plan,
        bytes(80),
        b"\xff" * 32,
        lease=_lease(plan),
    )

    assert hasher.calls == [("m32", 0, 32, tuple(range(32)))]
    assert candidate is not None
    assert candidate["nonce"] == 0
    assert candidate["independently_rechecked"] is True
    assert record.requested_route == "opencl_m32"
    assert record.executed_route == "opencl_m32"
    assert record.device_backend == backend
    assert record.kernel_identity == (
        f"chronus_native_sha256d:{backend}:opencl_m32"
    )
    assert record.kernel_build_status == (
        "native_method_bound_after_backend_self_check"
    )
    assert record.kernel_launch_count == 1
    assert record.kernel_ms == pytest.approx(0.25)
    assert record.completion_state is CompletionState.EARLY_WINNER
    assert record.evidence_class is EvidenceClass.HARDWARE_EXECUTED


@pytest.mark.parametrize("backend", ["cuda", "metal"])
def test_native_route_markers_are_bound_to_real_callable_methods(backend):
    hasher = _NativeHasher(backend)
    assert not hasattr(hasher, "k_m32")
    ProductionExecutionRouter(hasher, lambda *_args: (None, None, 0))
    assert hasher.k_m32 == hasher.grind_target_m32
    assert hasher.k_range == hasher.grind_target_range
    assert hasher.k_gold == hasher.grind_target_gold


def test_pythia_explicit_batch_certifies_hendrix_even_without_device_hendrix_kernel():
    coordinator = PythiaProductionMiningCoordinator.__new__(
        PythiaProductionMiningCoordinator
    )
    coordinator.execution_hasher = _NativeHasher("cuda")
    coordinator._nonce_order = NONCE_ORDER_HENDRIX

    plan = _plan(
        nonce_order=NONCE_ORDER_HENDRIX,
        evidence_refs={"search_architecture": SEARCH_ARCHITECTURE_ID},
    )

    assert coordinator._effective_nonce_order(plan) == NONCE_ORDER_HENDRIX


def test_non_native_hasher_does_not_receive_synthetic_capabilities():
    hasher = _NativeHasher("cpu")
    ProductionExecutionRouter(hasher, lambda *_args: (None, None, 0))
    assert not hasattr(hasher, "k_m32")
    assert not hasattr(hasher, "k_range")
    assert not hasattr(hasher, "k_gold")


def test_production_router_executes_plan_bound_nonce_order_not_injected_callback():
    class CpuHasher:
        backend = "cpu"
        device = "CPU"
        vendor = None
        grind_batch = 64
        launches = 0
        kernel_ms = 0.0
        k_gold = k_m32 = k_range = None

    plan = _plan("cpu_reference", nonce_order=NONCE_ORDER_HENDRIX)
    router = ProductionExecutionRouter(
        CpuHasher(),
        lambda header, target, start, count: (None, None, count),
        nonce_order=lambda _plan: NONCE_ORDER_M32,
    )
    record, _candidate = router.execute_plan(
        plan,
        bytes(80),
        bytes(32),
        lease=_lease(plan),
    )

    assert record.requested_nonce_order == NONCE_ORDER_HENDRIX
    assert record.executed_nonce_order == NONCE_ORDER_HENDRIX


def test_search_plan_refuses_unknown_nonce_order():
    with pytest.raises(ValueError, match="unsupported nonce_order"):
        _plan(nonce_order="invented-order")


def test_coordinator_binds_canonical_search_and_workforce_intent_into_plan():
    coordinator = PythiaProductionMiningCoordinator.__new__(
        PythiaProductionMiningCoordinator
    )
    coordinator._nonce_order = NONCE_ORDER_HENDRIX
    coordinator.last_mining_decision = None
    coordinator._chronus_fabric_state = {
        "schema": "pythia.chronus_search_fabric/2",
        "state": "NOT_BOUND",
        "logical_vertices": 600,
    }
    coordinator.execution_hasher = _NativeHasher("cpu")
    coordinator.pythia_search_precompute = precompute_pythia_search()

    plan = coordinator._bind_plan_execution_intent(_plan())

    # Hendrix is the immutable production search algorithm. The structural
    # architecture is supporting evidence, not a replacement search identity.
    assert plan.nonce_order == NONCE_ORDER_HENDRIX
    assert plan.evidence_refs["search_algorithm"] == NONCE_ORDER_HENDRIX
    assert plan.evidence_refs["search_architecture"] == SEARCH_ARCHITECTURE_ID
    assert plan.evidence_refs["search_precompute_digest"] == (
        coordinator.pythia_search_precompute.digest
    )
    assert plan.evidence_refs["configured_traversal_refinement"] == (
        NONCE_ORDER_HENDRIX
    )
    intent = plan.evidence_refs["technology_intent"]
    assert intent["composition_root"] == "PYTHIA"
    assert intent["dual_vertices"] == 600
    assert intent["hilbert_space"] == "11_qubits_C^2048"
    assert intent["proof_authority"] == (
        "sha256d_target_freshness_and_literal_pool_response_only"
    )
