"""
Part 3: Density Operators
=========================
Mixed state operations with entropy tracking.
"""

import numpy as np
from typing import List


class DensityMatrixProcessor:
    """Part 3: Mixed state operations with entropy tracking."""

    def __init__(self, num_workers: int = 8192, dim: int = None):
        self.num_workers = num_workers
        self.dim = dim or min(2**12, num_workers)
        self.dim = min(self.dim, 64)  # Practical limit for density matrices
        self.rho = self.initialize_mixed_state()
        self.memory_bandwidth = 2e15  # 2 PB/s HBM4

    def initialize_mixed_state(self) -> np.ndarray:
        """Create density matrix for worker superposition (maximally mixed)."""
        p = 1.0 / self.dim
        rho = np.eye(self.dim, dtype=np.complex128) * p
        return rho

    def apply_quantum_operation(self, kraus_operators: List[np.ndarray]):
        """rho -> sum_k K_k rho K_k^dagger"""
        new_rho = np.zeros_like(self.rho)
        for K in kraus_operators:
            new_rho += K @ self.rho @ np.conj(K.T)
        self.rho = new_rho
        # Renormalize
        tr = np.trace(self.rho)
        if abs(tr) > 1e-12:
            self.rho = self.rho / tr
        return self.rho

    def measure_entropy(self) -> float:
        """von Neumann entropy S(rho) = -Tr(rho log rho)"""
        eigenvalues = np.linalg.eigvalsh(self.rho)
        eigenvalues = np.maximum(eigenvalues, 1e-12)
        return float(-np.sum(eigenvalues * np.log(eigenvalues)))

    def compute_purity(self) -> float:
        """Purity = Tr(rho^2), 1 for pure states, 1/dim for fully mixed."""
        return float(np.real(np.trace(self.rho @ self.rho)))

    def partial_trace(self, subsystem_dim: int) -> np.ndarray:
        """Partial trace over subsystem of given dimension."""
        total_dim = self.rho.shape[0]
        if subsystem_dim <= 0 or subsystem_dim > total_dim:
            return self.rho
        n_subsystems = total_dim // subsystem_dim
        if n_subsystems <= 1:
            return self.rho
        rho_reshaped = self.rho.reshape(n_subsystems, subsystem_dim, n_subsystems, subsystem_dim)
        reduced = np.trace(rho_reshaped, axis1=0, axis2=2)
        return reduced

    def mutual_information(self, dim_a: int, dim_b: int) -> float:
        """I(A:B) = S(rho_A) + S(rho_B) - S(rho_AB)"""
        rho_a = self.partial_trace(dim_a)
        rho_b = self.partial_trace(dim_b)

        eig_a = np.maximum(np.linalg.eigvalsh(rho_a), 1e-12)
        eig_b = np.maximum(np.linalg.eigvalsh(rho_b), 1e-12)

        S_a = -np.sum(eig_a * np.log(eig_a))
        S_b = -np.sum(eig_b * np.log(eig_b))
        S_ab = self.measure_entropy()

        return float(S_a + S_b - S_ab)

    def inject_error(self, error_rate: float = 0.01) -> None:
        """Inject random errors into the density matrix."""
        noise = np.random.randn(*self.rho.shape) + 1j * np.random.randn(*self.rho.shape)
        self.rho += error_rate * noise
        # Make Hermitian
        self.rho = (self.rho + np.conj(self.rho.T)) / 2
        # Renormalize
        tr = np.trace(self.rho)
        if abs(tr) > 1e-12:
            self.rho = self.rho / tr
