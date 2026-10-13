"""Intelligence/first_principles_quantum.py — First-Principles Quantum Mathematical Substrate

Provides exact complex linear algebra, Hilbert state representations, unitary gates,
observables, and Bell state creation adhering to AGENTS.md Foundational Axioms.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from kellogg.quantum_tensor import Complex, ComplexMatrix, QuantumState

# Aliases and exact gates
ComplexVector = List[Complex]
DensityMatrix = ComplexMatrix
Observable = ComplexMatrix
UnitaryEvolution = ComplexMatrix
ProjectiveMeasurement = ComplexMatrix

# Exact Gates
Hadamard = ComplexMatrix(2, 2, [
    [Complex(1.0 / math.sqrt(2.0), 0.0), Complex(1.0 / math.sqrt(2.0), 0.0)],
    [Complex(1.0 / math.sqrt(2.0), 0.0), Complex(-1.0 / math.sqrt(2.0), 0.0)],
])

PauliX = ComplexMatrix(2, 2, [
    [Complex.ZERO, Complex.ONE],
    [Complex.ONE, Complex.ZERO],
])

PauliY = ComplexMatrix(2, 2, [
    [Complex.ZERO, Complex(0.0, -1.0)],
    [Complex(0.0, 1.0), Complex.ZERO],
])

PauliZ = ComplexMatrix(2, 2, [
    [Complex.ONE, Complex.ZERO],
    [Complex.ZERO, Complex(-1.0, 0.0)],
])


def exact_hadamard() -> ComplexMatrix:
    """Return 2x2 Hadamard gate."""
    return Hadamard


def exact_qft_matrix(n_qubits: int) -> ComplexMatrix:
    """Exact QFT matrix of dimension N = 2^n_qubits."""
    dim = 1 << n_qubits
    scale = 1.0 / math.sqrt(dim)
    data = []
    for j in range(dim):
        row = []
        for k in range(dim):
            angle = 2.0 * math.pi * (j * k) / dim
            row.append(Complex(scale * math.cos(angle), scale * math.sin(angle)))
        data.append(row)
    return ComplexMatrix(dim, dim, data)


def create_bell_state(state_type: int = 0) -> QuantumState:
    """Create maximally entangled Bell state:
    0: |Phi+> = (|00> + |11>)/sqrt(2)
    1: |Phi-> = (|00> - |11>)/sqrt(2)
    2: |Psi+> = (|01> + |10>)/sqrt(2)
    3: |Psi-> = (|01> - |10>)/sqrt(2)
    """
    inv_sqrt2 = 1.0 / math.sqrt(2.0)
    c_plus = Complex(inv_sqrt2, 0.0)
    c_minus = Complex(-inv_sqrt2, 0.0)
    z = Complex.ZERO

    if state_type == 0:
        amps = [c_plus, z, z, c_plus]
    elif state_type == 1:
        amps = [c_plus, z, z, c_minus]
    elif state_type == 2:
        amps = [z, c_plus, c_plus, z]
    elif state_type == 3:
        amps = [z, c_plus, c_minus, z]
    else:
        raise ValueError(f"Unknown Bell state type: {state_type}")

    return QuantumState(4, amps)


__all__ = [
    "Complex",
    "ComplexVector",
    "ComplexMatrix",
    "QuantumState",
    "DensityMatrix",
    "Observable",
    "UnitaryEvolution",
    "ProjectiveMeasurement",
    "Hadamard",
    "PauliX",
    "PauliY",
    "PauliZ",
    "exact_hadamard",
    "exact_qft_matrix",
    "create_bell_state",
]
