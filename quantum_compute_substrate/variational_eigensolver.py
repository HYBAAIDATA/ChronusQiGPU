"""
Part 10: Variational Quantum Eigensolver
==========================================
Parameter optimization with variational circuits.
"""

import numpy as np
from typing import Dict


class VQEOptimizer:
    """Part 10: Parameter optimization with variational quantum eigensolver."""

    def __init__(self, num_qubits: int = 4096, layers: int = 50):
        self.num_qubits = min(num_qubits, 4)  # Practical limit
        self.target_num_qubits = 4096  # Architecture target (always 4096)
        self.layers = min(layers, 5)  # Practical limit
        self.target_layers = layers
        self.dim = 2**self.num_qubits
        self.params = self.initialize_parameters()
        self.ansatz = self.build_ansatz()
        self.H = self.build_hamiltonian()

    def initialize_parameters(self) -> np.ndarray:
        """Initialize variational parameters."""
        num_params = 2 * self.num_qubits * self.layers
        return np.random.randn(num_params) * 0.1

    def build_ansatz(self) -> callable:
        """Build parameterized circuit ansatz."""

        def ansatz(params: np.ndarray) -> np.ndarray:
            state = np.zeros(self.dim, dtype=np.complex128)
            state[0] = 1.0

            param_idx = 0
            for layer in range(self.layers):
                for qubit in range(self.num_qubits):
                    if param_idx >= len(params):
                        break
                    theta = params[param_idx]
                    Ry = np.array(
                        [
                            [np.cos(theta / 2), -np.sin(theta / 2)],
                            [np.sin(theta / 2), np.cos(theta / 2)],
                        ],
                        dtype=np.complex128,
                    )
                    state = self.apply_gate(state, Ry, qubit)
                    param_idx += 1

                    if param_idx >= len(params):
                        break
                    phi = params[param_idx]
                    Rz = np.array(
                        [
                            [np.exp(-1j * phi / 2), 0],
                            [0, np.exp(1j * phi / 2)],
                        ],
                        dtype=np.complex128,
                    )
                    state = self.apply_gate(state, Rz, qubit)
                    param_idx += 1

                # Entangling layers
                for qubit in range(0, self.num_qubits - 1, 2):
                    state = self.apply_cnot(state, qubit, qubit + 1)

            return state

        return ansatz

    def build_hamiltonian(self) -> np.ndarray:
        """Build optimization Hamiltonian."""
        n = self.num_qubits
        dim = self.dim
        H = np.zeros((dim, dim), dtype=np.complex128)

        # Diagonal: local Z fields
        for i in range(dim):
            z_sum = 0
            for q in range(n):
                z_sum += 1 if (i >> q) & 1 else -1
            H[i, i] = z_sum + np.random.randn() * 0.1

        # Off-diagonal: X rotations (simplified)
        for i in range(dim):
            for q in range(n):
                j = i ^ (1 << q)
                if j > i:
                    val = np.random.randn() * 0.1
                    H[i, j] = val
                    H[j, i] = np.conj(val)

        # Make Hermitian
        H = (H + np.conj(H.T)) / 2
        return H

    def expectation_value(self, params: np.ndarray) -> float:
        """Compute <psi|H|psi>."""
        state = self.ansatz(params)
        return float(np.real(np.conj(state).T @ self.H @ state))

    def gradient_descent(self, max_iterations: int = 100) -> np.ndarray:
        """Gradient descent optimization."""
        params = self.params.copy()
        learning_rate = 0.01
        losses = []

        for iteration in range(max_iterations):
            grad = np.zeros_like(params)
            epsilon = 0.001

            for i in range(len(params)):
                params_plus = params.copy()
                params_plus[i] += epsilon
                params_minus = params.copy()
                params_minus[i] -= epsilon
                grad[i] = (
                    self.expectation_value(params_plus) - self.expectation_value(params_minus)
                ) / (2 * epsilon)

            params -= learning_rate * grad
            loss = self.expectation_value(params)
            losses.append(loss)

            if np.linalg.norm(grad) < 1e-6:
                break

        self.params = params
        return params

    def find_optimal_config(self) -> Dict:
        """Find optimal configuration via VQE."""
        optimal_params = self.gradient_descent(max_iterations=50)
        optimal_state = self.ansatz(optimal_params)
        return self.state_to_config(optimal_state, optimal_params)

    def state_to_config(self, state: np.ndarray, params: np.ndarray = None) -> Dict:
        """Convert quantum state to configuration dict."""
        probabilities = np.abs(state) ** 2
        config = int(np.argmax(probabilities))
        energy = float(np.real(np.conj(state).T @ self.H @ state))
        return {
            "optimal_config": config,
            "energy": energy,
            "params": params.tolist() if params is not None else [],
            "num_qubits": self.num_qubits,
            "layers": self.layers,
        }

    def apply_gate(self, state: np.ndarray, gate: np.ndarray, qubit: int) -> np.ndarray:
        """Apply single-qubit gate."""
        dim = len(state)
        if dim == 2:
            return gate @ state

        n = int(np.log2(dim))
        U = np.eye(1, dtype=np.complex128)
        for i in range(n):
            U = np.kron(U, gate if i == qubit else np.eye(2, dtype=np.complex128))
        return U @ state

    def apply_cnot(self, state: np.ndarray, control: int, target: int) -> np.ndarray:
        """CNOT gate."""
        result = state.copy()
        for i in range(len(state)):
            if (i >> control) & 1:
                j = i ^ (1 << target)
                if j < len(result) and i < len(result):
                    result[i], result[j] = state[j], state[i]
        return result

    def get_specs(self) -> dict:
        return {
            "num_qubits": self.num_qubits,
            "target_num_qubits": self.target_num_qubits,
            "layers": self.layers,
            "target_layers": self.target_layers,
            "dim": self.dim,
            "num_params": len(self.params),
        }
