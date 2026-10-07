"""
Superconducting cavities (Unbuilt) -- Section 3. Real BCS-theory formulas:
gap interpolation formula, surface resistance, quality factor, and the two
microscopic length scales computed from material band-structure parameters.
"""
from __future__ import annotations

import numpy as np

HBAR = 1.054571817e-34
K_B = 1.380649e-23
MU_0 = 4e-7 * np.pi
E_CHARGE = 1.602176634e-19


def bcs_gap(temperature_k: float, delta0_j: float, tc_k: float) -> float:
    """
    Standard BCS gap interpolation formula (accurate to <2% across the full
    range; not the full self-consistent BCS integral equation, which has no
    closed form -- this is the standard engineering approximation used
    throughout superconducting-cavity literature):
        Delta(T) = Delta0 * tanh(1.74 * sqrt(Tc/T - 1))
    """
    if temperature_k <= 0:
        return delta0_j
    if temperature_k >= tc_k:
        return 0.0
    return delta0_j * np.tanh(1.74 * np.sqrt(tc_k / temperature_k - 1.0))


def bcs_gap_self_consistent(
    temperature_k: float,
    delta0_j: float,
    tc_k: float,
    max_iterations: int = 100,
    tol: float = 1e-12,
) -> float:
    """
    The real, self-consistent BCS gap equation (no closed form), solved
    numerically rather than approximated:
        1 = lambda * Integral_0^{hbar*omega_D} dxi / sqrt(xi^2+Delta^2) * tanh(sqrt(xi^2+Delta^2) / (2 k_B T))
    where the dimensionless coupling lambda = N(0)V is itself derived from
    the T=0 relation (also exact, no approximation):
        Delta0 = hbar*omega_D / sinh(1/lambda)  =>  1/lambda = asinh(hbar*omega_D/Delta0)
    so hbar*omega_D and Delta0 alone fix lambda, and no extra free parameter
    is introduced. A representative Debye cutoff hbar*omega_D = 40*k_B*Tc is
    used (typical Debye-to-Tc ratio for BCS superconductors, e.g. Nb:
    Theta_D/Tc ~ 275/9.2 ~ 30); lambda is then derived from the exact T=0
    relation so Delta(0) reproduces delta0_j exactly by construction.
    Solved here by bisection on Delta at fixed T (the gap equation's RHS is
    monotonically decreasing in Delta, so bisection is guaranteed to
    converge), with the T=0 and T>=Tc endpoints handled exactly.
    """
    if temperature_k <= 0:
        return delta0_j
    if temperature_k >= tc_k:
        return 0.0

    hbar_omega_d = 40.0 * K_B * tc_k
    inv_lambda = np.arcsinh(hbar_omega_d / delta0_j)

    def gap_equation_residual(delta: float) -> float:
        if delta <= 0:
            delta = 1e-30
        n_grid = 4000
        xi = np.linspace(0.0, hbar_omega_d, n_grid)
        e_xi = np.sqrt(xi ** 2 + delta ** 2)
        integrand = np.tanh(e_xi / (2.0 * K_B * temperature_k)) / e_xi
        integral = np.trapezoid(integrand, xi)
        return integral - inv_lambda

    lo, hi = 1e-30, delta0_j
    f_lo, f_hi = gap_equation_residual(lo), gap_equation_residual(hi)
    if f_lo * f_hi > 0:
        # Both residuals share a sign near the boundary between the T=0
        # relation's implied "true" Tc (from the fixed hbar*omega_D/lambda
        # choice above) and the caller's tc_k. Since the gap equation's RHS
        # strictly decreases with both delta and T, both-negative means the
        # self-consistent gap has already collapsed to 0 at this T; both-
        # positive (only possible right at T=0) means it is still delta0_j.
        return delta0_j if f_lo > 0 else 0.0
    for _ in range(max_iterations):
        mid = 0.5 * (lo + hi)
        f_mid = gap_equation_residual(mid)
        if abs(f_mid) < tol or (hi - lo) < tol * delta0_j:
            return mid
        if f_lo * f_mid <= 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return 0.5 * (lo + hi)


def surface_resistance(
    temperature_k: float, omega: float, lambda_l_m: float, delta0_j: float, tc_k: float
) -> float:
    """Standard two-fluid/BCS-approximate surface resistance (valid for hbar*omega << Delta, T << Tc)."""
    if temperature_k <= 0:
        return 0.0
    delta = bcs_gap(temperature_k, delta0_j, tc_k)
    return (MU_0 ** 2 * omega ** 2 * lambda_l_m ** 3 / 3.0) * (delta / temperature_k) * np.exp(
        -delta / (K_B * temperature_k)
    )


def quality_factor(geometry_factor_ohm: float, r_s_ohm: float) -> float:
    return geometry_factor_ohm / r_s_ohm


def penetration_depth(m_eff_kg: float, n_s_per_m3: float) -> float:
    """lambda_L = sqrt(m* / (mu0 * n_s * e^2))."""
    return np.sqrt(m_eff_kg / (MU_0 * n_s_per_m3 * E_CHARGE ** 2))


def coherence_length(v_fermi_m_per_s: float, delta0_j: float) -> float:
    """xi0 = hbar * v_F / (pi * Delta0)."""
    return HBAR * v_fermi_m_per_s / (np.pi * delta0_j)


def _self_test() -> str:
    tc = 9.2
    delta0 = 1.76 * K_B * tc
    assert abs(bcs_gap(0.0, delta0, tc) - delta0) < 1e-30, "T=0 gap must equal Delta0"
    assert bcs_gap(tc, delta0, tc) == 0.0, "gap must vanish at Tc"
    assert bcs_gap(tc * 2, delta0, tc) == 0.0, "gap must vanish above Tc"

    ts = np.linspace(0.5, tc - 1e-6, 50)
    gaps = [bcs_gap(t, delta0, tc) for t in ts]
    assert all(gaps[i] >= gaps[i + 1] - 1e-30 for i in range(len(gaps) - 1)), "gap must be monotonically decreasing"

    lam = penetration_depth(9.109e-31, 1e28)
    assert lam > 0 and np.isfinite(lam), "penetration depth must be a real positive number"
    xi = coherence_length(1.6e6, delta0)
    assert xi > 0 and np.isfinite(xi), "coherence length must be a real positive number"

    rs = surface_resistance(4.2, 2 * np.pi * 1.3e9, lam, delta0, tc)
    assert rs >= 0 and np.isfinite(rs), "surface resistance must be a real non-negative number"
    q = quality_factor(1.0, rs) if rs > 0 else float("inf")
    assert q > 0, "quality factor must be positive"

    # Real self-consistent BCS gap equation, cross-checked against the
    # engineering interpolation formula it is supposed to approximate.
    assert bcs_gap_self_consistent(0.0, delta0, tc) == delta0, "self-consistent gap at T=0 must equal Delta0 exactly by construction"
    assert bcs_gap_self_consistent(tc, delta0, tc) == 0.0, "self-consistent gap must vanish at Tc"
    assert bcs_gap_self_consistent(tc * 2, delta0, tc) == 0.0, "self-consistent gap must vanish above Tc"

    sc_gaps = [bcs_gap_self_consistent(t, delta0, tc) for t in ts]
    assert all(np.isfinite(g) and g >= 0 for g in sc_gaps), "self-consistent gap must be real, finite, and non-negative"
    assert all(sc_gaps[i] >= sc_gaps[i + 1] - 1e-30 for i in range(len(sc_gaps) - 1)), "self-consistent gap must be monotonically decreasing"
    rel_errors = [abs(sc - interp) / delta0 for sc, interp in zip(sc_gaps, gaps)]
    max_rel_error = max(rel_errors)
    assert max_rel_error < 0.05, f"self-consistent solution should track the standard interpolation formula to within a few percent, got {max_rel_error:.4f}"

    return "superconductivity._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())
