"""Deep multi-angle variational ansatz on the existing 32-face VQC graph.

The module adds a bounded 4 x 32 x 3 parameter program without copying Tensor
or Chronus. Tensor remains the logical representation owner and Chronus remains
the physical execution owner. This NumPy path is the deterministic reference;
it makes no compression, device-speed, or consensus-authority claim.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np


@dataclass(frozen=True)
class LayeredVariationalResult:
    distribution: np.ndarray
    state: np.ndarray
    energy: float
    parameters: np.ndarray
    loss_curve: list[float]
    grad_norm_curve: list[float]
    layers: int
    evaluations: int
    state_audit: dict[str, Any]


class LayeredVariationalAnsatz:
    """Multi-angle graph ansatz with gamma, chi and eta per face and layer."""

    def __init__(self, adjacency: np.ndarray, layers: int = 4) -> None:
        graph = np.asarray(adjacency, dtype=np.float64)
        if graph.ndim != 2 or graph.shape[0] != graph.shape[1]:
            raise ValueError("adjacency must be square")
        if graph.shape[0] < 2 or not np.all(np.isfinite(graph)):
            raise ValueError("adjacency must contain at least two finite faces")
        if np.any(graph < 0) or not np.allclose(graph, graph.T, atol=1e-12):
            raise ValueError("adjacency must be symmetric and non-negative")
        if not np.allclose(np.diag(graph), 0.0, atol=1e-12):
            raise ValueError("adjacency diagonal must be zero")
        self.layers = int(layers)
        if self.layers < 1:
            raise ValueError("layers must be positive")
        self.adjacency = graph.copy()
        self.n = graph.shape[0]
        degree = np.maximum(graph.sum(axis=1), 1.0)
        self.mixer = graph / np.sqrt(degree[:, None] * degree[None, :])
        self.mixer_eigenvalues, self.mixer_eigenvectors = np.linalg.eigh(self.mixer)

    @classmethod
    def from_midas_ranker(cls, ranker: Any) -> "LayeredVariationalAnsatz":
        """Reuse the ranker's validated graph without transferring ownership."""
        return cls(ranker.adjacency, layers=int(ranker.config.num_layers))

    @property
    def parameter_count(self) -> int:
        return self.layers * self.n * 3

    def _state(self, probability: np.ndarray) -> np.ndarray:
        values = np.asarray(probability, dtype=np.float64)
        if values.shape != (self.n,) or not np.all(np.isfinite(values)):
            raise ValueError(f"probability must contain {self.n} finite values")
        if np.any(values < 0) or float(values.sum()) <= 0.0:
            raise ValueError("probability must be non-negative with positive mass")
        values = values / float(values.sum())
        return np.sqrt(values).astype(np.complex128)

    def evolve(
        self,
        probability: np.ndarray,
        resonance_weights: np.ndarray,
        theta: np.ndarray,
    ) -> np.ndarray:
        expected = (self.layers, self.n, 3)
        parameters = np.asarray(theta, dtype=np.float64)
        weights = np.asarray(resonance_weights, dtype=np.float64)
        if parameters.shape != expected or not np.all(np.isfinite(parameters)):
            raise ValueError(f"theta must contain finite values with shape {expected}")
        if weights.shape != (self.n,) or not np.all(np.isfinite(weights)):
            raise ValueError(
                f"resonance_weights must contain {self.n} finite values"
            )
        psi = self._state(probability)
        for layer in range(self.layers):
            gamma = parameters[layer, :, 0]
            chi = parameters[layer, :, 1]
            eta = parameters[layer, :, 2]
            psi *= np.exp(-1j * (gamma * weights + chi * weights**2))
            coefficients = self.mixer_eigenvectors.T @ psi
            psi = self.mixer_eigenvectors @ (
                np.exp(-1j * self.mixer_eigenvalues) * coefficients
            )
            psi *= np.exp(-1j * eta)
        norm = float(np.linalg.norm(psi))
        if not np.isfinite(norm) or norm <= 1e-15:
            raise FloatingPointError("variational state lost finite norm")
        return psi / norm

    def energy(
        self,
        probability: np.ndarray,
        resonance_weights: np.ndarray,
        theta: np.ndarray,
        objective_matrix: np.ndarray,
    ) -> float:
        objective = np.asarray(objective_matrix, dtype=np.complex128)
        if objective.shape != (self.n, self.n) or not np.all(
            np.isfinite(objective)
        ):
            raise ValueError(
                f"objective_matrix must be finite with shape {(self.n, self.n)}"
            )
        if not np.allclose(objective, objective.conj().T, atol=1e-12):
            raise ValueError("objective_matrix must be Hermitian")
        psi = self.evolve(probability, resonance_weights, theta)
        return float(np.real(np.vdot(psi, objective @ psi)))


class FisherNaturalGradientTrainer:
    """Central-difference trainer with an EMA diagonal empirical Fisher."""

    def __init__(
        self,
        ansatz: LayeredVariationalAnsatz,
        *,
        learning_rate: float = 0.08,
        damping: float = 1e-2,
        ema_beta: float = 0.9,
        finite_diff_eps: float = 1e-4,
        max_backtracks: int = 8,
    ) -> None:
        if learning_rate <= 0 or damping <= 0 or finite_diff_eps <= 0:
            raise ValueError(
                "learning_rate, damping and finite_diff_eps must be positive"
            )
        if not 0 <= ema_beta < 1 or max_backtracks < 0:
            raise ValueError("invalid EMA or backtracking configuration")
        self.ansatz = ansatz
        self.learning_rate = float(learning_rate)
        self.damping = float(damping)
        self.ema_beta = float(ema_beta)
        self.finite_diff_eps = float(finite_diff_eps)
        self.max_backtracks = int(max_backtracks)

    def _gradient(
        self,
        probability: np.ndarray,
        weights: np.ndarray,
        theta: np.ndarray,
        objective: np.ndarray,
    ) -> tuple[np.ndarray, int]:
        epsilon = self.finite_diff_eps
        gradient = np.zeros_like(theta)
        flat = theta.reshape(-1)
        output = gradient.reshape(-1)
        candidate = flat.copy()
        shape = theta.shape
        for index in range(flat.size):
            candidate[index] = flat[index] + epsilon
            plus = self.ansatz.energy(
                probability, weights, candidate.reshape(shape), objective
            )
            candidate[index] = flat[index] - epsilon
            minus = self.ansatz.energy(
                probability, weights, candidate.reshape(shape), objective
            )
            candidate[index] = flat[index]
            output[index] = (plus - minus) / (2.0 * epsilon)
        return gradient, 2 * flat.size

    def train(
        self,
        probability: np.ndarray,
        resonance_weights: np.ndarray,
        objective_matrix: np.ndarray,
        *,
        initial_theta: Optional[np.ndarray] = None,
        steps: int = 80,
        seed: int = 0,
    ) -> LayeredVariationalResult:
        shape = (self.ansatz.layers, self.ansatz.n, 3)
        if int(steps) < 1:
            raise ValueError("steps must be positive")
        if initial_theta is None:
            theta = 0.1 * np.random.default_rng(seed).standard_normal(shape)
        else:
            theta = np.asarray(initial_theta, dtype=np.float64).copy()
            if theta.shape != shape or not np.all(np.isfinite(theta)):
                raise ValueError(f"initial_theta must be finite with shape {shape}")
        fisher_diagonal = np.zeros_like(theta)
        losses: list[float] = []
        gradient_norms: list[float] = []
        evaluations = 0
        for step in range(int(steps)):
            current = self.ansatz.energy(
                probability, resonance_weights, theta, objective_matrix
            )
            evaluations += 1
            losses.append(current)
            gradient, used = self._gradient(
                probability, resonance_weights, theta, objective_matrix
            )
            evaluations += used
            gradient_norms.append(float(np.linalg.norm(gradient)))
            fisher_diagonal = (
                self.ema_beta * fisher_diagonal
                + (1.0 - self.ema_beta) * gradient**2
            )
            correction = 1.0 - self.ema_beta ** (step + 1)
            natural_gradient = gradient / (
                np.sqrt(fisher_diagonal / correction) + self.damping
            )
            rate = self.learning_rate
            for _ in range(self.max_backtracks + 1):
                proposal = theta - rate * natural_gradient
                proposal_energy = self.ansatz.energy(
                    probability,
                    resonance_weights,
                    proposal,
                    objective_matrix,
                )
                evaluations += 1
                if proposal_energy <= current + 1e-12:
                    theta = proposal
                    break
                rate *= 0.5
        state = self.ansatz.evolve(probability, resonance_weights, theta)
        energy = self.ansatz.energy(
            probability, resonance_weights, theta, objective_matrix
        )
        evaluations += 1
        distribution = np.abs(state) ** 2
        distribution /= float(distribution.sum())
        audit = {
            "dimension": self.ansatz.n,
            "state_norm": float(np.linalg.norm(state)),
            "dtype": str(state.dtype),
            "storage_bytes": int(state.nbytes),
            "backend": "numpy_reference",
            "tensor_compression_claimed": False,
            "consensus_authority": False,
        }
        return LayeredVariationalResult(
            distribution=distribution,
            state=state,
            energy=energy,
            parameters=theta,
            loss_curve=losses,
            grad_norm_curve=gradient_norms,
            layers=self.ansatz.layers,
            evaluations=evaluations,
            state_audit=audit,
        )


__all__ = [
    "FisherNaturalGradientTrainer",
    "LayeredVariationalAnsatz",
    "LayeredVariationalResult",
]
