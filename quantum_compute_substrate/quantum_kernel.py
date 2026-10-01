"""
Part 9: Quantum Kernel Methods
================================
Adaptive strategies with quantum kernel computations.
"""

import numpy as np
from typing import List, Dict


class QuantumKernelProcessor:
    """Part 9: Adaptive strategies with quantum kernel methods."""

    def __init__(self, num_qubits: int = 4096):
        self.num_qubits = num_qubits
        self.feature_dim = 2 ** min(num_qubits, 8)  # Practical limit
        self.kernel_cache = {}

    def encode_state(self, x: np.ndarray) -> np.ndarray:
        """Encode classical data into quantum state."""
        psi = np.zeros(self.feature_dim, dtype=np.complex128)
        for i in range(min(len(x), self.feature_dim)):
            psi[i] = np.exp(1j * float(x[i]))
        norm = np.linalg.norm(psi)
        if norm > 0:
            psi = psi / norm
        else:
            psi[0] = 1.0
        return psi

    def hadamard_gate(self) -> np.ndarray:
        """Single-qubit Hadamard gate."""
        return np.array([[1, 1], [1, -1]], dtype=np.complex128) / np.sqrt(2)

    def rotation_gate(self, angle: float) -> np.ndarray:
        """R_y rotation gate."""
        return np.array(
            [
                [np.cos(angle / 2), -np.sin(angle / 2)],
                [np.sin(angle / 2), np.cos(angle / 2)],
            ],
            dtype=np.complex128,
        )

    def apply_gate(self, state: np.ndarray, gate: np.ndarray, qubit: int) -> np.ndarray:
        """Apply single-qubit gate to state vector."""
        dim = len(state)
        n = int(np.log2(dim)) if dim > 1 else 1
        if dim == 2:
            return gate @ state

        U = np.eye(1, dtype=np.complex128)
        for i in range(n):
            U = np.kron(U, gate if i == qubit else np.eye(2, dtype=np.complex128))
        return U @ state

    def quantum_feature_map(self, x: np.ndarray) -> np.ndarray:
        """Map classical data to quantum feature space."""
        psi = self.encode_state(x)
        n = int(np.log2(self.feature_dim)) if self.feature_dim > 1 else 1
        for i in range(min(n, 8)):
            psi = self.apply_gate(psi, self.hadamard_gate(), i)
            angle = float(x[i % len(x)]) * np.pi / 2 if len(x) > 0 else 0
            psi = self.apply_gate(psi, self.rotation_gate(angle), i)
        return psi

    def compute_quantum_kernel(self, x_i: np.ndarray, x_j: np.ndarray) -> float:
        """k(x,y) = |<phi(x)|phi(y)>|^2"""
        key = (hash(x_i.tobytes()), hash(x_j.tobytes()))
        if key in self.kernel_cache:
            return self.kernel_cache[key]

        phi_i = self.quantum_feature_map(x_i)
        phi_j = self.quantum_feature_map(x_j)
        inner_product = float(np.abs(np.conj(phi_i).T @ phi_j) ** 2)

        self.kernel_cache[key] = inner_product
        return inner_product

    def compute_kernel_matrix(self, data: List[np.ndarray]) -> np.ndarray:
        """Full kernel matrix."""
        n = len(data)
        K = np.zeros((n, n))
        for i in range(n):
            for j in range(i, n):
                K[i, j] = self.compute_quantum_kernel(data[i], data[j])
                K[j, i] = K[i, j]
        return K

    def adaptive_compute_strategy(self, conditions: Dict) -> Dict:
        """Adapt strategy using quantum kernel."""
        conditions = self.conditions_to_vector(conditions)
        patterns = self.get_historical_patterns()
        if patterns:
            all_data = [conditions] + patterns
            similarities = self.compute_kernel_matrix(all_data)
            best_idx = int(np.argmax(similarities[0, 1:])) if len(patterns) > 0 else 0
            best_pattern = patterns[best_idx] if best_idx < len(patterns) else conditions
        else:
            best_pattern = conditions

        return self.adapt_parameters(best_pattern)

    def conditions_to_vector(self, conditions: Dict) -> np.ndarray:
        """Convert pool conditions to feature vector."""
        return np.array(
            [conditions.get("difficulty", 100), conditions.get("time", 0)], dtype=np.float64
        )

    def get_historical_patterns(self) -> List[np.ndarray]:
        """Get historical compute patterns."""
        return [
            np.array([100, 0], dtype=np.float64),
            np.array([50, 1], dtype=np.float64),
            np.array([200, 2], dtype=np.float64),
        ]

    def adapt_parameters(self, pattern: np.ndarray) -> Dict:
        """Adapt parameters based on pattern."""
        return {
            "nonce": int(pattern[0]) if len(pattern) > 0 else 0,
            "difficulty": float(pattern[0]) if len(pattern) > 0 else 100,
            "time": float(pattern[1]) if len(pattern) > 1 else 0,
        }

    def quantum_kernel_pca(self, data: List[np.ndarray], n_components: int) -> np.ndarray:
        """Kernel PCA with quantum kernel."""
        K = self.compute_kernel_matrix(data)
        n = len(data)
        one_n = np.ones((n, n)) / n
        K_centered = K - one_n @ K - K @ one_n + one_n @ K @ one_n

        eigvals, eigvecs = np.linalg.eigh(K_centered)
        idx = np.argsort(eigvals)[::-1]
        eigvals = eigvals[idx]
        eigvecs = eigvecs[:, idx]

        n_comp = min(n_components, len(eigvals))
        components = eigvecs[:, :n_comp]
        for i in range(n_comp):
            if eigvals[i] > 1e-12:
                components[:, i] /= np.sqrt(eigvals[i])

        return components

    def get_specs(self) -> dict:
        return {
            "num_qubits": self.num_qubits,
            "feature_dim": self.feature_dim,
            "kernel_cache_size": len(self.kernel_cache),
        }
