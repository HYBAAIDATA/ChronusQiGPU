#!/usr/bin/env python3
"""Create TURING quantum core modules."""

import os

BASE = r"C:\Users\leonn\Downloads\chronos-completed\turing_universal_quantum_computer\turing_universal_quantum_computer"

os.makedirs(BASE, exist_ok=True)

# Create hilbert.py
with open(os.path.join(BASE, "hilbert.py"), "w") as f:
    f.write('''"""TURING-owned Hilbert space mathematics and quantum state representation.

This module owns the mathematical model of quantum states, measurements, and
the Born distribution. It explicitly separates the mathematical distribution
from downstream seeded sampling.
"""

from __future__ import annotations

import numpy as np
from typing import Literal


class QuantumState:
    """Represents a quantum state vector in Hilbert space.

    This is a TURING-owned canonical representation. The state vector
    evolves unitarily and measurement produces a Born probability distribution.
    Downstream sampling is seeded and distinct from the quantum calculation.
    """

    def __init__(self, amplitudes: np.ndarray, basis: Literal["computational"] = "computational"):
        """Initialize a quantum state.

        Args:
            amplitudes: Complex array of state amplitudes.
            basis: Basis representation ("computational" or "custom").
        """
        self.amplitudes = np.asarray(amplitudes, dtype=complex)
        self.basis = basis
        self._dimension = self.amplitudes.shape[0]

    @property
    def dimension(self) -> int:
        """Return the Hilbert space dimension."""
        return self._dimension

    def probability_distribution(self) -> np.ndarray:
        """Compute the Born probability distribution |psi|^2.

        This is the mathematical measurement distribution - distinct from
        downstream seeded sampling.
        """
        return np.abs(self.amplitudes) ** 2

    def normalize(self) -> None:
        """Normalize the state vector."""
        norm = np.linalg.norm(self.amplitudes)
        if norm > 0:
            self.amplitudes = self.amplitudes / norm

    def evolve_unitary(self, unitary: np.ndarray) -> QuantumState:
        """Evolve the state by a unitary operator.

        Args:
            unitary: Unitary matrix acting on the state.

        Returns:
            New QuantumState with evolved amplitudes.
        """
        new_amplitudes = unitary @ self.amplitudes
        return QuantumState(new_amplitudes, basis=self.basis)

    def expect(self, observable: np.ndarray) -> float:
        """Compute the expectation value of an observable.

        Args:
            observable: Hermitian matrix representing the observable.

        Returns:
            Real expectation value <psi|O|psi>.
        """
        amps = self.amplitudes
        return float(amps.conj().T @ observable @ amps).real

    def __repr__(self) -> str:
        return f"QuantumState(dim={self._dimension}, basis={self.basis})"
''')

print("hilbert.py created")