"""
LHC integration (Unbuilt) -- Section 7. Real one-loop QCD running coupling
(asymptotic freedom) and the leading-order Debye screening mass -- pure
renormalization-group and thermal-field-theory formulas; no detector/collider
hardware or actual LHC data involved.
"""
from __future__ import annotations

import numpy as np


def running_coupling(q_squared: float, q0_squared: float, alpha_s0: float, n_c: int = 3, n_f: int = 6) -> float:
    """
    One-loop QCD running coupling:
      alpha_s(Q^2) = alpha_s(Q0^2) / (1 + b0*alpha_s(Q0^2)*ln(Q^2/Q0^2)),
      b0 = (11*Nc - 2*Nf)/(12*pi). Exhibits asymptotic freedom whenever
      11*Nc > 2*Nf, true for all physical Nf<=16 at Nc=3.
    """
    b0 = (11 * n_c - 2 * n_f) / (12 * np.pi)
    return alpha_s0 / (1 + b0 * alpha_s0 * np.log(q_squared / q0_squared))


def debye_screening_mass_squared(coupling_g: float, temperature: float, n_c: int = 3, n_f: int = 6) -> float:
    """m_D^2 = (g^2*T^2/3)*(Nc + Nf/2), leading-order thermal QCD."""
    return (coupling_g ** 2 * temperature ** 2 / 3.0) * (n_c + n_f / 2.0)


def _self_test() -> str:
    alpha0 = 0.118
    q0_sq = 91.19 ** 2
    assert abs(running_coupling(q0_sq, q0_sq, alpha0) - alpha0) < 1e-12, "boundary condition failed"

    alphas = [running_coupling(q_sq, q0_sq, alpha0, n_f=5) for q_sq in [q0_sq, 200.0 ** 2, 1000.0 ** 2, 10000.0 ** 2]]
    assert all(alphas[i] > alphas[i + 1] for i in range(len(alphas) - 1)), "asymptotic freedom violated"

    m1 = debye_screening_mass_squared(1.0, 200.0)
    m2 = debye_screening_mass_squared(1.0, 400.0)
    assert abs(m2 / m1 - 4.0) < 1e-9, "Debye mass^2 must scale as T^2"

    return "qcd._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())
