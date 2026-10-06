"""Evidence-scoped design profile for the GPU-to-hybrid-ASIC transition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HybridAsicDesignProfile:
    rounds_per_stage: int = 4
    sha256d_compressions_per_header: int = 3
    fixed_first_block_precomputed: bool = True
    variable_compressions_per_nonce: int = 2
    host_reverification_required: bool = True
    die_attestation_required: bool = True
    thermal_telemetry_required: bool = True

    def __post_init__(self) -> None:
        if self.rounds_per_stage not in {2, 4, 8, 16, 32, 64}:
            raise ValueError("rounds_per_stage must be a supported architectural exploration")
        if self.sha256d_compressions_per_header != 3:
            raise ValueError("Bitcoin SHA-256d over an 80-byte header requires three compressions")
        if self.variable_compressions_per_nonce != 2:
            raise ValueError("block-one precomputation leaves two nonce-dependent compressions")
        if not self.host_reverification_required:
            raise ValueError("host consensus re-verification cannot be disabled")

    def report(self) -> dict[str, Any]:
        from toe.foundation import UNIFIED_THEORY

        return {
            "schema": "hyba.hybrid_asic.design_profile.v1",
            "foundation_digest": UNIFIED_THEORY.digest,
            "rounds_per_stage": self.rounds_per_stage,
            "sha256d_compressions_per_header": self.sha256d_compressions_per_header,
            "fixed_first_block_precomputed": self.fixed_first_block_precomputed,
            "variable_compressions_per_nonce": self.variable_compressions_per_nonce,
            "host_reverification_required": self.host_reverification_required,
            "die_attestation_required": self.die_attestation_required,
            "thermal_telemetry_required": self.thermal_telemetry_required,
            "gpu_role": "reference executor, emulator, profiler, and fallback substrate",
            "asic_role": "optional measured fixed-function execution substrate",
            "composition": "capability-probed disjoint windows with host verification",
            "pdk_area_power_timing_claimed": False,
            "physical_asic_present": False,
            "comparative_advantage_claimed": False,
        }


DEFAULT_HYBRID_ASIC_PROFILE = HybridAsicDesignProfile()

__all__ = ["DEFAULT_HYBRID_ASIC_PROFILE", "HybridAsicDesignProfile"]
