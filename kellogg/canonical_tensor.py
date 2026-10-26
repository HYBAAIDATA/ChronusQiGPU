"""Kellogg canonical tensor state and SearchPlan builder with exact coverage proof.

Consolidated canonical tensor representation:
    T in H_futures (x) H_lanes (x) H_nonces

Algebraic foundations:
- Futures: N <= 8 chain futures held in superposition with literal pool probabilities.
- Lanes: 32 M-theory frame traversal lanes (dual overlay icosahedron + dodecahedron).
- Nonces: Leased interval [base_step, base_step + window) partitioned across 32 lanes.
- Coverage Law: Traversal with stride s over subwindow M = W // 32 is a strict
  bijection iff gcd(s, M) = 1. Since lane partitions [base + l*M, base + (l+1)*M)
  are pairwise disjoint, the global coverage over [base, base + W) is 100%
  with zero overlap.
- Representation: Explicitly chosen and logged per run:
  * ExactStateVector[Q(sqrt2)+iQ(sqrt2)] (pure algebraic field Q(zeta_8))
  * ExactCyclotomicRing[Z[phi]] (golden transfer matrix / Lucas ring)
  * ComplexHilbertSpace[C^N] (unitary evolution over C^N)
- Host verification: 100% independent bit-exact host double-SHA256 recheck against target.
"""

from __future__ import annotations

import hashlib
import json
import math
import struct
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from chronus.mla1517.mining.search_plan import (
    PlanSource,
    SearchPlan,
    WorkIdentity,
    _LANES,
)


class RepresentationChoice(str, Enum):
    """The canonical algebraic representation choice logged per run."""

    EXACT_CLIFFORD_T = "ExactStateVector[Q(sqrt2)+iQ(sqrt2)]"
    EXACT_CYCLOTOMIC_ZPHI = "ExactCyclotomicRing[Z[phi]]"
    COMPLEX64_HILBERT = "ComplexHilbertSpace[C^N]"


@dataclass(frozen=True)
class CoverageProofCertificate:
    """Machine-checkable certificate attesting to bijection and zero overlap."""

    is_bijection: bool
    zero_overlap: bool
    coverage_pct: float
    window: int
    base_step: int
    lanes: int
    stride: int
    subwindow: int
    gcd_coprime: bool
    representation: str
    certificate_sha256: str
    provenance: dict[str, Any]

    def verify(self) -> bool:
        """Replay mathematical verification of the coverage theorem."""
        if not self.is_bijection or not self.zero_overlap or self.coverage_pct != 100.0:
            return False
        if not self.gcd_coprime:
            return False
        if math.gcd(self.stride, self.subwindow) != 1:
            return False
        if self.lanes * self.subwindow != self.window:
            return False

        # Verify digest integrity
        payload = {
            "window": self.window,
            "base_step": self.base_step,
            "lanes": self.lanes,
            "stride": self.stride,
            "subwindow": self.subwindow,
            "representation": self.representation,
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        return digest == self.certificate_sha256

    def as_dict(self) -> dict[str, Any]:
        return {
            "is_bijection": self.is_bijection,
            "zero_overlap": self.zero_overlap,
            "coverage_pct": self.coverage_pct,
            "window": self.window,
            "base_step": self.base_step,
            "lanes": self.lanes,
            "stride": self.stride,
            "subwindow": self.subwindow,
            "gcd_coprime": self.gcd_coprime,
            "representation": self.representation,
            "certificate_sha256": self.certificate_sha256,
            "provenance": self.provenance,
        }


@dataclass(frozen=True)
class CanonicalKelloggTensor:
    """High-dimensional joint tensor state over futures x lanes x nonces."""

    futures: tuple[str, ...]
    future_probabilities: tuple[float, ...]
    window: int
    base_step: int
    stride: int = 5
    lanes: int = _LANES
    representation: RepresentationChoice = RepresentationChoice.EXACT_CLIFFORD_T
    created_at: float = field(default_factory=time.monotonic)
    representation_log: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if len(self.futures) == 0:
            raise ValueError("Futures dimension cannot be empty")
        if len(self.futures) > 8:
            raise ValueError(f"Futures dimension {len(self.futures)} exceeds bound N=8")
        if len(self.futures) != len(self.future_probabilities):
            raise ValueError("Futures and probabilities must match in length")
        prob_sum = sum(self.future_probabilities)
        if abs(prob_sum - 1.0) > 1e-6:
            raise ValueError(f"Probabilities must normalize to 1.0, got {prob_sum}")
        if self.window <= 0 or self.window % self.lanes != 0:
            raise ValueError(
                f"Window {self.window} must be positive and divisible by {self.lanes} lanes"
            )
        if self.base_step < 0 or self.base_step + self.window > 0x100000000:
            raise ValueError(
                f"Interval [{self.base_step}, {self.base_step + self.window}) exceeds uint32 domain"
            )

        subwindow = self.window // self.lanes
        if math.gcd(self.stride, subwindow) != 1:
            raise ArithmeticError(
                f"Stride {self.stride} is not coprime to subwindow {subwindow} (gcd={math.gcd(self.stride, subwindow)}): "
                f"bijection violated, coverage is incomplete"
            )

        if not self.representation_log:
            rep_log = {
                "representation": self.representation.value,
                "algebraic_field": (
                    "Q(sqrt2, i) [Clifford+T exact]"
                    if self.representation is RepresentationChoice.EXACT_CLIFFORD_T
                    else (
                        "Z[phi] [Lucas-Cassini ring]"
                        if self.representation is RepresentationChoice.EXACT_CYCLOTOMIC_ZPHI
                        else "C^N [Complex Hilbert]"
                    )
                ),
                "is_exact": self.representation
                in (
                    RepresentationChoice.EXACT_CLIFFORD_T,
                    RepresentationChoice.EXACT_CYCLOTOMIC_ZPHI,
                ),
                "tensor_dimensions": {
                    "futures": len(self.futures),
                    "lanes": self.lanes,
                    "subwindow": subwindow,
                    "total_nonces": self.window,
                },
                "stride": self.stride,
                "gcd_check": "PASS",
                "logged_at": time.time(),
            }
            object.__setattr__(self, "representation_log", rep_log)

    @property
    def subwindow(self) -> int:
        return self.window // self.lanes

    def generate_lane_nonces(self, lane_idx: int) -> tuple[int, ...]:
        """Generate the exact deterministic bijective traversal for one lane."""
        if not 0 <= lane_idx < self.lanes:
            raise IndexError(f"Lane {lane_idx} out of range [0, {self.lanes})")
        lane_base = self.base_step + lane_idx * self.subwindow
        m = self.subwindow
        s = self.stride
        return tuple(lane_base + ((k * s) % m) for k in range(m))

    def generate_all_nonces(self) -> dict[int, tuple[int, ...]]:
        """Generate nonces for all 32 lanes."""
        return {lane: self.generate_lane_nonces(lane) for lane in range(self.lanes)}

    def build_coverage_certificate(self) -> CoverageProofCertificate:
        """Construct a machine-checkable coverage certificate with exact proof."""
        subwindow = self.subwindow
        payload = {
            "window": self.window,
            "base_step": self.base_step,
            "lanes": self.lanes,
            "stride": self.stride,
            "subwindow": subwindow,
            "representation": self.representation.value,
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

        cert = CoverageProofCertificate(
            is_bijection=True,
            zero_overlap=True,
            coverage_pct=100.0,
            window=self.window,
            base_step=self.base_step,
            lanes=self.lanes,
            stride=self.stride,
            subwindow=subwindow,
            gcd_coprime=True,
            representation=self.representation.value,
            certificate_sha256=digest,
            provenance={
                "proof_method": "Coprime modular arithmetic over disjoint lane estates",
                "theorem": "gcd(s, M) == 1 => (k * s mod M) is a permutation of Z_M",
                "created_at": self.created_at,
                "representation_log": self.representation_log,
            },
        )
        assert cert.verify(), "Coverage certificate failed mathematical self-verification"
        return cert


def host_sha256d_recheck(
    header_prefix_76: bytes,
    nonce: int,
    target: int,
) -> tuple[bool, str]:
    """Independent 100% bit-exact host SHA256d verification against target.

    Never trusts device or emulator claims:
    Header = header_prefix_76 (76 bytes) + nonce_le (4 bytes) = 80 bytes.
    Hash = SHA256(SHA256(Header)).
    Target comparison: int.from_bytes(Hash, byteorder='little') <= target.
    """
    if len(header_prefix_76) != 76:
        raise ValueError(f"Header prefix must be exactly 76 bytes, got {len(header_prefix_76)}")
    if not 0 <= nonce <= 0xFFFFFFFF:
        raise ValueError(f"Nonce {nonce} must be uint32")

    header_80 = header_prefix_76 + struct.pack("<I", nonce)
    h1 = hashlib.sha256(header_80).digest()
    h2 = hashlib.sha256(h1).digest()
    val = int.from_bytes(h2, byteorder="little")
    passed = val <= target
    digest_hex = h2[::-1].hex()
    return passed, digest_hex


def build_kellogg_search_plan(
    identity: WorkIdentity,
    base_step: int,
    window: int,
    extranonce2: str,
    lane_order: tuple[int, ...] = tuple(range(_LANES)),
    preferred_face: int = 0,
    dispatch_breadth: int = 32,
    executor_route: str = "cpu_reference",
    stride: int = 5,
    policy_id: str = "kellogg_canonical_tensor",
    representation: RepresentationChoice | str = RepresentationChoice.EXACT_CLIFFORD_T,
    futures: tuple[str, ...] = ("job_primary",),
    future_probabilities: tuple[float, ...] = (1.0,),
    toe_frame_id: str | None = None,
    source: PlanSource = PlanSource.AGENTIC_PRECOMPUTED,
    plan_fallback_reason: str | None = None,
) -> SearchPlan:
    """Build an immutable SearchPlan backed by canonical Kellogg tensor state with coverage proof."""
    if isinstance(representation, str):
        try:
            rep_enum = RepresentationChoice(representation)
        except ValueError:
            rep_enum = RepresentationChoice.EXACT_CLIFFORD_T
    else:
        rep_enum = representation

    tensor = CanonicalKelloggTensor(
        futures=futures,
        future_probabilities=future_probabilities,
        window=window,
        base_step=base_step,
        stride=stride,
        lanes=len(lane_order),
        representation=rep_enum,
    )
    cert = tensor.build_coverage_certificate()

    evidence = {
        "kellogg_canonical_tensor": True,
        "coverage_proof": cert.as_dict(),
        "representation_choice": tensor.representation_log,
        "requested_route": executor_route,
        "subwindow_per_lane": tensor.subwindow,
        "stride": stride,
    }

    if toe_frame_id is not None:
        evidence["toe_frame_digest"] = toe_frame_id

    return SearchPlan(
        job_fingerprint=identity.job_fingerprint,
        pool_session_id=identity.pool_session_id,
        generation=identity.generation,
        base_step=base_step,
        window=window,
        extranonce2=extranonce2,
        lane_order=lane_order,
        preferred_face=preferred_face,
        dispatch_breadth=dispatch_breadth,
        executor_route=executor_route,
        policy_id=policy_id,
        evidence_refs=evidence,
        created_at=time.monotonic(),
        plan_id=str(uuid.uuid4()),
        nonce_order="hendrix_coprime_stride",
        toe_frame_id=toe_frame_id,
        source=source,
        plan_fallback_reason=plan_fallback_reason,
    )


from kellogg.mother_tensor import (
    EstateChunk600,
    KelloggMotherTensor,
    PartitionProof600,
    build_600_partition,
    kellogg_state_600,
)

__all__ = [
    "RepresentationChoice",
    "CoverageProofCertificate",
    "CanonicalKelloggTensor",
    "host_sha256d_recheck",
    "build_kellogg_search_plan",
    # 600-lane canonical mother-tensor and partition
    "EstateChunk600",
    "KelloggMotherTensor",
    "PartitionProof600",
    "build_600_partition",
    "kellogg_state_600",
]


# Keep monorepo scoring dependencies out of the standalone tensor import path.
def __getattr__(name: str):
    if name in _LANE_SCORER_EXPORTS:
        from kellogg import lane_scorer

        value = getattr(lane_scorer, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


_LANE_SCORER_EXPORTS = (
    "PerLaneScoreLog",
    "FutureSuperpositionEntry",
    "SuperpositionHoldLRU",
    "QuantumArsenal",
    "score_600_lanes",
)
__all__.extend(_LANE_SCORER_EXPORTS)
