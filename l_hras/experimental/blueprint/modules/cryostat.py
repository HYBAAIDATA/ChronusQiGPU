# l_hras/modules/cryostat.py

import numpy as np
from dataclasses import dataclass

@dataclass
class CryostatResult:
    T_bath: float
    T_target: float
    occupation: float
    efficiency: float
    cooling: float
    attestation: str

def cryostat_temperature(T_bath: float, T_target: float, omega: float = 1e9) -> CryostatResult:
    """Dilution-fridge thermodynamics."""
    hbar = 1.054571817e-34
    k_B = 1.380649e-23
    # Bose occupation
    n = 1 / (np.exp(hbar * omega / (k_B * T_bath)) - 1)
    # Carnot efficiency
    eta = 1 - T_target / T_bath
    # Cooling power (simplified)
    P = k_B * T_bath * omega  # approximation
    return CryostatResult(
        T_bath=T_bath,
        T_target=T_target,
        occupation=float(n),
        efficiency=float(eta),
        cooling=float(P),
        attestation="cryostat",
    )
