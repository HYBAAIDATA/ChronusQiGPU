"""
Part 4: Quantum Natural Gradient
=================================
Geodesic optimization on quantum manifolds using Fisher information.
"""

import numpy as np
from typing import List, Callable


class QuantumNaturalGradientOptimizer:
    """Part 4: Geodesic optimization on quantum manifolds."""

    def __init__(self, num_params: int = 4096):
        self.num_params = min(num_params, 64)  # Practical limit for Fisher matrix
        self.theta = np.random.randn(self.num_params) * 0.1
        self.fisher_matrix = np.eye(self.num_params)
        self.learning_rate = 0.01
        self.epsilon = 1e-8

    def compute_quantum_fisher(self, rho: np.ndarray,
                               derivatives: List[np.ndarray]) -> np.ndarray:
        """F_ij = (1/2) * Tr(rho {L_i, L_j})"""
        L = self.compute_sld(rho, derivatives)
        F = np.zeros((self.num_params, self.num_params), dtype=np.complex128)

        for i in range(min(len(L), self.num_params)):
            for j in range(min(len(L), self.num_params)):
                anticommutator = L[i] @ L[j] + L[j] @ L[i]
                F[i, j] = 0.5 * np.trace(rho @ anticommutator)

        return np.real(F)

    def compute_sld(self, rho: np.ndarray, derivatives: List[np.ndarray]) -> List[np.ndarray]:
        """Symmetric logarithmic derivatives for Fisher information."""
        eigvals, eigvecs = np.linalg.eigh(rho)
        L = []

        for d_rho in derivatives:
            L_i = np.zeros_like(rho)
            for i in range(len(eigvals)):
                for j in range(len(eigvals)):
                    if eigvals[i] + eigvals[j] > 1e-12:
                        coeff = 2.0 / (eigvals[i] + eigvals[j])
                        elem = np.conj(eigvecs[:, i]) @ d_rho @ eigvecs[:, j]
                        L_i += coeff * elem * np.outer(eigvecs[:, i], np.conj(eigvecs[:, j]))
            L.append(L_i)

        return L

    def update_parameters(self, gradient: np.ndarray):
        """Natural gradient update: theta <- theta - eta * F^{-1} * grad"""
        F_reg = self.fisher_matrix + self.epsilon * np.eye(self.num_params)
        natural_grad = np.linalg.solve(F_reg, gradient)
        self.theta -= self.learning_rate * natural_grad
        return self.theta

    def optimize(self, loss_fn: Callable, max_iterations: int = 100) -> dict:
        """Optimize with quantum natural gradient."""
        losses = []
        for iteration in range(max_iterations):
            loss = loss_fn(self.theta)
            losses.append(loss)

            # Numerical gradient
            grad = np.zeros_like(self.theta)
            eps = 0.001
            for i in range(len(self.theta)):
                theta_plus = self.theta.copy()
                theta_plus[i] += eps
                theta_minus = self.theta.copy()
                theta_minus[i] -= eps
                grad[i] = (loss_fn(theta_plus) - loss_fn(theta_minus)) / (2 * eps)

            # Update Fisher matrix (simplified: use identity + gradient outer product)
            self.fisher_matrix = np.eye(self.num_params) + 0.01 * np.outer(grad, grad)

            self.update_parameters(grad)

            if np.linalg.norm(grad) < 1e-6:
                break

        return {
            "final_loss": losses[-1] if losses else 0,
            "initial_loss": losses[0] if losses else 0,
            "iterations": len(losses),
            "converged": len(losses) < max_iterations,
            "losses": losses,
        }

    def state_from_params(self, theta: np.ndarray) -> np.ndarray:
        """Construct density matrix from parameters."""
        n_qubits = max(1, int(np.log2(min(len(theta), 64))) if len(theta) > 0 else 1)
        n_qubits = min(n_qubits, 4)  # Practical limit
        dim = 2 ** n_qubits
        psi = np.zeros(dim, dtype=np.complex128)
        psi[0] = 1.0

        for i in range(min(n_qubits, len(theta))):
            t = theta[i]
            Rz = np.array([[np.exp(-1j * t / 2), 0],
                           [0, np.exp(1j * t / 2)]])
            psi = self.apply_gate(psi, Rz, i, n_qubits)

        return np.outer(psi, np.conj(psi))

    def apply_gate(
            self,
            state: np.ndarray,
            gate: np.ndarray,
            qubit: int,
            n_qubits: int) -> np.ndarray:
        """Apply single-qubit gate."""
        dim = len(state)
        if dim == 2:
            return gate @ state

        U = np.eye(1)
        for i in range(n_qubits):
            U = np.kron(U, gate if i == qubit else np.eye(2))

        return U @ state
