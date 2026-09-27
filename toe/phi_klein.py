"""Phi-weighted Klein fold. Calls through poincare_golden_11d. No second metric."""

from __future__ import annotations

from typing import Tuple

import numpy as np

from toe.poincare_golden_11d import (
    GPU_PUNCH_IDS,
    LUCAS_TABLE,
    compute_poincare_norm_sq,
    fold_poincare_11d_vector,
    unfold_poincare_11d_vector,
)

PUNCH_ISA = {
    "fold": GPU_PUNCH_IDS["poincare_fold"],
    "unfold": GPU_PUNCH_IDS["poincare_unfold"],
    "geodesic": GPU_PUNCH_IDS["geodesic_distance"],
    "mint": GPU_PUNCH_IDS["mint_certificate"],
    "manifold": GPU_PUNCH_IDS["manifold_compute"],
    "phi_filter": GPU_PUNCH_IDS["phi_filter_score"],
}

HOROSPHERES = tuple(int(x) for x in LUCAS_TABLE[:11])


def phi_norm(x) -> float:
    return compute_poincare_norm_sq(x)


def fold(x) -> Tuple[np.ndarray, int]:
    return fold_poincare_11d_vector(np.asarray(x, dtype=np.float64))


def unfold(y) -> np.ndarray:
    return unfold_poincare_11d_vector(y)


def klein_identity(x) -> bool:
    """‖f(x)‖_φ² = ‖x‖_φ² / (1 + ‖x‖_φ²) < 1."""
    vec = np.asarray(x, dtype=np.float64).reshape(11)
    n = phi_norm(vec)
    folded, _ = fold(vec)
    left = phi_norm(folded)
    right = n / (1.0 + n) if n >= 0 else 1.0
    return left < 1.0 and abs(left - right) < 1e-12
