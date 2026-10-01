"""
Part 1: Hilbert Space Computing
================================
Quantum state space representation with Grover search support.
4,096-dimensional Hilbert space (≈12 qubit equivalent) (practical limit: 2^12 = 4096 dim).
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional


@dataclass
class QuantumComputeState:
    """Hilbert space representation with 4,096-dimensional Hilbert space (≈12 qubit equivalent)."""
    amplitudes: np.ndarray   # Complex amplitudes
    basis_dim: int           # 2^n dimensional space
    coherence_time: float    # T2 coherence in microseconds

    def __post_init__(self):
        norm = np.linalg.norm(self.amplitudes)
        if not np.isclose(norm, 1.0):
            self.amplitudes = self.amplitudes / norm

    def probability_measure(self, x: int) -> float:
        """P(x) = |<x|psi>|^2 = |alpha_x|^2"""
        return float(np.abs(self.amplitudes[x]) ** 2)

    def expectation(self, operator: np.ndarray) -> complex:
        """<psi|O|psi>"""
        return complex(np.conj(self.amplitudes).T @ operator @ self.amplitudes)


class HilbertSpaceProcessor:
    """Part 1: Quantum state evolution for compute operations."""

    def __init__(self, n_bits: int = 4096, num_workers: int = 8192):
        self.n_bits = n_bits
        self.dim = 2 ** min(n_bits, 12)  # Practical limit
        self.num_workers = num_workers
        self.state = self.initialize_uniform_superposition()

    def initialize_uniform_superposition(self) -> QuantumComputeState:
        """|psi> = (1/sqrt(N)) * sum|x>"""
        amplitudes = np.ones(self.dim, dtype=np.complex128) / np.sqrt(self.dim)
        return QuantumComputeState(amplitudes, self.dim, coherence_time=250.0)

    def check_match(self, x: int, target: int) -> bool:
        """Check if x matches target (simulated hash comparison)."""
        return x == target

    def apply_phase_oracle(self, target: int) -> QuantumComputeState:
        """Oracle U_f: |x> -> (-1)^f(x)|x>"""
        amplitudes = self.state.amplitudes.copy()
        if 0 <= target < self.dim:
            amplitudes[target] *= -1
        return QuantumComputeState(amplitudes, self.dim, self.state.coherence_time)

    def apply_diffusion(self) -> QuantumComputeState:
        """D = 2|psi><psi| - I"""
        amplitudes = self.state.amplitudes.copy()
        mean_amplitude = np.mean(amplitudes)
        transformed = 2 * mean_amplitude - amplitudes
        return QuantumComputeState(transformed, self.dim, self.state.coherence_time)

    def grover_iteration(self, target: int) -> QuantumComputeState:
        """Single Grover iteration: G = D * U_f"""
        self.state = self.apply_phase_oracle(target)
        self.state = self.apply_diffusion()
        return self.state

    def grover_search(self, target: int, iterations: Optional[int] = None) -> dict:
        """Full Grover search returning result dict."""
        if iterations is None:
            iterations = int(np.pi / 4 * np.sqrt(self.dim))
        self.state = self.initialize_uniform_superposition()
        for _ in range(iterations):
            self.grover_iteration(target)
        prob = self.state.probability_measure(target)
        return {
            "found": prob > 0.5,
            "target": target,
            "probability": prob,
            "iterations": iterations,
        }
