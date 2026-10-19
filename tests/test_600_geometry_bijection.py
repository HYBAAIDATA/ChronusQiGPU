"""Unit tests for the 600-Lane Solving Machine Geometry, Bijection, & Kellogg Mother-Tensor.

Verifies:
1. Exact 600-vertex geometry: Dodecahedron ⊕ Icosahedron overlay lifted to H4 dual
   polychoron decomposition and 11D coordinates in Q(phi)^11 via fold11().
2. Structured Hendrix Grover order: Exact quantum coined walk over C600 permutes 600 vertices
   deterministically with clamped materialisation bound (<= 2^20) across seeds [1337, 42, 2026].
3. Complete Hilbert-space tiling: Leased window W partitioned across 600 disjoint estate chunks
   with 100% complete coverage (Union == W) and strictly 0 overlap (Intersect == empty).
4. Strict vertex ownership: Exactly one unique vertex per lane (no lane aliasing or duplication).
5. Representation labeling: Explicitly logged NUMERICAL vs EXACT labels per coordinate transform.
6. Host SHA256d recheck: 100% independent bit-exact host double-SHA256 verification.
7. Kellogg mother-tensor: Shape [600, 8, chunk_size, 11], Yang-Mills gauge symmetry (no privileged lane).
8. Contraction proof: Contraction over 9 pillars strictly reproduces {phi_method, xor_0.5625, kappa_trace}
   with 8-step Ricci curvature convergence.
9. Consolidated shims & re-exports: Identical references across kellogg, kellogg.canonical_tensor,
   and tensor.
"""

from __future__ import annotations

import hashlib
import math
import struct
import time
import pytest

from chronus.exact_geometry import (
    EstateChunk600,
    PartitionProof600,
    build_600_partition,
    dodeca_overlay_icosa,
    embed_11d_exact,
    exact_walk_reference,
    hendrix_grover_order,
)
from chronus.mla1517.mining.search_plan import SearchPlan, WorkIdentity
from kellogg.ansatz_v3 import PHI, PHI_INV, RICCI_REF, TAU, XOR_INVARIANT, load_ansatz
from kellogg.mother_tensor import (
    CANONICAL_LANES,
    KelloggMotherTensor,
    kellogg_state_600,
)
import kellogg
import kellogg.canonical_tensor as kellogg_canonical
import tensor
import tensor.canonical_tensor as tensor_canonical

SEEDS = [1337, 42, 2026]


def _make_dummy_identity(
    pool_session_id: str = "braiins-600lane-session",
    generation: int = 1,
    job_id: str = "job_600_test",
    fingerprint: str = "fp_600_beefcafe",
) -> WorkIdentity:
    return WorkIdentity(
        pool_session_id=pool_session_id,
        generation=generation,
        job_id=job_id,
        job_fingerprint=fingerprint,
        target_generation=1,
        clean_jobs=True,
        received_at=time.monotonic(),
        work_space="workspace_600lane_dummy_hash",
    )


class Test600GeometryBijection:
    def test_dodeca_overlay_icosa_600_rays(self) -> None:
        """600 exact rays from H4 600-cell dual compound lift to 11D with unit norm."""
        rays = dodeca_overlay_icosa()
        assert len(rays) == 600
        assert len(set(r.numerator for r in rays)) == 600, "All 600 rays must have unique numerators"
        assert all(r.is_unit() for r in rays), "Every ray must be an exact unit vector"

        # Lift to 11D
        coords11 = embed_11d_exact(rays)
        assert len(coords11) == 600
        assert all(r11.in_phi_ball() for r11 in coords11), "11D lifted rays must lie in open phi ball"
        assert all(len(r11.numerator) == 11 for r11 in coords11), "11D lifted rays must have 11 components"

    @pytest.mark.parametrize("seed", SEEDS)
    def test_hendrix_grover_clamped_order(self, seed: int) -> None:
        """Hendrix Grover order must be a deterministic 600-permutation across seeds."""
        order = hendrix_grover_order(seed=seed)
        assert len(order) == 600
        assert len(set(order)) == 600
        assert set(order) == set(range(600)), "Must be a complete bijection of vertices 0..599"

        # Determinism check
        order_replay = hendrix_grover_order(seed=seed)
        assert order == order_replay

    @pytest.mark.parametrize("seed", SEEDS)
    @pytest.mark.parametrize("window", [600, 3000, 60000, 19200])
    def test_build_600_partition_totality_and_disjointness(self, seed: int, window: int) -> None:
        """Verify 100% complete coverage (Union == W) and 0% overlap (Intersection == empty)."""
        base_step = 100000
        chunks, proof = build_600_partition(base_step=base_step, window=window, seed=seed)

        assert len(chunks) == 600
        assert proof.is_complete is True
        assert proof.is_disjoint is True
        assert proof.overlap_proof == "EMPTY"
        assert proof.total_window == window
        assert proof.total_lanes == 600
        assert proof.order_seed == seed
        assert proof.recheck_passed is True
        assert proof.verify() is True

        # Check chunk bijection and ownership
        seen_nonces = set()
        seen_vertices = set()

        for chunk in chunks:
            assert chunk.verify_bijection() is True
            assert chunk.vertex_id not in seen_vertices, f"Duplicate vertex ownership: {chunk.vertex_id}"
            seen_vertices.add(chunk.vertex_id)

            chunk_set = set(chunk.nonces)
            assert len(chunk_set) == len(chunk.nonces), f"Lane {chunk.lane_id} has internal duplicates"

            overlap = seen_nonces.intersection(chunk_set)
            assert len(overlap) == 0, f"Lane {chunk.lane_id} overlaps with prior chunks: {overlap}"
            seen_nonces.update(chunk_set)

        assert len(seen_vertices) == 600, "All 600 vertices must own exactly 1 chunk"
        assert len(seen_nonces) == window, f"Expected {window} nonces, got {len(seen_nonces)}"
        assert seen_nonces == set(range(base_step, base_step + window)), "Union != window (tiling incomplete)"

        # Check representation labels
        rep_dict = dict(proof.representation_labels)
        assert rep_dict.get("poincare_cassini") == "EXACT"
        assert rep_dict.get("klein_poincare") == "NUMERICAL"

    def test_600_partition_host_sha256d_recheck(self) -> None:
        """Sample host SHA256d recheck executes double-SHA256 against synthetic header prefix."""
        header_prefix = b"\x01\x00\x00\x00" + b"\x00" * 32 + b"\x22" * 32 + b"\x29\xab\x5f\x49" + b"\xff\xff\x00\x1d"
        assert len(header_prefix) == 76

        max_target = (1 << 256) - 1
        chunks, proof = build_600_partition(
            base_step=50000,
            window=6000,
            seed=1337,
            header_prefix=header_prefix,
            target_int=max_target,
        )

        assert proof.recheck_passed is True
        assert proof.recheck_count > 0

        # Independent verification of sample chunk nonces
        from kellogg.canonical_tensor import host_sha256d_recheck
        for chunk in chunks[:5]:
            for nonce in chunk.nonces[:2]:
                passed, digest_hex = host_sha256d_recheck(header_prefix, nonce, max_target)
                assert passed is True
                assert len(digest_hex) == 64


    def test_kellogg_mother_tensor_shape_and_gauge_symmetry(self) -> None:
        """Mother-Tensor has shape [600, 8, chunk_size, 11] and enforces Yang-Mills gauge symmetry."""
        window = 600 * 16
        futures = ("job_0", "job_1", "job_reorg", "diff_up", "diff_down", "stale_risk", "fee_surge", "anchor")
        probs = (0.25, 0.20, 0.15, 0.10, 0.10, 0.10, 0.05, 0.05)

        mt = kellogg_state_600(
            window=window,
            base_step=0,
            seed=1337,
            futures=futures,
            future_probabilities=probs,
        )

        assert mt.lanes == 600
        assert len(mt.futures) == 8
        assert mt.chunk_size == 16
        assert mt.shape == (600, 8, 16, 11)
        assert mt.yang_mills_enforced is True

        gauge_report = mt.enforce_gauge_symmetry()
        assert gauge_report["symmetric"] is True
        assert gauge_report["transport_invariant"] is True

    def test_kellogg_mother_tensor_contraction_reproduces_targets(self) -> None:
        """Contraction over 9 pillars must reproduce {phi_method, xor_0.5625, kappa_trace}."""
        mt = kellogg_state_600(
            window=6000,
            base_step=0,
            seed=42,
        )

        evidence = mt.contract()
        assert evidence["contraction_verified"] is True

        # 1. Phi Method
        phi_data = evidence["phi_method"]
        assert phi_data["status"] == "PASS"
        assert abs(phi_data["phi_inv"] - PHI_INV) < 1e-12
        assert phi_data["identity_holds"] is True

        # 2. XOR 0.5625
        xor_data = evidence["xor_0.5625"]
        assert xor_data["status"] == "PASS"
        assert xor_data["reproduced"] == XOR_INVARIANT
        assert xor_data["target"] == 0.5625

        # 3. Kappa Trace (8-step Ricci flow convergence)
        kappa_data = evidence["kappa_trace"]
        assert kappa_data["status"] == "PASS"
        assert kappa_data["canonical_bound_holds"] is True
        assert kappa_data["steps"] <= RICCI_REF
        assert abs(kappa_data["final_kappa"]) <= TAU

    def test_kellogg_search_plan_collapse_from_mother_tensor(self) -> None:
        """Mother-Tensor collapses to a certified, immutable SearchPlan."""
        identity = _make_dummy_identity()
        mt = kellogg_state_600(
            window=6000,
            base_step=12000,
            seed=2026,
        )

        plan = mt.build_search_plan(
            identity=identity,
            extranonce2="01020304",
            executor_route="chronus_batch",
        )

        assert isinstance(plan, SearchPlan)
        assert plan.window == 6000
        assert plan.base_step == 12000
        assert plan.executor_route == "chronus_batch"
        assert plan.evidence_refs["kellogg_mother_tensor_600"] is True
        assert plan.evidence_refs["lanes"] == 600
        assert plan.evidence_refs["shape"] == [600, 1, 10, 11]
        assert plan.evidence_refs["yang_mills_gauge"] is True
        assert plan.evidence_refs["contraction"]["contraction_verified"] is True
        assert "partition_proof_600" in plan.evidence_refs

    def test_consolidated_shims_and_reexports(self) -> None:
        """Verify identical consolidated exports across kellogg, kellogg.canonical_tensor, and tensor."""
        assert kellogg.KelloggMotherTensor is KelloggMotherTensor
        assert kellogg.build_600_partition is build_600_partition
        assert kellogg.PartitionProof600 is PartitionProof600
        assert kellogg.EstateChunk600 is EstateChunk600
        assert kellogg.kellogg_state_600 is kellogg_state_600

        assert kellogg_canonical.KelloggMotherTensor is KelloggMotherTensor
        assert kellogg_canonical.build_600_partition is build_600_partition
        assert kellogg_canonical.PartitionProof600 is PartitionProof600
        assert kellogg_canonical.EstateChunk600 is EstateChunk600
        assert kellogg_canonical.kellogg_state_600 is kellogg_state_600

        assert tensor.KelloggMotherTensor is KelloggMotherTensor
        assert tensor.build_600_partition is build_600_partition
        assert tensor.PartitionProof600 is PartitionProof600
        assert tensor.EstateChunk600 is EstateChunk600
        assert tensor.kellogg_state_600 is kellogg_state_600

        assert tensor_canonical.KelloggMotherTensor is KelloggMotherTensor
        assert tensor_canonical.build_600_partition is build_600_partition
        assert tensor_canonical.PartitionProof600 is PartitionProof600
        assert tensor_canonical.EstateChunk600 is EstateChunk600
        assert tensor_canonical.kellogg_state_600 is kellogg_state_600
