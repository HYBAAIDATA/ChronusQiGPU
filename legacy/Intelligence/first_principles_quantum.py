"""
Intelligence/first_principles_quantum.py — First-Principles Quantum Mathematical Substrate

Re-exports exact complex linear algebra from quantum_tensor.py (Python port of
first_principles_quantum.ts) adhering to AGENTS.md Foundational Axioms.
"""

from __future__ import annotations

from .quantum_tensor import (
    Complex,
    ComplexVector,
    ComplexMatrix,
    DensityMatrix,
    Observable,
    UnitaryEvolution,
    ProjectiveMeasurement,
    Hadamard,
    PauliX,
    PauliY,
    PauliZ,
    exact_hadamard,
    exact_qft_matrix,
    create_bell_state,
)

__all__ = [
    "Complex",
    "ComplexVector",
    "ComplexMatrix",
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
