"""Numpy-only linear algebra helpers.

The substrate is hardware-agnostic; scipy is optional. We provide a pure-numpy
Hermitian-Pade matrix exponential to keep quantum_2026 usable without scipy.
"""

from __future__ import annotations
import numpy as np


def _is_hermitian(A: np.ndarray, tol: float = 1e-10) -> bool:
    return A.shape[0] == A.shape[1] and np.allclose(A, A.conj().T, atol=tol)


def expm(A: np.ndarray) -> np.ndarray:
    """Matrix exponential. Fast path for (skew-)Hermitian via eigendecomposition;
    scaling-and-squaring Pade fallback otherwise.
    """
    A = np.asarray(A)
    # -i * H case: spot Hermitian H behind a factor of i.
    # Try eigendecomposition of A directly (works for normal matrices).
    try:
        # For Hermitian H, np.linalg.eigh is exact and stable
        # A is often -1j * H_hermitian, which is skew-Hermitian. Handle both.
        H = 1j * A if _is_hermitian(1j * A) else (A if _is_hermitian(A) else None)
        if H is not None:
            w, V = np.linalg.eigh(H)
            # A = -1j*H => expm(A) = V diag(exp(-1j*w)) V^H
            # A =    H => expm(A) = V diag(exp(w)) V^H
            if _is_hermitian(A):
                exp_diag = np.exp(w)
            else:
                exp_diag = np.exp(-1j * w)
            return (V * exp_diag) @ V.conj().T
    except Exception:
        pass
    # General Pade scaling-and-squaring (order 6).
    norm = float(np.linalg.norm(A, ord=np.inf))
    s = max(0, int(np.ceil(np.log2(max(norm, 1e-12)))))
    B = A / (2.0**s)
    I = np.eye(A.shape[0], dtype=complex)
    # Pade order 6 coefficients
    b = [1.0, 1.0 / 2, 5.0 / 44, 1.0 / 66, 1.0 / 792, 1.0 / 15840, 1.0 / 665280]
    B2 = B @ B
    B4 = B2 @ B2
    B6 = B4 @ B2
    U = B @ (b[1] * I + b[3] * B2 + b[5] * B4)
    V = b[0] * I + b[2] * B2 + b[4] * B4 + b[6] * B6
    P = V + U
    Q = V - U
    R = np.linalg.solve(Q, P)
    for _ in range(s):
        R = R @ R
    return R
