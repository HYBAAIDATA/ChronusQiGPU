# l_hras/modules/qcd.py

import numpy as np
from dataclasses import dataclass

@dataclass
class QCDResult:
    alpha_s: float
    debye_mass: float
    attestation: str

def qcd_running_coupling(Q: float, Lambda_QCD: float = 0.2, n_f: int = 3) -> float:
    """One-loop QCD running coupling."""
    beta_0 = (11 - 2 * n_f / 3) / (4 * np.pi)
    alpha_s = 1 / (beta_0 * np.log(Q / Lambda_QCD))
    return float(alpha_s)

def debye_screening(T: float, g: float = 1.0, n_f: int = 3) -> float:
    """Debye screening mass."""
    return float(g * T * np.sqrt(1 + n_f / 6))

def lhc_qcd(energy: float, temperature: float) -> QCDResult:
    """LHC/QCD integration."""
    return QCDResult(
        alpha_s=qcd_running_coupling(energy),
        debye_mass=debye_screening(temperature),
        attestation="qcd",
    )
