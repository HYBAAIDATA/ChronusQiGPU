"""Aethel phi memory hierarchy — fold-depth memory tiers + integrity gate.

A four-tier folded hierarchy modelled on the traditional GPU memory stack:

    REGISTER (depth 0, no fold)
      -> SRAM  (depth 1)
      -> L2    (depth 2)
      -> HBM   (depth 3+)

Promote moves a resident toward REGISTER (unfold/refold shallower); demote moves
it toward HBM (fold deeper). Reading always reconstructs through
:func:`aethel.phi_fold.phi_unfold` — a tier change is a representation change,
never a lossy drop: every demotion keeps the full complement set.

The July Geodesic Tensor Engine memory surface is retained in this modern owner:
``store/load/promote/demote/get_working_set_ratio/get_effective_bandwidth/``
``get_memory_report``.  Bandwidth amplification is explicitly model arithmetic
from a measured representation ratio; it is never reported as hardware
telemetry.

:class:`TopologicalIntegrityGate` is the ECC-equivalent: after each tensor-core
operation it verifies measured reconstruction error, sequence chronology, and
spectral preservation.  It also preserves the July ``verify_roundtrip`` and
``get_metrics`` evidence surfaces.
"""

from __future__ import annotations

import itertools
import logging
import math
from dataclasses import dataclass
from enum import IntEnum
from typing import Dict, Optional, Tuple

import numpy as np

from .errors import AethelError
from .phi_fold import (
    NumericFoldState,
    phi_fold,
    phi_unfold,
    reconstruction_error,
    working_set_ratio,
)

logger = logging.getLogger("aethel.phi_memory")


class MemoryHierarchyError(AethelError):
    """A memory-hierarchy contract was violated."""


class MemoryTier(IntEnum):
    """Fold depth per tier."""

    REGISTER = 0
    SRAM = 1
    L2 = 2
    L2_CACHE = 2  # July compatibility spelling
    HBM = 3


@dataclass
class TierResident:
    """One named resident held at a fold depth.

    Custody identity is carried by the state itself: ``dtype`` and ``layout``
    are what the payload was folded as, and ``content_hash`` is the SHA-256
    content digest computed at fold time (see
    :meth:`NumericFoldState.compute_content_hash`).
    """

    name: str
    tier: MemoryTier
    state: NumericFoldState

    @property
    def retained_size(self) -> int:
        return self.state.retained_size

    @property
    def original_size(self) -> int:
        return self.state.original_size

    @property
    def dtype(self) -> np.dtype:
        return np.dtype(self.state.dtype)

    @property
    def layout(self) -> str:
        return self.state.layout

    @property
    def content_hash(self) -> str:
        return self.state.content_hash

    def verify_integrity(self) -> bool:
        """Re-derive the content digest; False means the resident was altered."""
        return self.state.verify_content_hash()


class PhiMemoryHierarchy:
    """Fold-depth memory hierarchy over :class:`NumericFoldState`."""

    TRADITIONAL_SPECS = {
        MemoryTier.REGISTER: {"capacity_kb": 256, "bandwidth_tbs": 50.0, "latency_ns": 1},
        MemoryTier.SRAM: {"capacity_kb": 192, "bandwidth_tbs": 20.0, "latency_ns": 30},
        MemoryTier.L2: {"capacity_mb": 50, "bandwidth_tbs": 12.0, "latency_ns": 200},
        MemoryTier.HBM: {"capacity_gb": 80, "bandwidth_tbs": 3.35, "latency_ns": 500},
    }

    def __init__(self, hbm_max_depth: int = 8) -> None:
        if hbm_max_depth < int(MemoryTier.HBM):
            raise MemoryHierarchyError(f"hbm_max_depth must be >= {int(MemoryTier.HBM)}")
        self.hbm_max_depth = int(hbm_max_depth)
        self._residents: Dict[str, TierResident] = {}
        self._promotion_count = 0
        self._demotion_count = 0
        self._eviction_count = 0

    @staticmethod
    def _tier_depth(tier: MemoryTier, hbm_max_depth: int) -> int:
        tier = MemoryTier(tier)
        return hbm_max_depth if tier == MemoryTier.HBM else int(tier)

    # -- residency ---------------------------------------------------------

    def store(
        self,
        name: str,
        array: np.ndarray,
        tier: MemoryTier = MemoryTier.HBM,
        *,
        fold_depth: int | None = None,
    ) -> TierResident:
        """Fold ``array`` to ``tier``/``fold_depth`` and hold it under ``name``."""
        if not name:
            raise MemoryHierarchyError("resident name is required")
        tier = MemoryTier(tier)
        depth = self._tier_depth(tier, self.hbm_max_depth) if fold_depth is None else int(fold_depth)
        if depth < 0:
            raise MemoryHierarchyError("fold_depth must be non-negative")
        resident = TierResident(name=name, tier=tier, state=phi_fold(array, depth=depth))
        self._residents[name] = resident
        logger.debug(
            "store %r at %s (depth %d, retained %d/%d)",
            name,
            tier.name,
            depth,
            resident.retained_size,
            resident.original_size,
        )
        return resident

    def read(self, name: str) -> np.ndarray:
        """Reconstruct the resident payload element-exactly."""
        return phi_unfold(self._resident(name).state)

    def load(self, name: str, tier: MemoryTier | None = None) -> NumericFoldState:
        """Return the folded state, optionally requiring a specific tier.

        This is the July ``load`` capability.  ``read`` remains the modern API
        for obtaining reconstructed values.
        """
        resident = self._resident(name)
        if tier is not None and resident.tier != MemoryTier(tier):
            raise MemoryHierarchyError(
                f"resident {name!r} is at {resident.tier.name}, not {MemoryTier(tier).name}"
            )
        return resident.state

    def _resident(self, name: str) -> TierResident:
        resident = self._residents.get(name)
        if resident is None:
            raise MemoryHierarchyError(f"no resident named {name!r}")
        return resident

    # -- tier transitions --------------------------------------------------

    def _refold_at_tier(self, resident: TierResident, tier: MemoryTier) -> TierResident:
        tier = MemoryTier(tier)
        depth = self._tier_depth(tier, self.hbm_max_depth)
        resident.state = phi_fold(phi_unfold(resident.state), depth=depth)
        resident.tier = tier
        return resident

    def promote(self, name: str, to_tier: MemoryTier | None = None) -> TierResident:
        """Move toward REGISTER, one level by default or directly to ``to_tier``."""
        resident = self._resident(name)
        target = (
            MemoryTier(max(int(MemoryTier.REGISTER), int(resident.tier) - 1))
            if to_tier is None
            else MemoryTier(to_tier)
        )
        if int(target) > int(resident.tier):
            raise MemoryHierarchyError("promotion target must be shallower than current tier")
        if target == resident.tier:
            return resident
        self._promotion_count += 1
        return self._refold_at_tier(resident, target)

    def demote(self, name: str, to_tier: MemoryTier | None = None) -> TierResident:
        """Move toward HBM, one level by default or directly to ``to_tier``."""
        resident = self._resident(name)
        if to_tier is None:
            if resident.tier == MemoryTier.HBM:
                if resident.state.depth < self.hbm_max_depth:
                    resident.state = phi_fold(
                        phi_unfold(resident.state), depth=resident.state.depth + 1
                    )
                    self._demotion_count += 1
                return resident
            target = MemoryTier(int(resident.tier) + 1)
        else:
            target = MemoryTier(to_tier)
            if int(target) < int(resident.tier):
                raise MemoryHierarchyError("demotion target must be deeper than current tier")
        if target == resident.tier:
            return resident
        self._demotion_count += 1
        return self._refold_at_tier(resident, target)

    # -- accounting --------------------------------------------------------

    def working_set_ratio(self, name: str) -> float:
        """Measured original/retained element ratio for one resident."""
        return working_set_ratio(self._resident(name).state)

    def get_working_set_ratio(self, name: str, tier: MemoryTier | None = None) -> float:
        resident = self._resident(name)
        if tier is not None and resident.tier != MemoryTier(tier):
            raise MemoryHierarchyError(
                f"resident {name!r} is at {resident.tier.name}, not {MemoryTier(tier).name}"
            )
        return working_set_ratio(resident.state)

    def get_effective_bandwidth(
        self,
        name: str,
        tier: MemoryTier | None = None,
        traditional_bandwidth_tbs: float = 3.35,
    ) -> float:
        """Return July compatibility accounting: bandwidth × measured ratio.

        This is a model-derived value, not device telemetry.  Hardware evidence
        must come from Chronus telemetry/benchmarking.
        """
        if traditional_bandwidth_tbs <= 0 or not math.isfinite(traditional_bandwidth_tbs):
            raise MemoryHierarchyError("traditional_bandwidth_tbs must be positive and finite")
        return traditional_bandwidth_tbs * self.get_working_set_ratio(name, tier)

    def tier_report(self) -> Dict[str, Dict[str, float]]:
        """Per-tier occupancy and measured representation ratio."""
        report: Dict[str, Dict[str, float]] = {
            tier.name: {"residents": 0, "original": 0, "retained": 0}
            for tier in (MemoryTier.REGISTER, MemoryTier.SRAM, MemoryTier.L2, MemoryTier.HBM)
        }
        for resident in self._residents.values():
            entry = report[resident.tier.name]
            entry["residents"] += 1
            entry["original"] += resident.original_size
            entry["retained"] += resident.retained_size
        for entry in report.values():
            original, retained = entry["original"], entry["retained"]
            entry["measured_ratio"] = (original / retained) if retained else 1.0
        return report

    def get_memory_report(self, traditional_bandwidth_tbs: float = 3.35) -> Dict[str, object]:
        """Full July-compatible hierarchy report with explicit truth boundary."""
        residents: Dict[str, Dict[str, object]] = {}
        for name, resident in self._residents.items():
            ratio = working_set_ratio(resident.state)
            residents[name] = {
                "tier": resident.tier.name,
                "fold_depth": resident.state.depth,
                "retained_size": resident.retained_size,
                "original_size": resident.original_size,
                "dtype": resident.dtype.name,
                "layout": resident.layout,
                "content_hash": resident.content_hash,
                "integrity_verified": resident.verify_integrity(),
                "measured_working_set_ratio": ratio,
                "effective_bandwidth_tbs_model": traditional_bandwidth_tbs * ratio,
            }
        return {
            "residents": residents,
            "tiers": self.tier_report(),
            "promotions": self._promotion_count,
            "demotions": self._demotion_count,
            "evictions": self._eviction_count,
            "truth_class": "measured_representation_plus_model_arithmetic",
            "effective_bandwidth_is_hardware_measurement": False,
        }


# -- TopologicalIntegrityGate ------------------------------------------------


@dataclass(frozen=True)
class IntegrityVerdict:
    """Machine-checkable gate result for one tensor operation."""

    op: str
    sequence: int
    reconstruction_error: float
    norm_ratio: float
    chronology_ok: bool
    passed: bool
    detail: str = ""


class TopologicalIntegrityGate:
    """Verifies every tensor-core/fold operation before its result is trusted."""

    def __init__(self, tolerance: float = 1e-10, spectral_band: float = 1e-6):
        if tolerance <= 0 or not math.isfinite(tolerance):
            raise MemoryHierarchyError("tolerance must be positive and finite")
        if spectral_band <= 0 or not math.isfinite(spectral_band):
            raise MemoryHierarchyError("spectral_band must be positive and finite")
        self.tolerance = float(tolerance)
        self.spectral_band = float(spectral_band)
        self._last_sequence = -1
        self._counter = itertools.count()
        self._verdicts = []

    def next_sequence(self) -> int:
        return next(self._counter)

    @property
    def verdicts(self) -> Tuple[IntegrityVerdict, ...]:
        return tuple(self._verdicts)

    @property
    def pass_rate(self) -> float:
        if not self._verdicts:
            return 1.0
        return sum(v.passed for v in self._verdicts) / len(self._verdicts)

    def verify(
        self,
        op: str,
        sequence: int,
        expected: np.ndarray,
        actual: np.ndarray,
        input_norm: float,
        output_norm: float,
        expected_norm_ratio: Optional[Tuple[float, float]] = None,
    ) -> IntegrityVerdict:
        chronology_ok = sequence > self._last_sequence
        if chronology_ok:
            self._last_sequence = sequence
        expected_array = np.asarray(expected, dtype=np.float64)
        actual_array = np.asarray(actual, dtype=np.float64)
        if expected_array.shape != actual_array.shape:
            error = float("inf")
        elif actual_array.size:
            error = float(np.max(np.abs(actual_array - expected_array)))
        else:
            error = 0.0
        ratio = (output_norm / input_norm) if input_norm > 0 else 1.0
        spectral_ok = True
        if expected_norm_ratio is not None:
            lo, hi = expected_norm_ratio
            spectral_ok = (lo - self.spectral_band) <= ratio <= (hi + self.spectral_band)
        reconstruction_ok = error <= self.tolerance
        passed = chronology_ok and reconstruction_ok and spectral_ok
        verdict = IntegrityVerdict(
            op=op,
            sequence=sequence,
            reconstruction_error=error,
            norm_ratio=ratio,
            chronology_ok=chronology_ok,
            passed=passed,
            detail=(
                ""
                if passed
                else (
                    f"reconstruction={error:.3e} (tol {self.tolerance:.1e}), "
                    f"norm_ratio={ratio:.6f}, chronology={chronology_ok}"
                )
            ),
        )
        self._verdicts.append(verdict)
        if not passed:
            logger.warning("integrity gate rejected op %r: %s", op, verdict.detail)
        return verdict

    def verify_fold(
        self, name: str, original: np.ndarray, state: NumericFoldState
    ) -> IntegrityVerdict:
        seq = self.next_sequence()
        error = reconstruction_error(original, state)
        in_norm = float(np.linalg.norm(np.asarray(original, dtype=np.float64)))
        out_norm = float(np.linalg.norm(phi_unfold(state).ravel()))
        chronology_ok = seq > self._last_sequence
        if chronology_ok:
            self._last_sequence = seq
        ratio = (out_norm / in_norm) if in_norm > 0 else 1.0
        passed = (
            chronology_ok and error <= self.tolerance and abs(ratio - 1.0) <= self.spectral_band
        )
        verdict = IntegrityVerdict(
            op=f"fold:{name}",
            sequence=seq,
            reconstruction_error=error,
            norm_ratio=ratio,
            chronology_ok=chronology_ok,
            passed=passed,
        )
        self._verdicts.append(verdict)
        return verdict

    def verify_roundtrip(self, data: np.ndarray, depth: int) -> Dict[str, object]:
        """July-compatible fold→unfold integrity gate."""
        original = np.asarray(data, dtype=np.float64)
        state = phi_fold(original, depth=int(depth))
        verdict = self.verify_fold("roundtrip", original, state)
        return {
            "passed": verdict.passed,
            "reconstruction_error": verdict.reconstruction_error,
            "chronology_valid": verdict.chronology_ok,
            "spectral_preserved": abs(verdict.norm_ratio - 1.0) <= self.spectral_band,
            "depth": int(depth),
        }

    def get_metrics(self) -> Dict[str, object]:
        errors = [v.reconstruction_error for v in self._verdicts]
        passed = sum(v.passed for v in self._verdicts)
        return {
            "checks_performed": len(self._verdicts),
            "checks_passed": passed,
            "checks_failed": len(self._verdicts) - passed,
            "pass_rate": self.pass_rate,
            "max_error_observed": max(errors, default=0.0),
            "tolerance": self.tolerance,
            "spectral_band": self.spectral_band,
        }


__all__ = [
    "IntegrityVerdict",
    "MemoryHierarchyError",
    "MemoryTier",
    "PhiMemoryHierarchy",
    "TierResident",
    "TopologicalIntegrityGate",
]
