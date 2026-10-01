"""David Deutsch (1953-).

Universal quantum computer (1985). Deutsch algorithm (1985) and Deutsch-Jozsa
(1992): the first proofs that quantum computers can exponentially outperform
classical for structured problems.

    Given oracle f: {0,1}^n -> {0,1}, promised constant or balanced.
    Classical: 2^{n-1} + 1 queries in the worst case.
    Quantum:   1 query. Full stop.
"""

from __future__ import annotations
import numpy as np
from typing import Callable
from .turing import H_GATE


def deutsch_algorithm(f: Callable[[int], int]) -> str:
    """1-bit Deutsch: is f constant or balanced?

    f: {0,1} -> {0,1}. Returns "constant" or "balanced" using one query.
    We emulate the standard phase-oracle circuit:
        |0>|1> -> H H -> Uf -> H I -> measure top qubit.
        Result 0 => constant, result 1 => balanced.
    """
    # phase oracle Uf on 2 qubits: |x>|y> -> |x>|y XOR f(x)>
    Uf = np.zeros((4, 4), dtype=complex)
    for x in (0, 1):
        for y in (0, 1):
            y_new = y ^ (f(x) & 1)
            row = x * 2 + y_new
            col = x * 2 + y
            Uf[row, col] = 1.0
    state = np.array([0, 1, 0, 0], dtype=complex)  # |01>
    H2 = np.kron(H_GATE, H_GATE)
    state = H2 @ state
    state = Uf @ state
    HI = np.kron(H_GATE, np.eye(2, dtype=complex))
    state = HI @ state
    # Marginal probability that top qubit is 0:
    p_top_zero = abs(state[0]) ** 2 + abs(state[1]) ** 2
    return "constant" if p_top_zero > 0.5 else "balanced"


def deutsch_jozsa(f: Callable[[int], int], num_bits: int) -> str:
    """n-bit Deutsch-Jozsa in one query."""
    n = num_bits
    N = 2**n
    dim = 2 * N
    Uf = np.zeros((dim, dim), dtype=complex)
    for x in range(N):
        for y in (0, 1):
            y_new = y ^ (f(x) & 1)
            Uf[x * 2 + y_new, x * 2 + y] = 1.0
    # Prepare |0>^n |1>
    state = np.zeros(dim, dtype=complex)
    state[1] = 1.0
    # Hadamard on all n+1 qubits
    Hn = H_GATE
    for _ in range(n):
        Hn = np.kron(Hn, H_GATE)
    state = Hn @ state
    state = Uf @ state
    # Hadamard on the first n qubits (identity on the last)
    Hn2 = H_GATE
    for _ in range(n - 1):
        Hn2 = np.kron(Hn2, H_GATE)
    Hn2 = np.kron(Hn2, np.eye(2, dtype=complex))
    state = Hn2 @ state
    # Probability that the first n qubits are all zero:
    p_all_zero = abs(state[0]) ** 2 + abs(state[1]) ** 2
    return "constant" if p_all_zero > 0.5 else "balanced"


def deutsch_query_advantage(num_bits: int) -> dict:
    return {
        "quantum_queries": 1,
        "classical_worst_case_queries": 2 ** (num_bits - 1) + 1,
        "speedup": 2 ** (num_bits - 1),
    }
