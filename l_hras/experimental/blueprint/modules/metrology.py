# l_hras/modules/metrology.py

import numpy as np
from dataclasses import dataclass

@dataclass
class MetrologyResult:
    fisher_information: float
    cramer_rao: float
    heisenberg: float
    attestation: str

def quantum_metrology(state: np.ndarray, generator: np.ndarray, N: int = 100) -> MetrologyResult:
    """Quantum Fisher information / Cramér-Rao bound."""
    # Variance
    expectation = float(np.real(state.conj() @ (generator @ state)))
    expectation_sq = float(np.real(state.conj() @ (generator @ (generator @ state))))
    variance = expectation_sq - expectation ** 2
    F_Q = 4 * variance
    # Cramér-Rao
    delta_theta = 1 / np.sqrt(F_Q) if F_Q > 0 else float('inf')
    # Heisenberg limit
    heisenberg = 1 / N
    return MetrologyResult(
        fisher_information=float(F_Q),
        cramer_rao=float(delta_theta),
        heisenberg=float(heisenberg),
        attestation="metrology",
    )
