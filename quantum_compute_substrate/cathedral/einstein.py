"""Albert Einstein (1879-1955).

The EPR argument -- and the singlet state that carries it:

    |Psi^-> = (|01> - |10>) / sqrt(2)

Perfect anticorrelation across any shared axis. Einstein called it spooky;
the substrate calls it invariant.
"""
from __future__ import annotations
import math
import numpy as np
from .pauli import X, Y, Z


def singlet_state() -> np.ndarray:
    v = np.zeros(4, dtype=complex)
    v[1] = 1.0 / math.sqrt(2.0)
    v[2] = -1.0 / math.sqrt(2.0)
    return v


def triplet_states():
    """Three symmetric Bell states forming the S=1 triplet."""
    t_plus = np.array([1, 0, 0, 0], dtype=complex)
    t_zero = np.array([0, 1, 1, 0], dtype=complex) / math.sqrt(2.0)
    t_minus = np.array([0, 0, 0, 1], dtype=complex)
    return t_plus, t_zero, t_minus


def correlator(A: np.ndarray, B: np.ndarray, state: np.ndarray) -> float:
    """<state| A tensor B |state>."""
    op = np.kron(A, B)
    return float(np.real(state.conj() @ op @ state))


def epr_anticorrelation(axis: str = "Z") -> float:
    """<Psi^-| sigma_a tensor sigma_a |Psi^-> = -1 for any axis a."""
    op = {"X": X, "Y": Y, "Z": Z}[axis]
    return correlator(op, op, singlet_state())
