"""Focused proofs for PYTHIA's precomputed production search architecture."""

from __future__ import annotations

import hashlib
import time

from chronus.mla1517.mining.execution_router import NONCE_ORDER_HENDRIX
from chronus.mla1517.mining.geodesic_support import ProductionExecutionRouter
from chronus.mla1517.mining.pythia_search import (
    DUAL_VERTEX_COUNT,
    HILBERT_DIM,
    HILBERT_WALK_HORIZON,
    SEARCH_ARCHITECTURE_ID,
    precompute_pythia_search,
    pythia_hendrix_nonces,
    pythia_hilbert_600_nonces,
    vertex_itinerary,
)
from chronus.mla1517.mining.search_plan import EvidenceClass, NonceLease, SearchPlan


def _sha256d(header: bytes, nonce: int) -> bytes:
    blob = header[:76] + int(nonce).to_bytes(4, "little")
    return hashlib.sha256(hashlib.sha256(blob).digest()).digest()


def _plan(window: int = 1200) -> SearchPlan:
    state = precompute_pythia_search()
    return SearchPlan(
        job_fingerprint="fp-pythia-600",
        pool_session_id="session-pythia-600",
        generation=1,
        base_step=1000,
        window=window,
        extranonce2="00000000",
        lane_order=tuple(range(32)),
        preferred_face=0,
        dispatch_breadth=32,
        executor_route="opencl_m32",
        policy_id="pythia-600-proof",
        evidence_refs={
            "search_architecture": SEARCH_ARCHITECTURE_ID,
            "search_precompute_digest": state.digest,
        },
        created_at=time.monotonic(),
        plan_id="plan-pythia-600",
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


def test_precompute_builds_full_dual32_11d_600_vertex_hilbert_lattice():
    state = precompute_pythia_search()
    summary = state.summary()

    assert summary["state"] == "READY"
    assert summary["prepared_before_pool_work"] is True
    assert summary["coarse_dual_faces"] == 32
    assert summary["dual_vertices"] == 600
    assert summary["dual_edges"] == 1200
    assert summary["manifold_dimension"] == 11
    assert summary["hilbert_qubits"] == 11
    assert summary["hilbert_dimension"] == HILBERT_DIM == 2048
    assert summary["hilbert_addresses"] == DUAL_VERTEX_COUNT == 600
    assert summary["hilbert_walk"] == "turing_exact_coined_cycle"
    assert summary["hilbert_walk_horizon"] == HILBERT_WALK_HORIZON == 300
    assert summary["hilbert_walk_positions_reached"] == 600
    assert len(summary["hilbert_walk_digest"]) == 64
    assert summary["all_coarse_faces_occupied"] is True
    assert len(set(state.hilbert_basis)) == 600
    assert max(state.hilbert_basis) < HILBERT_DIM
    assert state.hilbert_walk_rank[0] == 0
    assert set(state.hilbert_walk_rank) == set(range(600))
    assert all(len(neighbours) == 4 for neighbours in state.adjacency)


def test_itinerary_visits_every_dual_vertex_once_and_is_job_deterministic():
    header = bytes(range(80))
    first = vertex_itinerary(header)
    second = vertex_itinerary(header)

    assert first == second
    assert len(first) == 600
    assert set(first) == set(range(600))

    changed = bytearray(header)
    changed[0] ^= 0x01
    other = vertex_itinerary(bytes(changed))
    assert set(other) == set(first)


def test_hendrix_is_default_traversal_over_complete_structured_itinerary():
    header = bytes(range(80))
    base = 4000
    window = 5000
    structural = pythia_hilbert_600_nonces(
        header,
        base,
        window,
        preferred_face=7,
    )
    canonical = pythia_hendrix_nonces(
        header,
        base,
        window,
        preferred_face=7,
    )

    from chronus.mla1517.mining.hendrix_order import hendrix_schedule

    schedule = hendrix_schedule(window)
    expected = [structural[schedule.nonce_at(index)] for index in range(window)]

    assert canonical == expected
    assert len(canonical) == window
    assert len(set(canonical)) == window
    assert set(canonical) == set(range(base, base + window))


def test_pythia_preferred_face_steers_start_without_pruning_vertices():
    header = bytes(range(80))
    state = precompute_pythia_search()
    face0 = vertex_itinerary(header, state, preferred_face=0)
    face31 = vertex_itinerary(header, state, preferred_face=31)

    assert len(face0) == len(face31) == 600
    assert set(face0) == set(face31) == set(range(600))
    assert state.coarse_anchor[face0[0]] == 0
    assert state.coarse_anchor[face31[0]] == 31
    assert face0 != face31


def test_nonce_schedule_is_exact_full_lease_permutation():
    header = bytes(range(80))
    base = 4000
    window = 5000
    order = pythia_hilbert_600_nonces(header, base, window, preferred_face=7)

    assert len(order) == window
    assert len(set(order)) == window
    assert min(order) == base
    assert max(order) == base + window - 1
    assert set(order) == set(range(base, base + window))
    assert pythia_hilbert_600_nonces(
        header,
        base,
        window,
        position=211,
        count=97,
        preferred_face=7,
    ) == order[211:308]


def test_workforce_manifest_places_pythia_at_mining_composition_root():
    workforce = precompute_pythia_search().workforce_manifest()

    assert workforce["composition_root"] == "PYTHIA"
    assert workforce["enterprise_orchestrator"] == "EUCLID"
    owners = {entry["role"]: entry["owner"] for entry in workforce["roles"]}
    assert owners["world_model_and_causal_intelligence"] == "PYTHIA"
    assert owners["agentic_search_planner"] == "AgenticMiningController"
    assert owners["hilbert_walk"] == "Turing"
    assert owners["physical_execution"] == "Chronus"
    assert owners["healing_and_optimisation"] == "Salamander"


class _BatchHasher:
    backend = "opencl:test"
    device = "contract-gpu"
    vendor = "test"
    grind_batch = 128
    m32_window_max = 128
    k_m32 = object()
    k_range = object()
    k_gold = object()
    hendrix_on_device = False

    def __init__(self):
        self.launches = 0
        self.kernel_ms = 0.0
        self.seen = []

    def grind_target_batch(self, header, target_be, nonces):
        values = [int(value) for value in nonces]
        self.seen.extend(values)
        self.launches += 1
        self.kernel_ms += 0.5
        if not values:
            return None, None, 0
        nonce = values[0]
        return nonce, _sha256d(header, nonce), len(values)


def test_canonical_itinerary_executes_as_explicit_nonce_batch_on_proven_device():
    header = bytes(80)
    hasher = _BatchHasher()
    plan = _plan(window=1200)
    expected = pythia_hendrix_nonces(
        header,
        plan.base_step,
        plan.window,
        precompute=precompute_pythia_search(),
        preferred_face=plan.preferred_face,
    )

    def forbidden_contiguous_cpu(*_args):
        raise AssertionError(
            "canonical 600-vertex search silently used contiguous CPU execution"
        )

    router = ProductionExecutionRouter(hasher, forbidden_contiguous_cpu)
    record, candidate = router.execute_plan(
        plan,
        header,
        b"\xff" * 32,
        lease=_lease(plan),
    )

    assert hasher.seen == expected[: hasher.grind_batch]
    assert candidate is not None
    assert candidate["nonce"] == expected[0]
    assert candidate["independently_rechecked"] is True
    assert record.requested_nonce_order == NONCE_ORDER_HENDRIX
    assert record.executed_nonce_order == NONCE_ORDER_HENDRIX
    assert record.kernel_identity.endswith(SEARCH_ARCHITECTURE_ID)
    assert record.kernel_launch_count == 1
    assert record.evidence_class is EvidenceClass.HARDWARE_EXECUTED
