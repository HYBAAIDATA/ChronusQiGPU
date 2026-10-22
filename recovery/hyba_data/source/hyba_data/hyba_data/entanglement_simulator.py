"""Quantum-inspired entanglement simulator for optimization.

Generates correlated perturbations using quasi-quantum entanglement principles
to enable efficient exploration of complex optimization landscapes.

Part of the HYBA Quantum-Inspired Optimization Framework (Layer 2: Components).

Doctrine: Quantum is mathematics. Substrate-agnostic. Implement -> test -> push.
"""

from __future__ import annotations

import hashlib
import logging
import math
from typing import Any, Dict, Optional

import numpy as np

PHI = (1.0 + math.sqrt(5.0)) / 2.0

logger = logging.getLogger(__name__)


class EntanglementSimulator:
    """Quantum-inspired entanglement simulator for generating correlated perturbations.

    Leverages quasi-quantum entanglement principles to introduce tunneling effects
    and enable efficient exploration of complex optimization landscapes. Employs
    stochastic gradient estimation techniques inspired by quantum fluctuations.

    The entanglement matrix introduces correlations between variables inspired
    by quantum entanglement phenomena. The golden ratio (phi) can be used as
    a coupling constant for the entanglement strength, making the simulator
    HYBA-native.

    Attributes:
        tunneling_strength: Probability of tunneling through optimization barriers.
        perturbation_scale: Scale of stochastic perturbations for exploration.
        min_entanglement_dim: Minimum dimensionality of entanglement embedding.
        use_phi_coupling: Whether to use phi as entanglement coupling constant.
    """

    def __init__(
        self,
        tunneling_strength: float = 0.01,
        perturbation_scale: float = 0.1,
        min_entanglement_dim: int = 64,
        use_phi_coupling: bool = False,
    ):
        if not 0 <= tunneling_strength <= 1:
            raise ValueError(f"tunneling_strength must be in [0,1], got {tunneling_strength}")
        if perturbation_scale <= 0:
            raise ValueError(f"perturbation_scale must be > 0, got {perturbation_scale}")
        if min_entanglement_dim <= 0:
            raise ValueError(f"min_entanglement_dim must be > 0, got {min_entanglement_dim}")

        self.tunneling_strength = tunneling_strength
        self.perturbation_scale = perturbation_scale
        self.min_entanglement_dim = min_entanglement_dim
        self.use_phi_coupling = use_phi_coupling
        self._entanglement_cache: Dict[str, np.ndarray] = {}

    def simulate_entanglement(
        self, grad_vec: np.ndarray, variables: np.ndarray
    ) -> np.ndarray:
        """Simulate quantum entanglement to generate correlated perturbations.

        Steps:
        1. Generate entanglement matrix from current variable state
        2. Sample Laplace perturbations (fat tails help escape local minima)
        3. Apply tunneling with probability p = tunneling_strength
        4. Apply entanglement transformation: entangled = E @ tunneled

        Args:
            grad_vec: The gradient vector to perturb.
            variables: Current optimization variables (shapes entanglement).

        Returns:
            Perturbed gradient vector with entanglement effects.
        """
        dim = max(grad_vec.shape[0], self.min_entanglement_dim)

        # Generate entanglement matrix shaped by current variables
        entanglement_mat = self._generate_entanglement_matrix(dim, variables)

        # Sample perturbations from Laplace (fat tails for exploration)
        perturbations = self._sample_perturbations(grad_vec.shape)

        # Apply perturbation
        scale = self.perturbation_scale
        if self.use_phi_coupling:
            scale *= PHI
        perturbed_grad = grad_vec + scale * perturbations

        # Quantum tunneling: with prob p, reverse the gradient sign
        tunneling_mask = (
            np.random.rand(*grad_vec.shape) < self.tunneling_strength
        )
        tunneled_grad = (
            perturbed_grad * (1 - tunneling_mask)
            - perturbed_grad * tunneling_mask
        )

        # Apply entanglement: project into correlated space
        if tunneled_grad.size <= entanglement_mat.shape[0]:
            padded = np.pad(
                tunneled_grad,
                (0, entanglement_mat.shape[0] - tunneled_grad.size),
            )
            entangled = entanglement_mat @ padded
            entangled_grad = entangled[: tunneled_grad.size]
        else:
            entangled_grad = (
                entanglement_mat[: tunneled_grad.size, : tunneled_grad.size]
                @ tunneled_grad
            )

        return entangled_grad

    def _generate_entanglement_matrix(
        self, dim: int, variables: np.ndarray
    ) -> np.ndarray:
        """Generate near-orthogonal entanglement matrix via QR decomposition.

        Uses SHA-256 hash of variables as seed for deterministic but
        variable-shaped entanglement. QR on random matrix produces
        near-orthogonal Q, guaranteeing numerical stability.
        """
        var_hash = hashlib.sha256(variables.tobytes()).digest()
        seed_val = int.from_bytes(var_hash[:8], 'big')
        rng = np.random.default_rng(seed_val)

        # Construct random matrix and QR it for orthogonality
        A = rng.normal(0, 1.0 / math.sqrt(dim), (dim, dim))
        Q, _ = np.linalg.qr(A)

        # Add phi-structured correlations if coupling is enabled
        if self.use_phi_coupling:
            phi_phase = np.outer(
                np.cos(np.arange(dim) * PHI / dim),
                np.sin(np.arange(dim) * PHI / dim),
            )
            Q = Q + 0.05 * phi_phase[:dim, :dim]

        return self._normalize_matrix(Q)

    def _sample_perturbations(self, shape: tuple) -> np.ndarray:
        """Sample Laplace perturbations — fat tails help escape local minima."""
        return np.random.laplace(scale=1.0, size=shape)

    @staticmethod
    def _normalize_matrix(matrix: np.ndarray) -> np.ndarray:
        """Normalize by Frobenius norm."""
        norm = np.linalg.norm(matrix, ord="fro")
        if norm < 1e-15:
            return np.eye(matrix.shape[0]) / math.sqrt(matrix.shape[0])
        return matrix / norm

    def compute_entanglement_metrics(
        self, grad_vec: np.ndarray, variables: np.ndarray
    ) -> Dict[str, Any]:
        """Compute entanglement quality metrics."""
        entangled = self.simulate_entanglement(grad_vec, variables)
        original_norm = float(np.linalg.norm(grad_vec))
        entangled_norm = float(np.linalg.norm(entangled))
        correlation = float(np.dot(grad_vec, entangled[: len(grad_vec)])) / max(
            original_norm * entangled_norm, 1e-15
        )
        return {
            "original_norm": original_norm,
            "entangled_norm": entangled_norm,
            "norm_ratio": entangled_norm / max(original_norm, 1e-15),
            "correlation": correlation,
            "tunneling_prob": self.tunneling_strength,
            "perturbation_scale": self.perturbation_scale,
            "phi_coupling": self.use_phi_coupling,
        }
