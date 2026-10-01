"""John Bell (1928-1990).

CHSH:

    S = <A_0 B_0> + <A_0 B_1> + <A_1 B_0> - <A_1 B_1>

Classical (local hidden variable) bound: |S| <= 2.
Quantum (Tsirelson) bound: |S| <= 2 sqrt(2) ~ 2.8284.

Mermin-GHZ inequality: on |GHZ_n>, |<M>| = 2^(n-1), classical bound 2^((n-1)/2).
"""
from __future__ import annotations
import math
import numpy as np
from .pauli import X, Y, Z
from .einstein import correlator, singlet_state

TSIRELSON = 2.0 * math.sqrt(2.0)


def chsh_value(state: np.ndarray, A0: np.ndarray, A1: np.ndarray,
               B0: np.ndarray, B1: np.ndarray) -> float:
    return (correlator(A0, B0, state) + correlator(A0, B1, state)
            + correlator(A1, B0, state) - correlator(A1, B1, state))


def optimal_chsh_settings():
    """Settings that saturate Tsirelson on the singlet:
        A0 = Z, A1 = X
        B0 = -(Z+X)/sqrt(2), B1 = -(Z-X)/sqrt(2)
    Yields S = 2 sqrt(2).
    """
    A0 = Z
    A1 = X
    B0 = -(Z + X) / math.sqrt(2.0)
    B1 = -(Z - X) / math.sqrt(2.0)
    return A0, A1, B0, B1


def tsirelson_witness(state: np.ndarray | None = None) -> float:
    if state is None:
        state = singlet_state()
    return chsh_value(state, *optimal_chsh_settings())


def ghz_state(num_qubits: int) -> np.ndarray:
    n = 2 ** num_qubits
    v = np.zeros(n, dtype=complex)
    v[0] = 1.0 / math.sqrt(2.0)
    v[-1] = 1.0 / math.sqrt(2.0)
    return v


def mermin_ghz_operator(num_qubits: int) -> np.ndarray:
    """Mermin operator for n qubits (odd n).

    For odd n: M_n = Re[(X + iY)^{tensor n}] = sum over bitstrings with EVEN
    number of Y's, with sign (-1)^(#Y/2). Bit=0 -> X, Bit=1 -> Y.

    Standard form for n=3:  M_3 = XXX - XYY - YXY - YYX.
    On |GHZ_n> = (|0..0> + |1..1>) / sqrt(2),  <M_n> = 2^(n-1)  (odd n).
    """
    if num_qubits % 2 == 0:
        raise NotImplementedError("Mermin operator here is defined for odd n")

    def tensor(*ops):
        m = ops[0]
        for o in ops[1:]:
            m = np.kron(m, o)
        return m

    dim = 2 ** num_qubits
    M = np.zeros((dim, dim), dtype=complex)
    for mask in range(dim):
        bits = [(mask >> (num_qubits - 1 - i)) & 1 for i in range(num_qubits)]
        num_y = sum(bits)
        if num_y % 2 != 0:  # keep even Hamming weight (Re[(X+iY)^n])
            continue
        ops = [Y if b else X for b in bits]
        sign = (-1) ** (num_y // 2)
        M = M + sign * tensor(*ops)
    return M


def mermin_ghz_value(num_qubits: int) -> float:
    M = mermin_ghz_operator(num_qubits)
    psi = ghz_state(num_qubits)
    return float(np.real(psi.conj() @ M @ psi))
