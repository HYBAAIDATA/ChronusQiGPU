# l_hras/modules/chemistry.py

import numpy as np
from dataclasses import dataclass
eigh = np.linalg.eigh

@dataclass
class SCFResult:
    density: np.ndarray
    eigenvalues: np.ndarray
    energy: float
    converged: bool
    attestation: str

def kohn_sham_1d(n_electrons: int, n_grid: int = 100, max_iter: int = 100) -> SCFResult:
    """1D Kohn-Sham/LDA SCF loop."""
    # Grid
    x = np.linspace(-10, 10, n_grid)
    dx = x[1] - x[0]
    # Initial density
    rho = np.exp(-x ** 2) / np.sqrt(np.pi)
    rho = rho * n_electrons / (np.sum(rho) * dx)
    # SCF loop
    converged = False
    for iteration in range(max_iter):
        # Effective potential
        V_ext = -1 / (np.abs(x) + 1)
        V_hartree = np.convolve(rho, 1 / (np.abs(x) + 1), mode='same') * dx
        V_xc = -0.5 * (3 * rho / np.pi) ** (1/3)
        V_eff = V_ext + V_hartree + V_xc
        # Hamiltonian
        H = np.diag(V_eff) + np.diag(np.ones(n_grid - 1), 1) / dx**2 + np.diag(np.ones(n_grid - 1), -1) / dx**2
        # Eigenvalues
        eigenvalues, eigenvectors = eigh(H)
        # New density
        rho_new = np.sum(np.abs(eigenvectors[:, :n_electrons]) ** 2, axis=1)
        # Convergence
        if np.linalg.norm(rho_new - rho) < 1e-8:
            converged = True
            rho = rho_new
            break
        rho = 0.5 * rho + 0.5 * rho_new
    energy = float(np.sum(eigenvalues[:n_electrons]))
    return SCFResult(
        density=rho,
        eigenvalues=eigenvalues,
        energy=energy,
        converged=converged,
        attestation="chemistry",
    )
