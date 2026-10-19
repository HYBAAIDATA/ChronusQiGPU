"""PYTHIA production router -> Chronus Virtual iGPU (local deterministic inputs, no live pool).

Complements the scripted-pool coordinator test in
``chronus/mla1517_platform/python/test_chronus_vigpu_production_route.py``.
"""

from __future__ import annotations

import hashlib
import json
import os
import time

import pytest

from chronus.reference_contract import reference_execution
from chronus.mla1517.mining.backend_registry import BackendLane, BackendRegistry
from chronus.mla1517.mining.execution_router import NONCE_ORDER_HENDRIX
from chronus.mla1517.mining.exact_search import (
    SEARCH_ARCHITECTURE_ID,
    exact_face_order,
    exact_reference_nonces,
    precompute_exact_search,
)
from chronus.mla1517.mining.geodesic_support import ProductionExecutionRouter
from chronus.mla1517.mining.resident_search import compile_hendrix_plan
from dataclasses import replace

from chronus.mla1517.mining.search_plan import (
    CompletionState,
    EvidenceClass,
    NonceLease,
    SearchPlan,
)
from chronus.virtual_igpu.adapters import CPUEmulatorAdapter
from chronus.virtual_igpu.client import ChronusClient
from chronus.virtual_igpu.mining_hasher import ChronusVirtualIGPUHasher
from chronus.virtual_igpu.runtime import RuntimeDaemon

HEADER = bytes(range(80))
BASE = 0x0020_0000
WINDOW = 1200


@pytest.fixture(scope="module")
def precompute():
    return precompute_exact_search()


def _plan(state) -> SearchPlan:
    lane_order = exact_face_order(HEADER, state)
    return SearchPlan(
        job_fingerprint="fp-vigpu-route",
        pool_session_id="session-vigpu-route",
        generation=1,
        base_step=BASE,
        window=WINDOW,
        extranonce2="00000000",
        lane_order=lane_order,
        preferred_face=lane_order[0],
        dispatch_breadth=WINDOW,
        executor_route="chronus_batch",
        policy_id="canonical-600",
        evidence_refs={
            "search_architecture": SEARCH_ARCHITECTURE_ID,
            "search_precompute_digest": state.digest,
        },
        created_at=time.monotonic(),
        plan_id="plan-vigpu-route",
        nonce_order=NONCE_ORDER_HENDRIX,
    )


def _sealed(plan: SearchPlan, header: bytes, target_le: bytes, state) -> SearchPlan:
    artifact = compile_hendrix_plan(plan, header, bytes(target_le)[::-1], state)
    bound = replace(
        plan,
        evidence_refs={**plan.evidence_refs, "resident_hendrix": artifact.as_dict()},
    )
    artifact.require_context(bound, header, bytes(target_le)[::-1])
    return bound


def _lease(plan: SearchPlan) -> NonceLease:
    return NonceLease(
        lease_id=plan.plan_id,
        generation=plan.generation,
        plan_id=plan.plan_id,
        start=plan.base_step,
        count=plan.window,
    )


def _router(hasher, precompute) -> ProductionExecutionRouter:
    def cpu(header, target_le, start, count):  # independent software oracle, unused on this route
        raise AssertionError("cpu oracle must not execute the chronus_batch route")

    return ProductionExecutionRouter(hasher, cpu, pythia_precompute=precompute)


def _target_le(nonce: int) -> bytes:
    """Target admitting exactly one probe: the digest of ``nonce``."""
    digest = hashlib.sha256(
        hashlib.sha256(HEADER[:76] + nonce.to_bytes(4, "little")).digest()
    ).digest()
    return digest  # little-endian target == that digest's integer value


def test_registry_binds_chronus_lane_only_by_explicit_request() -> None:
    registry = BackendRegistry()
    selection = registry.select("chronus")
    assert selection.lane == "chronus" and selection.fallback is False
    assert isinstance(selection.hasher, ChronusVirtualIGPUHasher)
    assert (
        BackendLane.CHRONUS
        not in __import__(
            "chronus.mla1517.mining.backend_registry", fromlist=["_POLICY_ORDER"]
        )._POLICY_ORDER["auto"]
    )


def test_plan_executes_through_chronus_and_returns_a_host_verified_candidate(precompute) -> None:
    hasher = BackendRegistry().select("chronus").hasher
    draft = _plan(precompute)
    order = exact_reference_nonces(
        HEADER, BASE, WINDOW, preferred_face=draft.preferred_face
    )
    target_le = _target_le(order[700])
    plan = _sealed(draft, HEADER, target_le, precompute)
    limit = int.from_bytes(target_le, "little")

    def digest_int(nonce: int) -> int:
        blob = HEADER[:76] + nonce.to_bytes(4, "little")
        return int.from_bytes(hashlib.sha256(hashlib.sha256(blob).digest()).digest(), "little")

    # Independent expectation: the first nonce in Hendrix probe order at or under the target.
    index = next(i for i, n in enumerate(order) if digest_int(n) <= limit)
    winner = order[index]
    record, candidate = _router(hasher, precompute).execute_plan(plan, HEADER, target_le, lease=_lease(plan))
    assert candidate is not None and candidate["nonce"] == winner
    assert candidate["independently_rechecked"] is True
    assert record.completion_state is CompletionState.EARLY_WINNER
    assert record.locally_valid_shares == 1
    assert record.requested_route == record.executed_route == "chronus_batch"
    assert record.device_backend == "chronus_vigpu"
    assert record.hash_count == index + 1
    # Software emulator: verified software execution, never hardware evidence.
    assert record.evidence_class is EvidenceClass.SOFTWARE_VERIFIED
    assert hasher.launches >= 1
    assert hasher.last_result["receipt"]["actual_backend"] == "cpu-emulator"
    assert hasher.last_verification["status"] == "passed"


def test_complete_window_without_candidate_counts_every_nonce(precompute) -> None:
    hasher = BackendRegistry().select("chronus").hasher
    plan = _sealed(_plan(precompute), HEADER, bytes(32), precompute)
    record, candidate = _router(hasher, precompute).execute_plan(plan, HEADER, bytes(32), lease=_lease(plan))
    assert candidate is None
    assert record.completion_state is CompletionState.COMPLETE
    assert record.hash_count == WINDOW and record.completed_work_items == WINDOW


class _LyingAdapter(CPUEmulatorAdapter):
    def _sha256d_scan(self, workload, value, started):
        first = value["nonces"][0]
        return self._result(
            workload,
            {"hits": [{"nonce": first, "hash_hex": "00" * 32}], "checked": 1, "engine": "forged"},
            started,
        )


def test_lying_adapter_is_a_device_error_and_never_a_candidate(tmp_path, precompute) -> None:
    daemon = RuntimeDaemon(adapters=[_LyingAdapter()], store_dir=tmp_path / "rt")
    hasher = ChronusVirtualIGPUHasher(client=ChronusClient(daemon=daemon))
    plan = _sealed(_plan(precompute), HEADER, b"\xff" * 32, precompute)
    record, candidate = _router(hasher, precompute).execute_plan(plan, HEADER, b"\xff" * 32, lease=_lease(plan))
    assert candidate is None
    assert record.completion_state is CompletionState.DEVICE_ERROR
    assert record.locally_valid_shares == 0
    assert "verification_failed" in str(record.device_error) or "mismatch" in str(
        record.device_error
    )


def test_missing_chronus_lane_fails_closed(monkeypatch) -> None:
    import chronus.mla1517.mining.backend_registry as reg

    def unavailable():
        return reg.LaneProbe("chronus", False, None, None, 0.0, "no runtime")

    registry = BackendRegistry(probes={BackendLane.CHRONUS: unavailable})
    with pytest.raises(reg.BackendUnavailable, match="no runtime"):
        registry.select("chronus")
