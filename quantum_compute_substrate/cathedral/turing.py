"""Alan Turing (1912-1954).

Universal computation. In 2026:
  * Quantum universal gate set: {H, T, CNOT} is universal for BQP
    (Solovay-Kitaev: any 1-qubit unitary approximable in O(log^c(1/eps)) gates).
  * BQP witness: Deutsch-Jozsa distinguishes constant from balanced in 1 query,
    vs classical Omega(2^{n-1}) worst case.
"""
from __future__ import annotations
import math
import numpy as np

H_GATE = np.array([[1, 1], [1, -1]], dtype=complex) / math.sqrt(2.0)
S_GATE = np.array([[1, 0], [0, 1j]], dtype=complex)
T_GATE = np.array([[1, 0], [0, np.exp(1j * math.pi / 4)]], dtype=complex)
CNOT_GATE = np.array([
    [1, 0, 0, 0],
    [0, 1, 0, 0],
    [0, 0, 0, 1],
    [0, 0, 1, 0],
], dtype=complex)


def universal_gate_set():
    return {"H": H_GATE, "T": T_GATE, "CNOT": CNOT_GATE}


def solovay_kitaev_bound(epsilon: float, c: float = 3.97) -> float:
    """Number of gates from {H, T} to approximate any 1-qubit unitary to eps."""
    if epsilon <= 0:
        raise ValueError("epsilon must be positive")
    return (math.log(1.0 / epsilon)) ** c


def bqp_witness_deutsch_query_count(num_bits: int) -> dict:
    """Deutsch-Jozsa: 1 quantum query vs 2^{n-1} + 1 classical worst-case."""
    return {
        "quantum_queries": 1,
        "classical_worst_case_queries": 2 ** (num_bits - 1) + 1,
        "advantage": 2 ** (num_bits - 1),
    }


def quantum_turing_step(tape: np.ndarray, gate: np.ndarray) -> np.ndarray:
    """One step of a quantum Turing machine: apply a unitary gate to the tape state."""
    if not np.allclose(gate @ gate.conj().T, np.eye(gate.shape[0]), atol=1e-9):
        raise ValueError("gate must be unitary")
    if gate.shape[0] != tape.shape[0]:
        raise ValueError("dimension mismatch")
    return gate @ tape
