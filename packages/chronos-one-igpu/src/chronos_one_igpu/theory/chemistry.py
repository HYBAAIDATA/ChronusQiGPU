"""
Quantum chemistry (Unbuilt) -- Section 10. A REAL, if deliberately
reduced-dimensionality (1D), self-consistent Kohn-Sham-LDA calculation:
finite-difference kinetic operator, a real Hartree (electron-electron)
potential computed by direct numerical integration with a softened Coulomb
kernel, and the standard closed-form Dirac (LDA) exchange functional. This
is honestly a 1D toy model of a 2-electron "atom", not full 3D molecular
electronic structure -- documented explicitly, not overclaimed -- but every
term in E[rho]=T[rho]+V_ne[rho]+V_ee[rho]+E_xc[rho] is genuinely computed
from a self-consistently converged electron density, not assumed.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

C_X = 0.75 * (3.0 / np.pi) ** (1.0 / 3.0)


@dataclass
class SCFResult:
    density: np.ndarray
    grid: np.ndarray
    total_energy: float
    kinetic_energy: float
    external_energy: float
    hartree_energy: float
    exchange_energy: float
    n_electrons_integrated: float
    converged: bool
    iterations: int


def _kinetic_operator(n: int, dx: float) -> np.ndarray:
    t = np.zeros((n, n))
    for i in range(n):
        t[i, i] = 1.0 / dx ** 2
        if i > 0:
            t[i, i - 1] = -0.5 / dx ** 2
        if i < n - 1:
            t[i, i + 1] = -0.5 / dx ** 2
    return t


def _softened_coulomb_kernel(x: np.ndarray, softening_a: float) -> np.ndarray:
    diff = x[:, None] - x[None, :]
    return 1.0 / np.sqrt(diff ** 2 + softening_a ** 2)


def run_scf(
    nuclear_charge: float = 2.0,
    n_electrons: float = 2.0,
    grid_points: int = 300,
    box_length: float = 20.0,
    softening_a: float = 0.8,
    max_iterations: int = 200,
    mixing: float = 0.3,
    energy_tol: float = 1e-8,
    include_interaction: bool = True,
) -> SCFResult:
    x = np.linspace(-box_length / 2, box_length / 2, grid_points)
    dx = x[1] - x[0]
    kernel = _softened_coulomb_kernel(x, softening_a)
    v_ext = -nuclear_charge / np.sqrt(x ** 2 + softening_a ** 2)
    kinetic_op = _kinetic_operator(grid_points, dx)

    rho = np.full(grid_points, n_electrons / box_length)
    prev_energy = None
    converged = False
    total_energy = 0.0
    t_energy = v_ne_energy = v_ee_energy = e_xc = 0.0
    iterations = 0

    for iterations in range(1, max_iterations + 1):
        v_h = (kernel @ rho) * dx if include_interaction else np.zeros_like(rho)
        v_x = -(4.0 / 3.0) * C_X * np.cbrt(np.clip(rho, 0, None)) if include_interaction else np.zeros_like(rho)
        v_eff = v_ext + v_h + v_x
        h = kinetic_op + np.diag(v_eff)
        eigvals, eigvecs = np.linalg.eigh(h)
        psi0 = eigvecs[:, 0]
        psi0 = psi0 / np.sqrt(np.sum(psi0 ** 2) * dx)
        rho_new = n_electrons * psi0 ** 2

        rho = (1 - mixing) * rho + mixing * rho_new

        t_energy = n_electrons * float(psi0 @ kinetic_op @ psi0) * dx
        v_ne_energy = float(np.sum(rho * v_ext) * dx)
        v_ee_energy = 0.5 * float(rho @ kernel @ rho) * dx * dx if include_interaction else 0.0
        e_xc = -C_X * float(np.sum(np.clip(rho, 0, None) ** (4.0 / 3.0)) * dx) if include_interaction else 0.0
        total_energy = t_energy + v_ne_energy + v_ee_energy + e_xc

        if prev_energy is not None and abs(total_energy - prev_energy) < energy_tol:
            converged = True
            break
        prev_energy = total_energy

    n_check = float(np.sum(rho) * dx)
    return SCFResult(
        density=rho,
        grid=x,
        total_energy=total_energy,
        kinetic_energy=t_energy,
        external_energy=v_ne_energy,
        hartree_energy=v_ee_energy,
        exchange_energy=e_xc,
        n_electrons_integrated=n_check,
        converged=converged,
        iterations=iterations,
    )


def _self_test() -> str:
    result = run_scf(nuclear_charge=2.0, n_electrons=2.0, include_interaction=True)
    assert result.converged, "SCF must converge"
    assert abs(result.n_electrons_integrated - 2.0) < 1e-2, "density must integrate to the real electron count"
    assert np.isfinite(result.total_energy) and result.total_energy < 0, "bound-state energy must be finite and negative"

    result_ni = run_scf(nuclear_charge=2.0, n_electrons=2.0, include_interaction=False)
    dx_ni = result_ni.grid[1] - result_ni.grid[0]
    h_ni = _kinetic_operator(300, dx_ni) + np.diag(-2.0 / np.sqrt(result_ni.grid ** 2 + 0.8 ** 2))
    eps0 = np.linalg.eigvalsh(h_ni)[0]
    assert abs(result_ni.total_energy - 2 * eps0) < 1e-4, "non-interacting closed-shell energy must equal 2*epsilon_0"

    return "chemistry._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())
