# thermal.py -- Cryogenics as thermodynamics (temperature, Bose noise, entropy).
# Reuses theory.cryogenics formulae; adds a stateful environment object.

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np

from ..theory.cryogenics import (
    bose_occupation,
    carnot_cascade,
    dilution_fridge_stage_powers,
    HBAR,
    K_B,
)
from ..weak_measurement import project_to_psd_hermitian


@dataclass
class ThermalNoise:
    amplitude: float
    correlation_time: float
    occupation: float


class CryogenicEnvironment:
    """Thermal bath model: T, Bose occupation, cooling cascade, von Neumann S."""

    def __init__(self, temperature_k: float = 0.015, omega_hz: float = 5e9):
        self.temperature = float(temperature_k)
        self.omega = 2.0 * np.pi * float(omega_hz)

    def thermal_noise(self) -> ThermalNoise:
        n = bose_occupation(self.omega, self.temperature)
        corr = HBAR / (K_B * self.temperature) if self.temperature > 0 else float("inf")
        return ThermalNoise(amplitude=float(np.sqrt(max(n, 0.0))), correlation_time=float(corr), occupation=float(n))

    def cooling_power(self, t_hot: float, input_power_w: float = 25_000.0) -> float:
        return carnot_cascade(input_power_w, self.temperature, t_hot)

    def stage_powers(self, input_power_w: float = 25_000.0) -> Dict[str, float]:
        return dilution_fridge_stage_powers(input_power_w)

    @staticmethod
    def von_neumann_entropy(rho: np.ndarray) -> float:
        rho = project_to_psd_hermitian(rho)
        w = np.linalg.eigvalsh(rho)
        w = w[w > 1e-15]
        return float(-np.sum(w * np.log(w)))

    def apply_thermal_dephasing(self, rho: np.ndarray, dt: float, rate_scale: float = 1.0) -> np.ndarray:
        """Diagonal dephasing channel with rate ∝ n̄(T) (Bose occupation)."""
        rho = project_to_psd_hermitian(rho)
        nbar = bose_occupation(self.omega, self.temperature)
        gamma = rate_scale * nbar
        # Off-diagonal decay e^{-γ dt}
        decay = np.exp(-gamma * dt)
        out = rho.copy()
        n = out.shape[0]
        for i in range(n):
            for j in range(n):
                if i != j:
                    out[i, j] *= decay
        return project_to_psd_hermitian(out)


def _self_test() -> str:
    env = CryogenicEnvironment(temperature_k=0.015, omega_hz=1e9)
    noise = env.thermal_noise()
    assert noise.occupation >= 0.0
    assert noise.amplitude >= 0.0
    stages = env.stage_powers()
    assert "15mK" in stages
    rho = np.eye(4, dtype=complex) / 4.0
    s = env.von_neumann_entropy(rho)
    assert abs(s - np.log(4)) < 1e-10
    rho2 = env.apply_thermal_dephasing(rho, dt=1e-3)
    assert abs(np.trace(rho2).real - 1.0) < 1e-10
    return "environment.thermal._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())
