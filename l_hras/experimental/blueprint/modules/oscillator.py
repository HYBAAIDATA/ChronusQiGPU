# l_hras/modules/oscillator.py

import numpy as np
from dataclasses import dataclass

@dataclass
class NormalModes:
    frequencies: np.ndarray
    modes: np.ndarray
    attestation: str

def oscillator_lattice(couplings: np.ndarray) -> NormalModes:
    """Coupled-oscillator normal-mode diagonalization."""
    eigenvalues, eigenvectors = np.linalg.eigh(couplings)
    # Clip negative eigenvalues to 0 (unstable modes)
    eigenvalues = np.clip(eigenvalues, 0, None)
    return NormalModes(
        frequencies=np.sqrt(eigenvalues),
        modes=eigenvectors,
        attestation="oscillator_modes",
    )
