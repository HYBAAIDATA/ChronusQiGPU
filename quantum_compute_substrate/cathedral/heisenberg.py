"""Werner Heisenberg (1901-1976).

    sigma_A * sigma_B >= |<[A, B]>| / 2

The uncertainty principle in its Robertson-Schrodinger form, plus the
Maassen-Uffink entropic strengthening -- the modern, basis-independent
uncertainty relation.
"""
from __future__ import annotations
import math
import numpy as np


def standard_deviation(A: np.ndarray, psi: np.ndarray) -> float:
    mean = np.real(psi.conj() @ A @ psi)
    A2 = A @ A
    mean2 = np.real(psi.conj() @ A2 @ psi)
    return float(math.sqrt(max(0.0, mean2 - mean ** 2)))


def robertson_schrodinger_bound(A: np.ndarray, B: np.ndarray, psi: np.ndarray) -> float:
    """|<[A, B]>| / 2 -- the RHS of the Robertson-Schrodinger inequality."""
    comm = A @ B - B @ A
    return float(abs(psi.conj() @ comm @ psi) / 2.0)


def uncertainty_product(A: np.ndarray, B: np.ndarray, psi: np.ndarray) -> float:
    return standard_deviation(A, psi) * standard_deviation(B, psi)


def maassen_uffink_bound(basis_A: np.ndarray, basis_B: np.ndarray) -> float:
    """H(A) + H(B) >= -log2(max_ij |<a_i|b_j>|^2)  (Maassen-Uffink 1988).

    basis_A, basis_B are matrices whose columns are the measurement vectors.
    """
    overlaps = np.abs(basis_A.conj().T @ basis_B) ** 2
    c = float(overlaps.max())
    return -math.log2(max(c, 1e-300))


def shannon_entropy_of_measurement(basis: np.ndarray, psi: np.ndarray) -> float:
    """H = -sum_i p_i log2 p_i for measurement in the given basis."""
    amps = basis.conj().T @ psi
    probs = np.abs(amps) ** 2
    probs = probs[probs > 1e-15]
    return float(-np.sum(probs * np.log2(probs)))
