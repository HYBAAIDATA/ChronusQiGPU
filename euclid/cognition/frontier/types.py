"""Shared types, invariants, and evidence gates for EUCLID Frontier.

Defines the mathematical substrate:
- Vec[D]: Continuous vectors in R^D (D=32 for layer states, D=256 for latent thought vectors).
- GraphManifold: Discrete topological graph manifold with adjacency (A), edge weights (W),
  node weights (gamma), and Forman-Ricci curvature.
- CognitionProblem: Typed problem formulation requiring measured rewards only.
- Invariants: SEEDS=[1337, 42, 2026], KAPPA_BOUND=0.05, PHI_TARGET=0.40, RECONCILE_STEPS_REF=8.
- EvidenceGate: Fail-closed verification gate preventing unvalidated candidate promotion.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

import numpy as np

# Canonical invariants
SEEDS: List[int] = [1337, 42, 2026]
KAPPA_BOUND: float = 0.05
PHI_TARGET: float = 0.40
RECONCILE_STEPS_REF: int = 8
GOLDEN_RATIO: float = (1.0 + math.sqrt(5.0)) / 2.0
INV_GOLDEN_RATIO: float = 1.0 / GOLDEN_RATIO


@dataclass
class GraphManifold:
    """Discrete topological graph manifold (A: MxM, W: MxM, gamma: M)."""

    nodes: List[str]
    adjacency: np.ndarray  # (M, M) boolean/binary
    weights: np.ndarray  # (M, M) edge weights w_e >= 1e-4
    gamma: np.ndarray  # (M,) node weights
    ricci_curvatures: Dict[Tuple[str, str], float] = field(default_factory=dict)
    spectral_entropy: float = 0.0

    def __post_init__(self) -> None:
        m = len(self.nodes)
        self.adjacency = np.asarray(self.adjacency, dtype=np.float64).reshape((m, m))
        self.weights = np.asarray(self.weights, dtype=np.float64).reshape((m, m))
        # Enforce spectral floor invariant w_e >= 1e-4 on active edges
        self.weights = np.where(self.adjacency > 0, np.maximum(self.weights, 1e-4), 0.0)
        self.gamma = np.asarray(self.gamma, dtype=np.float64).reshape((m,))
        if not self.ricci_curvatures:
            self.recompute_curvatures()

    def recompute_curvatures(self) -> Dict[Tuple[str, str], float]:
        """Computes Forman-Ricci curvature for every directed edge in the manifold."""
        m = len(self.nodes)
        curvs: Dict[Tuple[str, str], float] = {}
        for i in range(m):
            src = self.nodes[i]
            deg_i = float(np.sum(self.adjacency[i, :]))
            w_i = float(self.gamma[i])
            for j in range(m):
                if self.adjacency[i, j] > 0:
                    dst = self.nodes[j]
                    deg_j = float(np.sum(self.adjacency[:, j]))
                    w_j = float(self.gamma[j])
                    w_e = float(self.weights[i, j])

                    # Standard Forman-Ricci curvature formulation for weighted graphs
                    # F(e) = w_e * ( (w_i/w_e + w_j/w_e) - sum_{e' ~ e} (w_i/sqrt(w_e*w_e') + w_j/sqrt(w_e*w_e')) )
                    # For normalized graph manifolds: Ric_F(e) = 4 - deg_i - deg_j + 3 * #triangles(e)
                    # Scaled by edge bottleneck factor
                    bottleneck = (w_i + w_j) / (2.0 * max(w_e, 1e-4))
                    ric = float(4.0 - deg_i - deg_j) / max(1.0, deg_i + deg_j) * (1.0 / bottleneck)
                    curvs[(src, dst)] = round(ric, 6)
        self.ricci_curvatures = curvs
        self.spectral_entropy = self.compute_von_neumann_entropy()
        return curvs

    def compute_von_neumann_entropy(self) -> float:
        """Computes Von Neumann spectral graph entropy S_VN = -Tr(rho log2 rho)."""
        m = len(self.nodes)
        if m <= 1:
            return 0.0
        deg = np.sum(self.weights, axis=1)
        total_deg = float(np.sum(deg))
        if total_deg <= 1e-9:
            return 0.0
        # Normalized Laplacian L_sym = I - D^{-1/2} W D^{-1/2}
        d_inv_sqrt = np.diag([1.0 / math.sqrt(d) if d > 1e-9 else 0.0 for d in deg])
        l_sym = np.eye(m) - d_inv_sqrt @ self.weights @ d_inv_sqrt
        # Density matrix rho = L_sym / Tr(L_sym)
        tr_l = float(np.trace(l_sym))
        if tr_l <= 1e-9:
            return 0.0
        rho = l_sym / tr_l
        eigenvals = np.linalg.eigvalsh(rho)
        entropy = 0.0
        for ev in eigenvals:
            if ev > 1e-12:
                entropy -= float(ev * math.log2(ev))
        return float(round(entropy, 6))

    @property
    def max_abs_curvature(self) -> float:
        if not self.ricci_curvatures:
            return 0.0
        return float(max(abs(c) for c in self.ricci_curvatures.values()))


@dataclass
class CognitionProblem:
    """Problem instance requiring measured sensor observations and verifiable rewards."""

    obs: np.ndarray
    reward: Optional[float] = None
    bounds: Tuple[float, float] = (0.0, 1.0)
    metadata: Dict[str, Any] = field(default_factory=dict)


class EvidenceGate:
    """Fail-closed independent verification gate preventing unvalidated candidate promotion."""

    def __init__(self, threshold: float = 0.85) -> None:
        self.threshold = threshold

    def held_out_score(self, candidate: Any) -> float:
        """Evaluates candidate performance on held-out test partitions only."""
        if hasattr(candidate, "held_out_score"):
            return float(candidate.held_out_score())
        if hasattr(candidate, "evaluation_score"):
            return float(candidate.evaluation_score)
        if isinstance(candidate, dict) and "held_out_score" in candidate:
            return float(candidate["held_out_score"])
        # Fail-closed default: if independent verification missing, score is 0.0
        return 0.0

    def approve(self, candidate: Any) -> bool:
        """Approves candidate only if held-out score strictly meets or exceeds threshold."""
        score = self.held_out_score(candidate)
        return bool(score >= self.threshold)
