"""Production routing proofs for native CUDA/Metal mining lanes.

These are software-contract tests. They prove that a capability-proven native
hasher reaches its real M32 method through the canonical production router and
that its physical backend remains labelled ``cuda``/``metal``. They do not
claim physical GPU execution; that remains a deployment evidence gate.
"""

from __future__ import annotations

import hashlib
import time

import pytest

from chronus.mla1517.mining.geodesic_support import ProductionExecutionRouter
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

    def grind_target_m32(self, header, target_be, base_nonce, lane_order, count):
        self.calls.append(("m32", base_nonce, count, tuple(lane_order)))
        self.launches += 1
        self.kernel_ms += 0.25
        # Max target means the first probe is valid. Return a real SHA256d so
        # the router's independent host recheck remains active in this test.
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


def _plan(route: str = "opencl_m32") -> SearchPlan:
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
        evidence_refs={},
        created_at=time.monotonic(),
        plan_id="plan-native-production",
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
    assert record.requested_route == "opencl_m32"  # historical route token
    assert record.executed_route == "opencl_m32"
    assert record.device_backend == backend
    assert record.kernel_launch_count == 1
    assert record.kernel_ms == pytest.approx(0.25)
    assert record.completion_state is CompletionState.EARLY_WINNER
    # The current evidence schema only permits HARDWARE_EXECUTED for its
    # OpenCL/remote/ASIC set. Native physical proof is therefore deliberately
    # under-claimed until that schema is generalized.
    assert record.evidence_class is EvidenceClass.SOFTWARE_VERIFIED


@pytest.mark.parametrize("backend", ["cuda", "metal"])
def test_native_route_markers_are_bound_to_real_callable_methods(backend):
    hasher = _NativeHasher(backend)
    assert not hasattr(hasher, "k_m32")
    ProductionExecutionRouter(hasher, lambda *_args: (None, None, 0))
    assert hasher.k_m32 == hasher.grind_target_m32
    assert hasher.k_range == hasher.grind_target_range
    assert hasher.k_gold == hasher.grind_target_gold


def test_non_native_hasher_does_not_receive_synthetic_capabilities():
    hasher = _NativeHasher("cpu")
    ProductionExecutionRouter(hasher, lambda *_args: (None, None, 0))
    assert not hasattr(hasher, "k_m32")
    assert not hasattr(hasher, "k_range")
    assert not hasattr(hasher, "k_gold")
