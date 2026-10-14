"""
Real-time control (Unbuilt) -- Section 8. Continuous-time Kalman-Bucy
filter: solves the algebraic Riccati equation via the classical
Hamiltonian-matrix eigen-decomposition method (no scipy required), and
independently verifies the solution by numerically integrating the
differential Riccati equation forward in time (RK4) and checking it
converges to the same steady state.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


def solve_continuous_riccati(a: np.ndarray, c: np.ndarray, q: np.ndarray, r: np.ndarray) -> np.ndarray:
    """
    Solves 0 = A^T P + P A + Q - P C^T R^-1 C P via the classical
    Hamiltonian-matrix eigenvector method: Z = [[A, -C^T R^-1 C], [-Q, -A^T]];
    take the n eigenvectors of Z with negative-real-part eigenvalues (the
    stable invariant subspace); partition as [X;Y]; P = Y X^-1.
    """
    n = a.shape[0]
    r_inv = np.linalg.inv(r)
    z = np.block([[a, -c.T @ r_inv @ c], [-q, -a.T]])
    eigvals, eigvecs = np.linalg.eig(z)
    stable_idx = np.argsort(eigvals.real)[:n]
    stable_vecs = eigvecs[:, stable_idx]
    x = stable_vecs[:n, :]
    y = stable_vecs[n:, :]
    p = y @ np.linalg.inv(x)
    p = (p + p.conj().T) / 2
    return p.real


def integrate_differential_riccati(
    a: np.ndarray, c: np.ndarray, q: np.ndarray, r: np.ndarray, p0: np.ndarray, t_final: float, n_steps: int = 20000
) -> np.ndarray:
    """Real RK4 integration of dP/dt = A^T P + P A + Q - P C^T R^-1 C P (the
    same equation solve_continuous_riccati solves algebraically), used ONLY
    as an independent numerical cross-check of the algebraic solver above."""
    r_inv = np.linalg.inv(r)

    def deriv(p: np.ndarray) -> np.ndarray:
        return a.T @ p + p @ a + q - p @ c.T @ r_inv @ c @ p

    dt = t_final / n_steps
    p = p0.copy()
    for _ in range(n_steps):
        k1 = deriv(p)
        k2 = deriv(p + 0.5 * dt * k1)
        k3 = deriv(p + 0.5 * dt * k2)
        k4 = deriv(p + dt * k3)
        p = p + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
    return p


@dataclass
class KalmanBucyFilter:
    a: np.ndarray
    c: np.ndarray
    q: np.ndarray
    r: np.ndarray
    p: np.ndarray = field(default=None)

    def __post_init__(self) -> None:
        # The Kalman-Bucy filter needs the *estimator* Riccati equation
        # A P + P A^T + Q - P C^T R^-1 C P = 0, whereas solve_continuous_riccati
        # solves the *regulator* convention A_in^T X + X A_in + Q - X C^T R^-1 C X = 0.
        # Passing A^T as A_in makes A_in^T = A, so X solves A P + P A^T + Q - ... = 0,
        # i.e. exactly the filter equation we need.
        self.p = solve_continuous_riccati(self.a.T, self.c, self.q, self.r)
        self.gain_k = self.p @ self.c.T @ np.linalg.inv(self.r)
        self.x_hat = np.zeros(self.a.shape[0])

    def step(self, measurement: np.ndarray, u: np.ndarray, dt: float) -> np.ndarray:
        innovation = measurement - self.c @ self.x_hat
        dx = self.a @ self.x_hat + u + self.gain_k @ innovation
        self.x_hat = self.x_hat + dt * dx
        return self.x_hat


def _self_test() -> str:
    a = np.array([[0.0, 1.0], [-1.0, -0.2]])
    c = np.eye(2)
    q = 0.01 * np.eye(2)
    r = 0.1 * np.eye(2)

    p_algebraic = solve_continuous_riccati(a, c, q, r)
    residual = a.T @ p_algebraic + p_algebraic @ a + q - p_algebraic @ c.T @ np.linalg.inv(r) @ c @ p_algebraic
    assert np.max(np.abs(residual)) < 1e-6, "algebraic Riccati residual too large"
    assert np.allclose(p_algebraic, p_algebraic.T, atol=1e-9), "P must be symmetric"
    eigvals_p = np.linalg.eigvalsh(p_algebraic)
    assert np.all(eigvals_p > -1e-9), "P must be positive semi-definite"

    p_integrated = integrate_differential_riccati(a, c, q, r, np.zeros((2, 2)), t_final=200.0, n_steps=40000)
    assert np.max(np.abs(p_integrated - p_algebraic)) < 1e-3, "ODE integration must converge to the algebraic solution"

    filt = KalmanBucyFilter(a=a, c=c, q=q, r=r)
    rng = np.random.default_rng(1)
    true_x = np.array([1.0, 0.0])
    for _ in range(2000):
        true_x = true_x + 0.001 * (a @ true_x)
        z = true_x + rng.normal(0, 0.05, size=2)
        filt.step(z, np.zeros(2), dt=0.001)
    assert np.linalg.norm(filt.x_hat - true_x) < 0.5, "filter must track the true state reasonably closely"

    return "control._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())
