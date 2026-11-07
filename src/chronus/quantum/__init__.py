"""Exact finite-field quantum evolution for Chronus.

Quantum behavior here comes from mathematics, not vendor hardware facades:
statevectors evolve over F_257 with exact field arithmetic — no floating
point, no simulated noise, no fabricated fidelities, no external backends.
"""

from chronus.quantum.grover import (
    diffusion,
    grover_iterate,
    grover_trajectory,
    oracle_flip,
)
from chronus.quantum.metallic_search import (
    METALLIC_COEFFICIENTS,
    QSqrt2,
    algebraic_search,
    exact_search,
    generalized_iterate,
    one_shot_phases,
    phase_iterate,
)
from chronus.quantum.statevector import (
    I_UNIT,
    INV_SQRT2,
    MAX_QUBITS,
    OMEGA_8,
    P,
    SQRT2,
    StateVector,
)

__all__ = [
    "I_UNIT",
    "INV_SQRT2",
    "MAX_QUBITS",
    "METALLIC_COEFFICIENTS",
    "OMEGA_8",
    "P",
    "QSqrt2",
    "SQRT2",
    "StateVector",
    "algebraic_search",
    "diffusion",
    "exact_search",
    "generalized_iterate",
    "grover_iterate",
    "grover_trajectory",
    "one_shot_phases",
    "oracle_flip",
    "phase_iterate",
]
