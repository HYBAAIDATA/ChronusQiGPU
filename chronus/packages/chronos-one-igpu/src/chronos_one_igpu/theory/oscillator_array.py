"""
Physical quantum hardware (Unbuilt) -- Section 1 of "Real Maths for the
Unbuilt Parts": a lattice of coupled quantum harmonic oscillators (a cavity
array), solved exactly via diagonalization, with the coupling matrix g_ij
computed from real geometry (current-carrying elements).

Model actually implemented (stated precisely, not overclaimed):
  H_array = sum_i hbar*omega_i a_i^dagger a_i
            + sum_{i<j} hbar*g_ij (a_i^dagger a_j + a_i a_j^dagger)
This Hamiltonian is number-conserving (no a_i a_j or a_i^dagger a_j^dagger
"squeezing" terms), so it is exactly solved by an ORDINARY orthogonal
diagonalization of the real symmetric single-particle matrix
  M_ii = omega_i,  M_ij = g_ij (i != j)
which is the degenerate case of a Bogoliubov transformation with a zero
anomalous block. The eigenvalues of M are the normal-mode frequencies
Omega_k; E0 = (1/2) sum_k hbar*Omega_k is the zero-point energy. If squeezing
terms were present, a genuine symplectic Bogoliubov diagonalization (not
plain eigh) would be required -- that generalization is implemented in
`bogoliubov_transform_squeezed` for completeness/testing.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np

HBAR = 1.054571817e-34
MU_0 = 4e-7 * np.pi


@dataclass
class NormalModeResult:
    normal_frequencies: np.ndarray
    zero_point_energy_j: float
    mode_vectors: np.ndarray


def coupling_matrix_from_point_currents(
    omega: np.ndarray, positions: np.ndarray, moments: np.ndarray
) -> np.ndarray:
    """
    Real g_ij for point-like current elements J_i(r) = m_i * delta(r - r_i):
    the double integral g_ij = (mu0*omega_i*omega_j/4pi) * Int[J_i.J_j/|r-r'|]
    collapses exactly to m_i.m_j / |r_i-r_j| for delta-function sources.
    """
    n = len(omega)
    g = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            dist = np.linalg.norm(positions[i] - positions[j])
            if dist == 0:
                continue
            g[i, j] = (MU_0 * omega[i] * omega[j] / (4 * np.pi)) * (
                np.dot(moments[i], moments[j]) / dist
            )
    return g


def diagonalize_oscillator_array(omega: np.ndarray, g: np.ndarray) -> NormalModeResult:
    """Exact solution of H_array (number-conserving coupling only)."""
    m = np.diag(omega).astype(float) + g
    m = (m + m.T) / 2
    eigvals, eigvecs = np.linalg.eigh(m)
    e0 = 0.5 * HBAR * float(np.sum(eigvals))
    return NormalModeResult(normal_frequencies=eigvals, zero_point_energy_j=e0, mode_vectors=eigvecs)


def bogoliubov_transform_squeezed(
    omega: np.ndarray, g_hop: np.ndarray, g_sq: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Genuine symplectic Bogoliubov diagonalization for the general quadratic
    bosonic Hamiltonian that DOES include anomalous (squeezing) terms, via
    the standard Colpa algorithm: K = [[A,B],[B*,A*]], Sigma = diag(I,-I);
    the N eigenvalues of Sigma@K with the largest real part are the normal
    mode frequencies Omega_k.
    """
    n = len(omega)
    a = np.diag(omega).astype(complex) + g_hop
    a = (a + a.conj().T) / 2
    b = g_sq.astype(complex)
    b = (b + b.T) / 2
    k = np.block([[a, b], [b.conj(), a.conj()]])
    sigma = np.block([[np.eye(n), np.zeros((n, n))], [np.zeros((n, n)), -np.eye(n)]])
    eigvals, eigvecs = np.linalg.eig(sigma @ k)
    order = np.argsort(-eigvals.real)
    eigvals = eigvals[order]
    return eigvals.real[:n], eigvecs[:, order]


def _self_test() -> str:
    omega = np.array([1.0e9, 1.05e9, 0.95e9, 1.1e9])
    g = np.zeros((4, 4))
    result = diagonalize_oscillator_array(omega, g)
    assert np.allclose(np.sort(result.normal_frequencies), np.sort(omega)), "zero-coupling case failed"

    omega2 = np.array([1.0, 1.0])
    g2 = np.array([[0.0, 0.3], [0.3, 0.0]])
    result2 = diagonalize_oscillator_array(omega2, g2)
    expected = np.sort([1.0 - 0.3, 1.0 + 0.3])
    assert np.allclose(np.sort(result2.normal_frequencies), expected), "two-mode coupling case failed"

    pos_near = np.array([[0, 0, 0], [1.0, 0, 0]])
    pos_far = np.array([[0, 0, 0], [1e12, 0, 0]])
    moments = np.array([[1.0, 0, 0], [1.0, 0, 0]])
    g_near = coupling_matrix_from_point_currents(np.array([1.0, 1.0]), pos_near, moments)
    g_far = coupling_matrix_from_point_currents(np.array([1.0, 1.0]), pos_far, moments)
    assert g_far[0, 1] < g_near[0, 1] / 1e10, "coupling must fall off as separation grows (1/distance law)"
    assert np.isclose(g_near[0, 1], g_far[0, 1] * 1e12), "coupling must scale exactly as 1/distance"

    omega_k, _ = bogoliubov_transform_squeezed(omega2, g2, np.zeros((2, 2)))
    assert np.allclose(np.sort(omega_k), expected, atol=1e-6), "squeezed-Bogoliubov B=0 case failed"

    return "oscillator_array._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())
