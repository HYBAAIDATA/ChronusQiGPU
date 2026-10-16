"""
Quantum metrology (Unbuilt) -- Section 6. Real quantum Fisher information
(QFI) computed from an arbitrary density matrix and generator, the
Cramer-Rao bound, and the closed-form QFI for squeezed light.
"""
from __future__ import annotations

import numpy as np


def quantum_fisher_information(rho: np.ndarray, h: np.ndarray, eig_tol: float = 1e-12) -> float:
    """
    F_Q[rho,H] = 2*sum_{i,j: li+lj>0} (li-lj)^2/(li+lj) * |<i|H|j>|^2,
    computed directly from the real eigendecomposition of rho.
    """
    eigvals, eigvecs = np.linalg.eigh(rho)
    h_eig = eigvecs.conj().T @ h @ eigvecs
    n = len(eigvals)
    total = 0.0
    for i in range(n):
        for j in range(n):
            denom = eigvals[i] + eigvals[j]
            if denom > eig_tol:
                total += ((eigvals[i] - eigvals[j]) ** 2 / denom) * abs(h_eig[i, j]) ** 2
    return 2 * total


def cramer_rao_bound(f_q: float, n_measurements: int) -> float:
    return 1.0 / np.sqrt(n_measurements * f_q)


def qfi_squeezed_light(squeezing_parameter_r: float) -> float:
    return 4 * np.sinh(squeezing_parameter_r) ** 2 + 2


def _self_test() -> str:
    rng = np.random.default_rng(0)
    psi = rng.normal(size=4) + 1j * rng.normal(size=4)
    psi /= np.linalg.norm(psi)
    rho = np.outer(psi, psi.conj())
    h = rng.normal(size=(4, 4))
    h = (h + h.T) / 2
    f_q = quantum_fisher_information(rho, h)
    mean_h = np.real(psi.conj() @ h @ psi)
    mean_h2 = np.real(psi.conj() @ h @ h @ psi)
    variance = mean_h2 - mean_h ** 2
    assert abs(f_q - 4 * variance) < 1e-8, "pure-state QFI must equal 4*Var(H)"

    assert abs(qfi_squeezed_light(0.0) - 2.0) < 1e-12, "unsqueezed QFI must equal 2"
    assert cramer_rao_bound(10.0, 400) < cramer_rao_bound(10.0, 100), "CR bound must shrink with more measurements"

    return "metrology._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())
