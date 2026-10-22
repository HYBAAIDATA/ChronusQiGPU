"""HYBA Data — data-class eligibility gate for PULVINI external claims.

Doctrine: PULVINI applies to structured numerical / φ-pattern working sets only.
Universal compression is RESTRICTED until elevated to honest structured scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Sequence, Union

import numpy as np

ArrayLike = Union[np.ndarray, Sequence[float]]


class DataClass(str, Enum):
    STRUCTURED_NUMERICAL = "structured_numerical"
    PHI_PATTERN = "phi_pattern"
    SPARSE_STRUCTURED = "sparse_structured"
    ARBITRARY_BYTES = "arbitrary_bytes"
    UNKNOWN = "unknown"


ELIGIBLE_FOR_EXTERNAL = {
    DataClass.STRUCTURED_NUMERICAL,
    DataClass.PHI_PATTERN,
    DataClass.SPARSE_STRUCTURED,
}


@dataclass(frozen=True)
class EligibilityResult:
    eligible: bool
    data_class: DataClass
    reason: str
    stats: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "eligible": self.eligible,
            "data_class": self.data_class.value,
            "reason": self.reason,
            "stats": self.stats,
        }


def _as_float_array(x: ArrayLike) -> np.ndarray:
    arr = np.asarray(x, dtype=np.float64).ravel()
    if arr.size == 0:
        raise ValueError("Empty array is not eligible")
    return arr


def classify_array(x: ArrayLike) -> EligibilityResult:
    """Heuristic eligibility classifier for external claim gating.

    This does not invent compression performance — it only gates whether a
    dataset is in the documented eligible class for BOUNDED external language.
    """
    arr = _as_float_array(x)
    finite = np.isfinite(arr)
    if not np.all(finite):
        return EligibilityResult(
            False,
            DataClass.UNKNOWN,
            "Non-finite values present",
            {"size": int(arr.size), "finite_frac": float(finite.mean())},
        )

    # sparse structured
    zero_frac = float(np.mean(arr == 0.0))
    # smoothness proxy: lag-1 correlation
    if arr.size >= 4:
        a = arr[:-1]
        b = arr[1:]
        if np.std(a) > 0 and np.std(b) > 0:
            corr = float(np.corrcoef(a, b)[0, 1])
        else:
            corr = 0.0
    else:
        corr = 0.0

    # dynamic range
    amin, amax = float(arr.min()), float(arr.max())
    span = amax - amin
    stats = {
        "size": int(arr.size),
        "zero_frac": zero_frac,
        "lag1_corr": corr,
        "min": amin,
        "max": amax,
        "span": span,
        "std": float(arr.std()),
    }

    if zero_frac >= 0.5 and corr >= 0.2:
        dc = DataClass.SPARSE_STRUCTURED
        ok = True
        reason = "Sparse with residual structure"
    elif abs(corr) >= 0.35:
        dc = DataClass.STRUCTURED_NUMERICAL
        ok = True
        reason = "Structured numerical (lag-1 correlation)"
    elif span > 0 and float(arr.std()) / max(span, 1e-12) < 0.45 and abs(corr) >= 0.15:
        dc = DataClass.PHI_PATTERN
        ok = True
        reason = "Smooth / φ-pattern-like numerical series"
    else:
        dc = DataClass.ARBITRARY_BYTES
        ok = False
        reason = "Insufficient structure for external PULVINI claims"

    eligible = ok and dc in ELIGIBLE_FOR_EXTERNAL
    return EligibilityResult(eligible, dc, reason, stats)


def assert_eligible(x: ArrayLike, *, for_external_claim: bool = True) -> EligibilityResult:
    res = classify_array(x)
    if for_external_claim and not res.eligible:
        raise PermissionError(
            "Dataset not eligible for external PULVINI claims: "
            f"{res.data_class.value} — {res.reason}. "
            "Universal compression is RESTRICTED — elevate to structured/φ-pattern scope only."
        )
    return res
