"""Erwin Schrodinger (1887-1961).

    i hbar d|psi>/dt = H |psi>

Wave mechanics, entanglement ("Verschraenkung"), and the cat -- all here.
2026 elevation: exact unitary evolution via the substrate's numpy expm,
cat states of arbitrary size, and phi-cat states that live on the fold.
"""
from __future__ import annotations
import math
import numpy as np
from ..quantum_2026._linalg import expm

PHI = (1.0 + math.sqrt(5.0)) / 2.0


def schrodinger_evolution(H: np.ndarray, psi0: np.ndarray, t: float,
                          hbar: float = 1.0) -> np.ndarray:
    """|psi(t)> = exp(-i H t / hbar) |psi(0)>."""
    if not np.allclose(H, H.conj().T, atol=1e-10):
        raise ValueError("H must be Hermitian")
    U = expm(-1j * H * t / hbar)
    return U @ psi0


def energy_expectation(H: np.ndarray, psi: np.ndarray) -> float:
    return float(np.real(psi.conj() @ H @ psi))


def cat_state(dim: int, alpha: complex) -> np.ndarray:
    """|cat> = (|alpha> + |-alpha>) / sqrt(2 + 2 exp(-2|alpha|^2))

    Fock-basis coherent state |alpha> = e^{-|alpha|^2/2} sum_n alpha^n/sqrt(n!) |n>.
    """
    n = np.arange(dim)
    coeff = np.exp(-abs(alpha) ** 2 / 2.0) * (alpha ** n) / np.sqrt(_factorials(dim))
    plus = coeff
    minus = np.exp(-abs(alpha) ** 2 / 2.0) * ((-alpha) ** n) / np.sqrt(_factorials(dim))
    cat = plus + minus
    return cat / np.linalg.norm(cat)


def phi_cat_state(dim: int) -> np.ndarray:
    """Cat state at alpha = sqrt(phi) -- lives on the fold-substrate scale."""
    return cat_state(dim, alpha=math.sqrt(PHI))


def _factorials(n: int) -> np.ndarray:
    out = np.ones(n)
    for i in range(1, n):
        out[i] = out[i - 1] * i
    return out
