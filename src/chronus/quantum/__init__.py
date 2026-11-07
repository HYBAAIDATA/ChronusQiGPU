"""Exact finite-field quantum evolution for Chronus.

Quantum behavior here comes from mathematics, not vendor hardware facades:
statevectors evolve over F_257 with exact field arithmetic — no floating
point, no simulated noise, no fabricated fidelities, no external backends.
"""

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
    "OMEGA_8",
    "P",
    "SQRT2",
    "StateVector",
]
