"""Plastic Intelligence — Compute Configuration and Thermal Management Authority.

Operates across Substrates:
  - Substrate 9: Tensor (25-punch dispatch execution and kernel fusion)
  - Substrate 8: MDMemory (Multi-dimensional buffer caching and layout)
  - Substrate 12: Storage (Galois cell retention and cache flush)

Provides ADVISORY intelligence for punch fusion, dispatch sizing, thermal
throttling, and hardware-budget analysis. PYTHIA remains final authority for
mining truth, SearchPlan finalization, nonce-estate coverage, SHA256d/target
proof semantics, share validation/submission, credentials, and pool acknowledgements.

LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
inline below. MUST NOT import from any sibling algorithm.
Substrate route: mining
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import time
from typing import Any, Dict, List, Optional


@dataclass
class PlasticComputeProfile:
    """Dynamic compute configuration commanded by Plastic Intelligence."""

    batch_size: int
    fused_punches: List[str]
    target_thermal_c: float
    current_thermal_c: float
    power_budget_watts: float
    estimated_hashrate_mhs: float
    plasticity_score: float
    timestamp: float = field(default_factory=time.time)
    provenance_hash: str = ""

    def __post_init__(self):
        if not self.provenance_hash:
            seed = (
                f"{self.batch_size}:{len(self.fused_punches)}:"
                f"{self.target_thermal_c}:{self.timestamp}"
            )
            self.provenance_hash = hashlib.sha256(seed.encode("utf-8")).hexdigest()

    def to_scalar(self) -> int:
        """Dual-mode scalar return: batch size."""
        return int(self.batch_size)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_size": self.batch_size,
            "fused_punches": list(self.fused_punches),
            "target_thermal_c": self.target_thermal_c,
            "current_thermal_c": self.current_thermal_c,
            "power_budget_watts": self.power_budget_watts,
            "estimated_hashrate_mhs": self.estimated_hashrate_mhs,
            "plasticity_score": self.plasticity_score,
            "timestamp": self.timestamp,
            "provenance_hash": self.provenance_hash,
        }


class PlasticIntelligence:
    """Advisory intelligence for compute tuning, kernel fusion, and thermal curves."""

    DEFAULT_FUSION = [
        "phi_filter_score",
        "sha256d_grind_mark",
        "cassini_power",
        "zeckendorf_encode",
    ]

    def __init__(
        self,
        base_batch_size: int = 2048,
        thermal_throttle_threshold_c: float = 82.0,
        max_power_watts: float = 250.0,
    ):
        self.current_batch_size = base_batch_size
        self.min_batch_size = 256
        self.max_batch_size = 65536
        self.thermal_throttle_threshold = thermal_throttle_threshold_c
        self.power_budget = max_power_watts
        self.current_temp = 55.0
        self.current_power = 120.0
        self.active_fused_punches = list(self.DEFAULT_FUSION)
        self.plasticity_score = 0.85
        self.adaptation_history: List[PlasticComputeProfile] = []

    def configure_dispatch(
        self,
        current_temp_c: Optional[float] = None,
        current_power_w: Optional[float] = None,
        observed_hashrate: float = 100.0,
    ) -> PlasticComputeProfile:
        """Autonomously tune dispatch batch size and punch pipelining based on thermal telemetry."""
        if current_temp_c is not None:
            self.current_temp = current_temp_c
        if current_power_w is not None:
            self.current_power = current_power_w

        # Thermal throttling logic
        if self.current_temp >= self.thermal_throttle_threshold:
            # Overheating: back off batch size by 50%
            self.current_batch_size = max(self.min_batch_size, int(self.current_batch_size * 0.5))
            self.active_fused_punches = ["phi_filter_score", "sha256d_grind_mark"]
        elif self.current_temp < (self.thermal_throttle_threshold - 15.0) and self.current_power < (
            self.power_budget - 30.0
        ):
            # Thermal headroom exists: safely scale batch size up
            self.current_batch_size = min(self.max_batch_size, int(self.current_batch_size * 1.25))
            self.active_fused_punches = list(self.DEFAULT_FUSION)

        profile = PlasticComputeProfile(
            batch_size=self.current_batch_size,
            fused_punches=list(self.active_fused_punches),
            target_thermal_c=self.thermal_throttle_threshold,
            current_thermal_c=self.current_temp,
            power_budget_watts=self.power_budget,
            estimated_hashrate_mhs=observed_hashrate,
            plasticity_score=self.plasticity_score,
        )
        self.adaptation_history.append(profile)
        return profile

    def fuse_punches(self, requested_punches: List[str]) -> List[str]:
        """Fuse redundant or consecutive punch calls into an optimized hardware dispatch order."""
        # Eliminate duplicates while preserving ordering
        seen = set()
        fused = []
        for p in requested_punches:
            if p not in seen:
                seen.add(p)
                fused.append(p)
        self.active_fused_punches = fused
        return self.active_fused_punches

    def learn(self, temp_delta: float, hashrate_gain: float) -> None:
        """Plasticity reinforcement: learn optimal operating point along efficiency Pareto front."""
        if hashrate_gain > 0 and temp_delta <= 1.0:
            self.plasticity_score = min(1.0, self.plasticity_score + 0.02)
        else:
            self.plasticity_score = max(0.1, self.plasticity_score - 0.01)

    def crystallize(self) -> Dict[str, Any]:
        """Cool-down transition: crystallize dynamic weights into static hardware profiles."""
        return {
            "crystallized_batch_size": self.current_batch_size,
            "crystallized_punches": list(self.active_fused_punches),
            "final_plasticity": self.plasticity_score,
            "safe_restart_profile": True,
        }
