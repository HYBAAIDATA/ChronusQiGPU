"""Consolidated Cortex Topological & Spectral Context Engine.

Deduplicates and unifies cortex_topological_context and cortex_spectral_context
with toe.topology and toe.geometry into a single first-principles module.

Emergence thesis:
Intelligence emerges from high-dimensional topological invariants (Betti numbers,
Euler characteristic) and spectral projections on Riemann/hyperbolic manifolds,
without empirical float heuristics.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from toe.topology import StateTopology, TopologicalAnalytics

SQRT5 = 5.0**0.5
PHI = (1.0 + SQRT5) / 2.0


@dataclass
class TopologicalContextResult:
    """Topological context invariants of a feature space."""

    betti_numbers: Dict[str, int]
    euler_characteristic: int
    topological_complexity: float
    dimension: int
    sample_count: int


@dataclass
class SpectralContextResult:
    """Spectral context invariants from gauge and curvature operators."""

    spectral_gap: float
    eigenvalues: List[float]
    condition_number: float
    effective_rank: int
    casimir_invariants: List[float]


class CortexTopologicalEngine:
    """Unified topological context analyzer for multi-dimensional manifolds."""

    def __init__(self, manifold_dimension: int = 10) -> None:
        self.dimension = manifold_dimension

    def analyze_context_topology(
        self, points: np.ndarray, epsilon: float = 0.5
    ) -> TopologicalContextResult:
        """Compute Betti numbers (b0, b1, b2) and Euler characteristic from point clouds."""
        points = np.asarray(points, dtype=float)
        n, d = points.shape

        # Use canonical TopologicalAnalytics for persistent Betti numbers
        analytics = TopologicalAnalytics()
        homology = analytics.compute_persistent_homology(points, epsilon=epsilon)
        b0 = int(homology.get("betti_0", 1))
        b1 = int(homology.get("betti_1", 0))
        b2 = int(homology.get("betti_2", 0))

        euler = b0 - b1 + b2
        complexity = float(b1) / float(max(1, b0)) + math.log(max(1.0, float(n)))

        return TopologicalContextResult(
            betti_numbers={"b0": b0, "b1": b1, "b2": b2},
            euler_characteristic=euler,
            topological_complexity=complexity,
            dimension=d,
            sample_count=n,
        )


class CortexSpectralEngine:
    """Unified spectral and gauge-invariant context analyzer."""

    def __init__(self, regularization: float = 1e-9) -> None:
        self.regularization = regularization

    def analyze_spectral_context(self, matrix: np.ndarray) -> SpectralContextResult:
        """Compute gauge-invariant Casimir spectrum, condition number, and spectral gap."""
        matrix = np.asarray(matrix, dtype=float)
        if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
            # Covariance embedding if not square
            gram = matrix.T @ matrix
        else:
            gram = 0.5 * (matrix + matrix.T)

        evals = np.linalg.eigvalsh(gram)
        evals = np.sort(np.maximum(evals, 0.0))

        gap = float(evals[1] - evals[0]) if len(evals) > 1 else 0.0
        cond = float(evals[-1] / max(evals[0], self.regularization)) if len(evals) > 0 else 1.0

        # Effective rank via spectral entropy
        total_p = np.sum(evals)
        if total_p > 0:
            probs = evals / total_p
            probs = probs[probs > 1e-12]
            entropy = -float(np.sum(probs * np.log(probs)))
            effective_rank = max(1, int(round(math.exp(entropy))))
        else:
            effective_rank = 1

        casimir = [float(np.sum(evals**k)) for k in (1, 2, 3)]

        return SpectralContextResult(
            spectral_gap=gap,
            eigenvalues=[float(x) for x in evals],
            condition_number=cond,
            effective_rank=effective_rank,
            casimir_invariants=casimir,
        )


__all__ = [
    "CortexSpectralEngine",
    "CortexTopologicalEngine",
    "SpectralContextResult",
    "TopologicalContextResult",
]
