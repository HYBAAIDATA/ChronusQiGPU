"""Tests for 600-lane geometry bijection, mother-tensor, and proof verification.

Phase P3 unit test suite:
- 600-vertex dodecahedron ⊕ icosahedron overlay lifted to 11D
- Hendrix Grover-derivative order (clamped <= 2^20)
- Leased window W partitioned into 600 disjoint chunks (100% complete, 0% overlap)
- Unique vertex ownership per lane
- PartitionProof600 self-verifying certificate
- Host double-SHA256 recheck
- KelloggMotherTensor [600 × 8 × chunksize × 11D]
- Yang-Mills gauge symmetry (variance = 0)
- Pillar contraction reproducing {phi_method, xor_0.5625, kappa_trace} with <= 8 steps
- SearchPlan collapse
- Re-export shims across kellogg, kellogg.canonical_tensor, and tensor.canonical_tensor
"""

import math
import pytest

from chronus.exact_geometry import (
    EstateChunk600,
    ExactRay,
    PartitionProof600,
    build_600_partition,
    dodeca_overlay_icosa,
    embed_11d_exact,
    hendrix_grover_order,
)
from chronus.mla1517.mining.search_plan import PlanSource, SearchPlan, WorkIdentity
from kellogg.ansatz_v3 import (
    ANSATZ_V3,
    FUTURES,
    LANES,
    SEEDS,
    AnsatzV3,
    RicciReconciliationTrace,
    load_ansatz,
)
from kellogg.mother_tensor import (
    KelloggMotherTensor,
    PillarContractionResult,
    kellogg_state_600,
)


def test_dodeca_overlay_icosa_vertex_count():
    rays = dodeca_overlay_icosa()
    assert len(rays) == 600
    assert all(isinstance(r, ExactRay) for r in rays)
    assert all(r.is_unit() for r in rays)


def test_embed_11d_exact():
    rays = dodeca_overlay_icosa()
    coords11 = embed_11d_exact(rays[:10])
    assert len(coords11) == 10
    for r in coords11:
        assert len(r.numerator) == 11
        assert r.in_phi_ball() is True



@pytest.mark.parametrize("seed", SEEDS)
def test_hendrix_grover_order_permutation(seed: int):
    order = hendrix_grover_order(seed)
    assert len(order) == 600
    assert len(set(order)) == 600
    assert min(order) == 0
    assert max(order) == 599


def test_hendrix_grover_order_clamped():
    # Verify materialisation bound <= 2^20
    order = hendrix_grover_order(1337)
    assert len(order) <= (1 << 20)


@pytest.mark.parametrize("window", [600, 3000, 19200, 60000])
@pytest.mark.parametrize("seed", [1337, 42])
def test_build_600_partition_complete_and_disjoint(window: int, seed: int):
    base_step = 100000
    chunks, proof = build_600_partition(base_step=base_step, window=window, seed=seed)

    assert len(chunks) == 600
    assert proof.is_complete is True
    assert proof.is_disjoint is True
    assert proof.overlap_proof == "EMPTY"
    assert proof.total_window == window
    assert proof.total_lanes == 600
    assert proof.verify() is True

    # Validate union and pairwise intersection
    collected_nonces = []
    for c in chunks:
        assert c.verify_bijection() is True
        collected_nonces.extend(c.nonces)

    assert len(collected_nonces) == window
    assert len(set(collected_nonces)) == window
    assert set(collected_nonces) == set(range(base_step, base_step + window))


def test_build_600_partition_unique_vertex_ownership():
    chunks, proof = build_600_partition(base_step=0, window=1200, seed=2026)
    vertex_owners = [c.vertex_id for c in chunks]
    assert len(vertex_owners) == 600
    assert len(set(vertex_owners)) == 600


def test_partition_proof_tamper_detection():
    chunks, proof = build_600_partition(base_step=0, window=600, seed=1337)
    assert proof.verify() is True

    # Tampered copy with modified total_window
    tampered = PartitionProof600(
        bijection_fn=proof.bijection_fn,
        coverage_hash=proof.coverage_hash,
        overlap_proof=proof.overlap_proof,
        is_complete=proof.is_complete,
        is_disjoint=proof.is_disjoint,
        total_window=proof.total_window + 1,  # tampered
        total_lanes=proof.total_lanes,
        recheck_passed=proof.recheck_passed,
        recheck_count=proof.recheck_count,
        order_seed=proof.order_seed,
        certificate_sha256=proof.certificate_sha256,
        representation_labels=proof.representation_labels,
    )
    assert tampered.verify() is False


def test_host_sha256d_recheck():
    prefix = b"A" * 76
    target = (1 << 256) - 1  # max 256-bit int ensures all valid hashes pass
    chunks, proof = build_600_partition(
        base_step=5000,
        window=1200,
        seed=1337,
        header_prefix=prefix,
        target_int=target,
    )
    assert proof.recheck_passed is True
    assert proof.recheck_count > 0


def test_mother_tensor_dimensions_and_gauge():
    mt = kellogg_state_600(
        base_step=0,
        window=6000,
        seed=1337,
        futures=("job_0", "job_1"),
        future_probabilities=(0.7, 0.3),
    )
    assert mt.dims == (600, 2, 10, 11)
    assert mt.enforce_gauge_symmetry() is True


def test_ansatz_v3_reconciliation_canonical_bound():
    ansatz = load_ansatz("ansatz_v3")
    trace = ansatz.reconcile_lane(
        lane_id=0,
        initial_kappa=-0.162,
        c_pre=0.8,
        trauma_intensity=9.0,
    )
    assert trace.is_canonical is True
    assert trace.steps_taken <= 8
    assert abs(trace.final_kappa) <= 0.05
    assert trace.execution_granted is True


def test_ansatz_v3_xor_transition():
    ansatz = load_ansatz("ansatz_v3")
    ratio = ansatz.compute_xor_transition(0xAA, 0x55)
    assert ratio == 0.5625


def test_mother_tensor_pillar_contraction():
    mt = kellogg_state_600(base_step=1000, window=1800, seed=42)
    contraction = mt.contract()

    assert contraction.is_complete is True
    assert len(contraction.missing_pillars) == 0
    assert contraction.phi_method is not None
    assert "0.618033988749895" in contraction.phi_method
    assert contraction.xor_05625 == 0.5625
    assert contraction.kappa_trace is not None
    assert contraction.kappa_trace.steps_taken <= 8
    assert len(contraction.contraction_hash) == 64


def test_search_plan_collapse_from_mother_tensor():
    mt = kellogg_state_600(base_step=0, window=1200, seed=1337)
    identity = WorkIdentity(
        pool_session_id="session_test",
        generation=1,
        job_id="job_001",
        job_fingerprint="fp_abc123",
        target_generation=1,
        clean_jobs=True,
        received_at=100.0,
    )
    plan = mt.build_search_plan(
        identity=identity,
        base_step=0,
        window=1200,
        extranonce2="00000001",
        executor_route="chronus_batch",
    )

    assert isinstance(plan, SearchPlan)
    assert plan.job_fingerprint == "fp_abc123"
    assert plan.base_step == 0
    assert plan.window == 1200
    assert len(plan.lane_order) == 32
    assert plan.evidence_refs["kellogg_mother_tensor_600"] is True
    assert "partition_proof" in plan.evidence_refs


def test_consolidated_shims():
    import kellogg
    import kellogg.canonical_tensor as kct
    import tensor.canonical_tensor as tct

    for sym in (
        "EstateChunk600",
        "PartitionProof600",
        "build_600_partition",
        "AnsatzV3",
        "load_ansatz",
        "KelloggMotherTensor",
        "PillarContractionResult",
        "kellogg_state_600",
    ):
        assert hasattr(kellogg, sym)
        assert hasattr(kct, sym)
        assert hasattr(tct, sym)
        assert getattr(kellogg, sym) is getattr(kct, sym)
        assert getattr(kct, sym) is getattr(tct, sym)
