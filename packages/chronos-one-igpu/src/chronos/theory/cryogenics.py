"""
Cryogenic system (Unbuilt) -- Section 2. Real thermodynamics: Bose
occupation, a dilution-refrigerator entropy-conservation cascade, and
cooling power from a real Cp(T) integral (trapezoidal quadrature) -- no
physical apparatus simulated, purely the mathematics of heat and entropy flow.
"""
from __future__ import annotations

from typing import Callable, Dict

import numpy as np

HBAR = 1.054571817e-34
K_B = 1.380649e-23


def bose_occupation(omega: float, temperature_k: float) -> float:
    """n(T) = 1 / (exp(hbar*omega / kB*T) - 1)."""
    if temperature_k <= 0:
        return 0.0
    x = HBAR * omega / (K_B * temperature_k)
    if x > 700:
        return 0.0
    return 1.0 / (np.exp(x) - 1.0)


def carnot_cascade(power_warm_w: float, t_cold_k: float, t_warm_k: float) -> float:
    """Reversible entropy-pump cascade: P_cold = P_warm * T_cold / T_warm."""
    return power_warm_w * (t_cold_k / t_warm_k)


def dilution_fridge_stage_powers(power_warm_w: float = 25_000.0) -> Dict[str, float]:
    """Real cascade numbers from 300K to each stage (see module self-test note
    on why these differ from the source document's own internally
    inconsistent narrative numbers)."""
    stages = {"4K": 4.0, "100mK": 0.1, "15mK": 0.015}
    t_warm = 300.0
    return {name: carnot_cascade(power_warm_w, t_cold, t_warm) for name, t_cold in stages.items()}


def cooling_power_thermodynamic(
    helium_flow_mol_per_s: float,
    cp_of_t: Callable[[float], float],
    t_cold_k: float,
    t_warm_k: float,
    n_points: int = 2000,
) -> float:
    """Real numerical integral: Qdot = ndot_He * Int[Tcold,Twarm] Cp(T) dT."""
    ts = np.linspace(t_cold_k, t_warm_k, n_points)
    cps = np.array([cp_of_t(t) for t in ts])
    return helium_flow_mol_per_s * float(np.trapezoid(cps, ts))


def _self_test() -> str:
    omega = 1e9
    t_hot = 1e6
    n_computed = bose_occupation(omega, t_hot)
    n_classical = K_B * t_hot / (HBAR * omega)
    assert abs(n_computed - n_classical) / n_classical < 1e-4, "high-T Bose limit failed"
    assert bose_occupation(omega, 0.0) == 0.0, "T=0 occupation must vanish"

    stages = dilution_fridge_stage_powers(25_000.0)
    assert abs(stages["4K"] - 25000 * 4.0 / 300.0) < 1e-6, "4K stage power mismatch"
    assert abs(stages["100mK"] - 25000 * 0.1 / 300.0) < 1e-6, "100mK stage power mismatch"
    assert abs(stages["15mK"] - 1.25) < 1e-9, "15mK stage power mismatch"

    cp_const = 20.0
    integral_result = cooling_power_thermodynamic(1.0, lambda t: cp_const, 15e-3, 300.0)
    assert abs(integral_result - cp_const * (300.0 - 15e-3)) / (cp_const * 300.0) < 1e-6, "constant-Cp quadrature failed"

    return "cryogenics._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())
