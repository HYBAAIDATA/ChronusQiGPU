"""
Photonic interconnects (Unbuilt) -- Section 4. Real waveguide
electrodynamics: propagation constant from the dispersion relation, and mode
coupling from a real numerical overlap integral of two evanescently
overlapping Gaussian-approximated waveguide modes, plus the phenomenological
exponential fit kappa(d) = kappa0 * exp(-gamma*d) used to summarize it.
"""
from __future__ import annotations

import numpy as np

EPS_0 = 8.8541878128e-12


def propagation_constant(omega: float, mu: float, epsilon: float, k_c: float) -> complex:
    """
    beta = sqrt(omega^2*mu*epsilon - k_c^2). Returns a real beta for a
    propagating mode, or a purely imaginary beta (evanescent/cutoff mode)
    when omega^2*mu*epsilon < k_c^2 -- both are genuine outcomes of the same
    formula, not special-cased.
    """
    value = omega ** 2 * mu * epsilon - k_c ** 2
    return complex(np.sqrt(complex(value)))


def gaussian_mode_overlap_coupling(
    n_core: float,
    n_bg: float,
    wavelength_m: float,
    mode_width_m: float,
    separation_m: float,
    n_grid: int = 4000,
    extent_factor: float = 12.0,
) -> float:
    """
    Real numerical evaluation of kappa = (omega*eps0/2P) * Int (n^2-n_bg^2) E1.E2 dA
    using 1D Gaussian-beam approximations for two identical, parallel,
    transversely offset waveguide modes, integrated numerically (trapezoid
    quadrature on a fine grid) rather than assumed.
    """
    omega = 2 * np.pi * 2.998e8 / wavelength_m
    x = np.linspace(-extent_factor * mode_width_m, extent_factor * mode_width_m + separation_m, n_grid)
    e1 = np.exp(-(x ** 2) / (2 * mode_width_m ** 2))
    e2 = np.exp(-((x - separation_m) ** 2) / (2 * mode_width_m ** 2))
    p_norm = np.trapezoid(e1 ** 2, x)
    index_perturbation = n_core ** 2 - n_bg ** 2
    integral = np.trapezoid(index_perturbation * e1 * e2, x)
    return float((omega * EPS_0) / (2 * p_norm) * integral)


def coupling_exponential_fit(kappa0: float, gamma: float, separation_m: float) -> float:
    return kappa0 * np.exp(-gamma * separation_m)


def _self_test() -> str:
    beta_prop = propagation_constant(omega=2 * np.pi * 2e14, mu=4e-7 * np.pi, epsilon=2.1 * EPS_0, k_c=1e5)
    assert abs(beta_prop.imag) < 1e-6 * abs(beta_prop.real), "propagating mode should have ~zero imaginary part"

    beta_evan = propagation_constant(omega=1.0, mu=4e-7 * np.pi, epsilon=EPS_0, k_c=1e10)
    assert abs(beta_evan.real) < 1e-6 * abs(beta_evan.imag), "evanescent mode should have ~zero real part"

    kappas_abs = [
        abs(gaussian_mode_overlap_coupling(1.5, 1.44, 1.55e-6, 3e-6, d))
        for d in [2e-6, 5e-6, 10e-6, 20e-6]
    ]
    assert all(kappas_abs[i] >= kappas_abs[i + 1] for i in range(len(kappas_abs) - 1)), "coupling must decay with distance"

    assert abs(coupling_exponential_fit(5.0, 0.3, 0.0) - 5.0) < 1e-12, "exponential fit must equal kappa0 at d=0"

    return "photonics._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())
