"""Continuous-time and Szegedy discrete-time quantum walks."""

from __future__ import annotations
import numpy as np
from ._linalg import expm


def szegedy_walk_operator(P: np.ndarray) -> np.ndarray:
    """Szegedy quantization of classical Markov chain P (row-stochastic).

    U = S * (2 * Pi_A - I) where |psi_x> = sum_y sqrt(P[x,y]) |x>|y>, Pi_A =
    sum_x |psi_x><psi_x| projects on the "start" edges, and S swaps registers.
    Spectral gap of U is sqrt of classical spectral gap - quadratic speedup.
    """
    P = np.asarray(P, dtype=float)
    n = P.shape[0]
    assert P.shape == (n, n)
    # Ensure row-stochastic
    row_sum = P.sum(axis=1, keepdims=True)
    row_sum[row_sum == 0] = 1.0
    P = P / row_sum
    # psi_x = column-stack: dim n^2 vector for each x
    A = np.zeros((n * n, n))
    for x in range(n):
        for y in range(n):
            A[x * n + y, x] = np.sqrt(P[x, y])
    Pi_A = A @ A.T  # projector onto span{|psi_x>}
    I = np.eye(n * n)
    R = 2 * Pi_A - I
    # Swap operator S: |x>|y> -> |y>|x>
    S = np.zeros((n * n, n * n))
    for x in range(n):
        for y in range(n):
            S[y * n + x, x * n + y] = 1.0
    return S @ R


class ModernQWalk:
    def __init__(self, adjacency: np.ndarray) -> None:
        self.A = np.asarray(adjacency, dtype=float)
        self.n = self.A.shape[0]

    def continuous_time_walk(self, t: float) -> np.ndarray:
        D = np.diag(self.A.sum(axis=1))
        L = D - self.A
        return expm(-1j * L * t)

    def search(self, target: int, max_time: float = 10.0) -> dict:
        t_opt = min(np.pi / (2.0 * np.sqrt(max(1, self.n))), max_time)
        U = self.continuous_time_walk(t_opt)
        psi0 = np.ones(self.n, dtype=complex) / np.sqrt(self.n)
        psi = U @ psi0
        return {
            "optimal_time": float(t_opt),
            "target_probability": float(np.abs(psi[target]) ** 2),
            "final_state": psi,
            "speedup": float(np.sqrt(self.n)),
        }

    def szegedy_walk(self, P: np.ndarray | None = None) -> np.ndarray:
        if P is None:
            row = self.A.sum(axis=1, keepdims=True)
            row[row == 0] = 1.0
            P = self.A / row
        return szegedy_walk_operator(P)
