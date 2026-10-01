"""Aethel phi memory hierarchy — fold-depth memory tiers + integrity gate.

A four-tier folded hierarchy modelled on the traditional GPU memory stack:

    REGISTER (depth 0, no compression)
      -> SRAM  (depth 1, ~phi^1 retained-ratio)
      -> L2    (depth 2, ~phi^2)
      -> HBM   (depth 3+, ~phi^3+)

Promote moves a resident toward REGISTER (unfold one level); demote moves
it toward HBM (fold one level deeper). Reading always reconstructs through
:func:`aethel.phi_fold.phi_unfold` — a tier change is a representation
change, never a lossy drop: every demotion keeps the full complement set.

:class:`TopologicalIntegrityGate` is the ECC-equivalent: after each
tensor-core operation it verifies measured reconstruction error, sequence
chronology, and spectral preservation. It never asserts a property that
was not measured on the op's inputs and outputs.
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
    """A memory-hierarchy contract was violated (unknown resident, bad
    tier transition, or a capacity breach)."""


class MemoryTier(IntEnum):
    """Fold depth per tier — depth IS the compression level."""

    REGISTER = 0
    SRAM = 1
    L2 = 2
    HBM = 3


@dataclass
class TierResident:
    """One named resident held at a fold depth."""

    name: str
    tier: MemoryTier
    state: NumericFoldState

    @property
    def retained_size(self) -> int:
        return self.state.retained_size

    @property
    def original_size(self) -> int:
        return self.state.original_size


class PhiMemoryHierarchy:
    """Fold-depth memory hierarchy over :class:`NumericFoldState`.

    ``store(name, array, tier)`` folds the payload to the tier's depth.
    ``promote``/``demote`` re-fold the same payload one level up/down —
    the payload is recovered through unfold before the transition so no
    information is dropped.
    """

    def __init__(self, hbm_max_depth: int = 8) -> None:
        if hbm_max_depth < int(MemoryTier.HBM):
            raise MemoryHierarchyError(f"hbm_max_depth must be >= {int(MemoryTier.HBM)}")
        self.hbm_max_depth = int(hbm_max_depth)
        self._residents: Dict[str, TierResident] = {}

    # -- residency ---------------------------------------------------------

    def store(
        self, name: str, array: np.ndarray, tier: MemoryTier = MemoryTier.HBM
    ) -> TierResident:
        """Fold ``array`` to ``tier``'s depth and hold it under ``name``."""
        if not name:
            raise MemoryHierarchyError("resident name is required")
        depth = int(tier) if tier != MemoryTier.HBM else self.hbm_max_depth
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

    def _resident(self, name: str) -> TierResident:
        resident = self._residents.get(name)
        if resident is None:
            raise MemoryHierarchyError(f"no resident named {name!r}")
        return resident

    # -- tier transitions --------------------------------------------------

    def promote(self, name: str) -> TierResident:
        """Move the resident one tier closer to REGISTER (less folding)."""
        resident = self._resident(name)
        if resident.tier == MemoryTier.REGISTER:
            return resident
        target = MemoryTier(int(resident.tier) - 1)
        depth = int(target)
        resident.state = phi_fold(phi_unfold(resident.state), depth=depth)
        resident.tier = target
        return resident

    def demote(self, name: str) -> TierResident:
        """Move the resident one tier closer to HBM (deeper folding)."""
        resident = self._resident(name)
        if resident.tier == MemoryTier.HBM:
            if resident.state.depth < self.hbm_max_depth:
                resident.state = phi_fold(
                    phi_unfold(resident.state), depth=resident.state.depth + 1
                )
            return resident
        target = MemoryTier(int(resident.tier) + 1)
        depth = int(target) if target != MemoryTier.HBM else int(MemoryTier.HBM)
        resident.state = phi_fold(phi_unfold(resident.state), depth=depth)
        resident.tier = target
        return resident

    # -- accounting --------------------------------------------------------

    def working_set_ratio(self, name: str) -> float:
        """Measured original/retained ratio for one resident."""
        return working_set_ratio(self._resident(name).state)

    def tier_report(self) -> Dict[str, Dict[str, float]]:
        """Per-tier occupancy and measured compression — internal
        accounting, not a device property."""
        report: Dict[str, Dict[str, float]] = {
            tier.name: {"residents": 0, "original": 0, "retained": 0} for tier in MemoryTier
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
    """Verifies every tensor-core operation before its result is trusted.

    Three measured checks:
      * reconstruction — max-abs error between the unfolded inputs and the
        operation's recorded input slices is within ``tolerance``;
      * chronology — operation sequence indices are strictly increasing
        (a replayed or reordered record fails);
      * spectral preservation — ``||output|| / ||input||`` stays within
        ``spectral_band`` of the expected operator norm bounds declared
        per call (a fold may rescale magnitudes only by the operator).
    """

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
        """Gate one operation. ``expected``/``actual`` are the unfolded
        reference vs produced result; ``expected_norm_ratio`` optionally
        bounds ||out||/||in|| for the operator."""
        chronology_ok = sequence > self._last_sequence
        if chronology_ok:
            self._last_sequence = sequence
        error = (
            float(
                np.max(
                    np.abs(
                        np.asarray(actual, dtype=np.float64)
                        - np.asarray(expected, dtype=np.float64)
                    )
                )
            )
            if np.size(actual)
            else 0.0
        )
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
        """Gate a fold/unfold round-trip on measured reconstruction error."""
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


__all__ = [
    "IntegrityVerdict",
    "MemoryHierarchyError",
    "MemoryTier",
    "PhiMemoryHierarchy",
    "TierResident",
    "TopologicalIntegrityGate",
]
