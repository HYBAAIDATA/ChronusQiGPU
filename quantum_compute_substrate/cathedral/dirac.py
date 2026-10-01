"""Paul Dirac (1902-1984).

Bra-ket notation, gamma matrices, and the Dirac equation:

    (i gamma^mu partial_mu - m) psi = 0

2026 elevation: gamma matrices as substrate primitives, Clifford algebra
verified by tests, bra/ket/inner/outer as first-class operations.
"""

from __future__ import annotations
import numpy as np


def ket(v):
    """|v>: column vector."""
    a = np.asarray(v, dtype=complex).reshape(-1, 1)
    return a


def bra(v):
    """<v|: conjugate row vector."""
    a = np.asarray(v, dtype=complex).reshape(1, -1).conj()
    return a


def inner(bra_row, ket_col) -> complex:
    """<u|v>."""
    b = np.asarray(bra_row, dtype=complex).reshape(1, -1)
    k = np.asarray(ket_col, dtype=complex).reshape(-1, 1)
    return complex((b @ k)[0, 0])


def outer(ket_col, bra_row) -> np.ndarray:
    """|u><v|."""
    k = np.asarray(ket_col, dtype=complex).reshape(-1, 1)
    b = np.asarray(bra_row, dtype=complex).reshape(1, -1)
    return k @ b


# Dirac gamma matrices in the Dirac representation.
I2 = np.eye(2, dtype=complex)
SIGMA_X = np.array([[0, 1], [1, 0]], dtype=complex)
SIGMA_Y = np.array([[0, -1j], [1j, 0]], dtype=complex)
SIGMA_Z = np.array([[1, 0], [0, -1]], dtype=complex)

GAMMA0 = np.block([[I2, np.zeros((2, 2))], [np.zeros((2, 2)), -I2]])
GAMMA1 = np.block([[np.zeros((2, 2)), SIGMA_X], [-SIGMA_X, np.zeros((2, 2))]])
GAMMA2 = np.block([[np.zeros((2, 2)), SIGMA_Y], [-SIGMA_Y, np.zeros((2, 2))]])
GAMMA3 = np.block([[np.zeros((2, 2)), SIGMA_Z], [-SIGMA_Z, np.zeros((2, 2))]])
GAMMAS = (GAMMA0, GAMMA1, GAMMA2, GAMMA3)
MINKOWSKI = np.diag([1.0, -1.0, -1.0, -1.0])


def anticommutator(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    return A @ B + B @ A


def dirac_hamiltonian(mass: float, momentum) -> np.ndarray:
    """H_Dirac = c alpha . p + beta m c^2 in natural units (c = 1).

    Here alpha_i = gamma^0 gamma^i and beta = gamma^0.
    """
    px, py, pz = momentum
    alpha_x = GAMMA0 @ GAMMA1
    alpha_y = GAMMA0 @ GAMMA2
    alpha_z = GAMMA0 @ GAMMA3
    return px * alpha_x + py * alpha_y + pz * alpha_z + mass * GAMMA0
