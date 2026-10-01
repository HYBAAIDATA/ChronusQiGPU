"""Rolf Landauer (1927-1999).

Landauer's principle:

    E_min = kT ln 2  per irreversibly erased bit.

Computation is physical. Reversible computation is free (of Landauer cost);
irreversible erasure costs at least kT ln 2 per bit. Fredkin and Toffoli
gates realise reversible universal computation.
"""

from __future__ import annotations
import math
import numpy as np

BOLTZMANN_K = 1.380649e-23  # J / K


def landauer_cost(temperature_kelvin: float, bits_erased: int) -> float:
    """Minimum energy dissipated per irreversibly erased bit, in Joules."""
    if temperature_kelvin < 0 or bits_erased < 0:
        raise ValueError("require T >= 0, bits >= 0")
    return BOLTZMANN_K * temperature_kelvin * math.log(2) * bits_erased


def fredkin_gate() -> np.ndarray:
    """Controlled-SWAP on 3 qubits. Reversible and universal for classical
    reversible computation."""
    U = np.eye(8, dtype=complex)
    # |110> <-> |101>
    for a, b in [(0b101, 0b110)]:
        U[a, a] = 0
        U[b, b] = 0
        U[a, b] = 1
        U[b, a] = 1
    return U


def toffoli_gate() -> np.ndarray:
    """Controlled-controlled-NOT (CCX). Reversible and universal for classical."""
    U = np.eye(8, dtype=complex)
    U[6, 6] = 0
    U[7, 7] = 0
    U[6, 7] = 1
    U[7, 6] = 1
    return U


def is_reversible(gate: np.ndarray, atol: float = 1e-10) -> bool:
    d = gate.shape[0]
    return bool(np.allclose(gate @ gate.conj().T, np.eye(d), atol=atol))


def reversible_computation_cost(temperature_kelvin: float, num_ops: int) -> float:
    """Reversible ops cost 0 (Landauer floor)."""
    return 0.0
