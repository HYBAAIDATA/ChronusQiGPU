"""Unit tests for Canonical Kellogg Tensor state and SearchPlan builder with coverage proof.

Verifies:
1. Exact bijection: gcd(s, M) == 1 yields an exact permutation of [0, M) with zero collisions.
2. Zero overlap: Disjoint 32-lane partitions cover [base, base + W) with empty pairwise intersections.
3. Fail-closed on non-coprime stride: Non-coprime stride raises ArithmeticError.
4. SearchPlan builder & certificate: Validates immutable SearchPlan with verifiable CoverageProofCertificate.
5. Representation choice logging: Telemetry is recorded per run for exact and Hilbert representations.
6. Host SHA256d recheck: 100% independent bit-exact host verification against consensus target.
7. Future superposition: Bounded N <= 8 chain futures held in superposition with normalized probabilities.
8. Consolidated shims: Consistent export across kellogg, kellogg.canonical_tensor, tensor.canonical_tensor, and tensor.
"""

from __future__ import annotations

import hashlib
import math
import struct
import time
import pytest

from chronus.mla1517.mining.search_plan import (
    PlanSource,
    SearchPlan,
    WorkIdentity,
    _LANES,
)
from kellogg.canonical_tensor import (
    CanonicalKelloggTensor,
    CoverageProofCertificate,
    RepresentationChoice,
    build_kellogg_search_plan,
    host_sha256d_recheck,
)
import kellogg
import tensor
import tensor.canonical_tensor as tensor_canonical


def _make_dummy_identity(
    pool_session_id: str = "braiins-session-001",
    generation: int = 1,
    job_id: str = "job_42a",
    fingerprint: str = "fp_beefcafe",
) -> WorkIdentity:
    return WorkIdentity(
        pool_session_id=pool_session_id,
        generation=generation,
        job_id=job_id,
        job_fingerprint=fingerprint,
        target_generation=1,
        clean_jobs=True,
        received_at=time.monotonic(),
        work_space="header_workspace_hash_dummy",
    )


class TestKelloggCanonicalTensor:
    def test_kellogg_stride_bijection(self) -> None:
        """Verify gcd(s, M) == 1 produces a strict permutation bijection with 100% coverage."""
        windows = [32 * 8, 32 * 32, 32 * 128]
        strides = [1, 5, 7, 11]

        for window in windows:
            for stride in strides:
                subwindow = window // 32
                if math.gcd(stride, subwindow) != 1:
                    continue

                tensor_obj = CanonicalKelloggTensor(
                    futures=("current",),
                    future_probabilities=(1.0,),
                    window=window,
                    base_step=1000,
                    stride=stride,
                )

                # Check lane 0
                nonces_lane0 = tensor_obj.generate_lane_nonces(0)
                assert len(nonces_lane0) == subwindow
                assert len(set(nonces_lane0)) == subwindow
                expected_set_0 = set(range(1000, 1000 + subwindow))
                assert set(nonces_lane0) == expected_set_0

    def test_kellogg_lane_partition_zero_overlap(self) -> None:
        """Verify the 32 lanes partition [base_step, base_step + window) with zero overlap."""
        window = 32 * 64
        base_step = 50000
        tensor_obj = CanonicalKelloggTensor(
            futures=("primary_chain",),
            future_probabilities=(1.0,),
            window=window,
            base_step=base_step,
            stride=5,
        )

        all_lanes = tensor_obj.generate_all_nonces()
        assert len(all_lanes) == 32

        seen_nonces = set()
        for lane_idx, nonces in all_lanes.items():
            assert len(nonces) == window // 32
            lane_set = set(nonces)
            assert len(lane_set) == len(nonces), f"Lane {lane_idx} contains duplicate nonces"

            # Check zero overlap with all previous lanes
            overlap = seen_nonces.intersection(lane_set)
            assert len(overlap) == 0, f"Lane {lane_idx} has non-empty overlap with previous lanes: {overlap}"
            seen_nonces.update(lane_set)

        assert len(seen_nonces) == window
        assert seen_nonces == set(range(base_step, base_step + window))

    def test_kellogg_rejects_non_coprime_stride(self) -> None:
        """Non-coprime stride must fail closed with ArithmeticError."""
        # subwindow = 320 // 32 = 10; stride 2 or 5 shares factors with 10.
        with pytest.raises(ArithmeticError, match="bijection violated"):
            CanonicalKelloggTensor(
                futures=("job",),
                future_probabilities=(1.0,),
                window=320,
                base_step=0,
                stride=2,
            )

        with pytest.raises(ArithmeticError, match="bijection violated"):
            build_kellogg_search_plan(
                identity=_make_dummy_identity(),
                base_step=0,
                window=320,
                extranonce2="00000001",
                stride=5,  # gcd(5, 10) = 5 != 1
            )

    def test_kellogg_search_plan_coverage_certificate(self) -> None:
        """SearchPlan builder must attach a self-verifiable CoverageProofCertificate."""
        identity = _make_dummy_identity()
        plan = build_kellogg_search_plan(
            identity=identity,
            base_step=12800,
            window=32 * 32,
            extranonce2="01020304",
            preferred_face=3,
            dispatch_breadth=16,
            executor_route="cpu_reference",
            stride=5,
            representation=RepresentationChoice.EXACT_CLIFFORD_T,
        )

        assert isinstance(plan, SearchPlan)
        assert plan.window == 32 * 32
        assert plan.base_step == 12800
        assert plan.preferred_face == 3
        assert plan.evidence_refs["kellogg_canonical_tensor"] is True

        cert_dict = plan.evidence_refs["coverage_proof"]
        assert cert_dict["is_bijection"] is True
        assert cert_dict["zero_overlap"] is True
        assert cert_dict["coverage_pct"] == 100.0
        assert cert_dict["gcd_coprime"] is True

        # Reconstruct certificate and verify
        cert = CoverageProofCertificate(**cert_dict)
        assert cert.verify() is True

    def test_kellogg_representation_choice_logging(self) -> None:
        """Every plan must explicitly record its algebraic representation telemetry."""
        for choice in RepresentationChoice:
            plan = build_kellogg_search_plan(
                identity=_make_dummy_identity(),
                base_step=0,
                window=32 * 16,
                extranonce2="00000000",
                representation=choice,
            )
            rep_log = plan.evidence_refs["representation_choice"]
            assert rep_log["representation"] == choice.value
            assert "algebraic_field" in rep_log
            assert "is_exact" in rep_log
            assert "logged_at" in rep_log
            assert rep_log["gcd_check"] == "PASS"

    def test_kellogg_tensor_superposition_futures(self) -> None:
        """Superposition state holds up to N=8 futures with normalized probabilities."""
        futures = ("job_0", "job_1", "job_reorg", "diff_up", "diff_down", "stale_risk", "fee_surge", "anchor")
        probs = (0.3, 0.2, 0.1, 0.1, 0.1, 0.1, 0.05, 0.05)
        tensor_obj = CanonicalKelloggTensor(
            futures=futures,
            future_probabilities=probs,
            window=32 * 8,
            base_step=0,
            stride=5,
        )
        assert len(tensor_obj.futures) == 8
        assert tensor_obj.representation_log["tensor_dimensions"]["futures"] == 8

        # N > 8 must raise ValueError
        with pytest.raises(ValueError, match="exceeds bound N=8"):
            CanonicalKelloggTensor(
                futures=futures + ("extra_future_9",),
                future_probabilities=probs + (0.0,),
                window=32 * 8,
                base_step=0,
            )

        # Unnormalized probabilities must raise ValueError
        with pytest.raises(ValueError, match="must normalize to 1.0"):
            CanonicalKelloggTensor(
                futures=("f1", "f2"),
                future_probabilities=(0.5, 0.2),
                window=32 * 8,
                base_step=0,
            )

    def test_kellogg_host_sha256d_recheck(self) -> None:
        """Host recheck independently computes double-SHA256 and compares to target."""
        # 76-byte synthetic Bitcoin block header prefix
        header_prefix = b"\x01\x00\x00\x00" + b"\x00" * 32 + b"\x11" * 32 + b"\x29\xab\x5f\x49" + b"\xff\xff\x00\x1d"
        assert len(header_prefix) == 76

        nonce = 123456
        # Compute exact hash manually
        h1 = hashlib.sha256(header_prefix + struct.pack("<I", nonce)).digest()
        h2 = hashlib.sha256(h1).digest()
        actual_val = int.from_bytes(h2, "little")

        # Test target greater than actual => passes
        passed_hi, digest_hi = host_sha256d_recheck(header_prefix, nonce, actual_val + 1)
        assert passed_hi is True
        assert digest_hi == h2[::-1].hex()

        # Test target equal to actual => passes
        passed_eq, _ = host_sha256d_recheck(header_prefix, nonce, actual_val)
        assert passed_eq is True

        # Test target less than actual => fails
        passed_lo, _ = host_sha256d_recheck(header_prefix, nonce, actual_val - 1)
        assert passed_lo is False

        # Invalid prefix length raises
        with pytest.raises(ValueError, match="76 bytes"):
            host_sha256d_recheck(b"too_short", nonce, 0xFFFF)

    def test_kellogg_consolidated_shims(self) -> None:
        """Imports from kellogg, kellogg.canonical_tensor, tensor, tensor.canonical_tensor are identical."""
        assert kellogg.CanonicalKelloggTensor is CanonicalKelloggTensor
        assert kellogg.CoverageProofCertificate is CoverageProofCertificate
        assert kellogg.build_kellogg_search_plan is build_kellogg_search_plan
        assert kellogg.host_sha256d_recheck is host_sha256d_recheck

        assert tensor.CanonicalKelloggTensor is CanonicalKelloggTensor
        assert tensor.CoverageProofCertificate is CoverageProofCertificate
        assert tensor.build_kellogg_search_plan is build_kellogg_search_plan
        assert tensor.host_sha256d_recheck is host_sha256d_recheck

        assert tensor_canonical.CanonicalKelloggTensor is CanonicalKelloggTensor
        assert tensor_canonical.build_kellogg_search_plan is build_kellogg_search_plan
