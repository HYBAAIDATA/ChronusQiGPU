"""Deterministic M32 lane and search-policy contracts.

M32 is a finite routing topology, not a claim of quantum execution. The
structured label records which declared lane contract was selected. It does
not alter the SHA256d proof rule or emit a performance claim.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Literal

M32_STRUCTURE_PRIOR = "truncated_icosahedron_32f"
FLAT_STRUCTURE_PRIOR = "flat"
_ALLOWED_PRIORS = frozenset((M32_STRUCTURE_PRIOR, FLAT_STRUCTURE_PRIOR))
_ALLOWED_ORDERINGS = frozenset(("m32_lane_order", "exhaustive"))

# The literature's ~16-minute reference horizon is used as a hard safety bound,
# not as a claim of quantum advantage. See arXiv:2110.00878.
WORK_WINDOW_MAX_S = 16 * 60
# The active OpenCL payload implements first-block SHA-256 midstate caching:
# the host precomputes the SHA-256 midstate of the constant 64-byte header
# prefix once per job (sha256_midstate), so each work-item compresses only the
# nonce block + final digest. This is an honest constant-factor optimisation
# (beta = 0.5) — it never bypasses the double-SHA256 consensus predicate.
# Verified by test_midstate_kernel_matches_reference in tests/.
KERNEL_BETA_MIDSTATE = 0.5


@dataclass(frozen=True)
class Partition:
    """Explicit candidate-window contract; it never bypasses SHA256d."""

    device_id: str
    nonce_start: int
    nonce_end: int
    stride: int = 1
    extra_nonce_start: int = 0
    extra_nonce_end: int = 1
    ntime_variation: int = 0
    merkle_recompute: bool = False

    def __post_init__(self) -> None:
        if not self.device_id:
            raise ValueError("device_id is required")
        if not 0 <= self.nonce_start < self.nonce_end <= 0xFFFFFFFF:
            raise ValueError("nonce range must be an ordered uint32 interval")
        if self.stride <= 0:
            raise ValueError("stride must be positive")
        if not 0 <= self.extra_nonce_start <= self.extra_nonce_end:
            raise ValueError("extra nonce range must be ordered and non-negative")
        if self.ntime_variation < 0:
            raise ValueError("ntime_variation cannot be negative")


@dataclass(frozen=True)
class ScheduleFingerprint:
    """Auditable cost knobs from the mining schedule literature."""

    k_hash: int = 1
    merkle_recompute: bool = False
    midstate_reuse: bool = True
    work_window_seconds: int = WORK_WINDOW_MAX_S
    kernel_beta_midstate: float = KERNEL_BETA_MIDSTATE

    @property
    def beta_midstate(self) -> float:
        return 0.5 if self.midstate_reuse else 1.0

    @property
    def alpha_merkle(self) -> int:
        return int(self.merkle_recompute)

    def __post_init__(self) -> None:
        if self.k_hash <= 0:
            raise ValueError("k_hash must be positive")
        if not 0 < self.work_window_seconds <= WORK_WINDOW_MAX_S:
            raise ValueError(
                f"work_window_seconds must be between 1 and {WORK_WINDOW_MAX_S}"
            )
        if self.kernel_beta_midstate not in (0.5, 1.0):
            raise ValueError("kernel_beta_midstate must be 0.5 or 1.0")
        if self.beta_midstate != self.kernel_beta_midstate:
            raise ValueError(
                "schedule beta_midstate diverges from the active kernel contract"
            )

    def as_dict(self) -> dict[str, object]:
        return {
            "k_hash": self.k_hash,
            "alpha_merkle": self.alpha_merkle,
            "beta_midstate": self.beta_midstate,
            "work_window_seconds": self.work_window_seconds,
            "kernel_beta_midstate": self.kernel_beta_midstate,
        }

    def fingerprint_bytes(self, partition: Partition) -> bytes:
        """Return a deterministic, auditable schedule fingerprint payload."""
        payload = {
            "partition": asdict(partition),
            "schedule": self.as_dict(),
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True)
class SearchPolicy:
    candidate_ordering: Literal["m32_lane_order", "exhaustive"] = "m32_lane_order"
    oracle_budget: int = 250_000
    structure_prior: str = M32_STRUCTURE_PRIOR
    schedule: ScheduleFingerprint = field(default_factory=ScheduleFingerprint)

    def __post_init__(self) -> None:
        if self.candidate_ordering not in _ALLOWED_ORDERINGS:
            raise ValueError("unsupported candidate ordering")
        if self.structure_prior not in _ALLOWED_PRIORS:
            raise ValueError("unsupported structure prior")
        if self.oracle_budget <= 0:
            raise ValueError("oracle budget must be positive")


def build_lane_descriptor(policy: SearchPolicy, *, dispatched: bool = False) -> dict[str, object]:
    """Return a serializable lane record with no simulated execution fields."""
    return {
        "status": "dispatched" if dispatched else "pending",
        "mode": "m32_structured" if policy.structure_prior == M32_STRUCTURE_PRIOR else "flat_exhaustive",
        "candidate_ordering": policy.candidate_ordering,
        "structure_prior": policy.structure_prior,
        "budget": policy.oracle_budget,
        "proof": "sha256d",
        "execution_substrate": "mla1517_hardware_or_explicit_solver",
        "exact_candidate_coverage": True,
        "schedule_fingerprint": policy.schedule.as_dict(),
        "policy": asdict(policy),
    }
