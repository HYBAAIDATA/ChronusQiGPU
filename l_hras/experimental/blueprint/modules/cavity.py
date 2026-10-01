# l_hras/modules/cavity.py

import numpy as np
from dataclasses import dataclass

@dataclass
class CavityResult:
    gap: float
    resistance: float
    Q_factor: float
    attestation: str

def superconducting_cavity(T: float, Tc: float, omega: float = 1e9) -> CavityResult:
    """BCS superconductivity (gap, surface resistance, Q-factor)."""
    k_B = 1.380649e-23
    # BCS gap (interpolation approximation)
    if T >= Tc:
        gap = 0.0
    else:
        gap = 1.764 * k_B * Tc * np.sqrt(1 - T / Tc)
    # Surface resistance (simplified)
    Rs = 1e-8 * (T / Tc) ** 2 if T < Tc else 1e-3
    # Q-factor
    mu_0 = 1.25663706212e-6
    lambda_L = 1e-7
    Q = omega * mu_0 * lambda_L / Rs if Rs > 0 else 0
    return CavityResult(
        gap=float(gap),
        resistance=float(Rs),
        Q_factor=float(Q),
        attestation="cavity",
    )
