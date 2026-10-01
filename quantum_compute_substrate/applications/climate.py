"""
Climate-simulation kernel — quantum-mathematical linear advection.

Implements a 1D linear advection step ∂t u + c ∂x u = 0 using a
unitary-inspired spectral method (FFT-based). This is the kind of
kernel that dominates exascale climate codes (e.g. ICON, MPAS).

Claim lane: MATHEMATICAL_QUANTUM (SUBSTRATE-AGNOSTIC). Reference kernel only.
"""

import numpy as np
from typing import Dict


class AdvectionKernel:
    """Spectral advection kernel."""

    def __init__(self, nx: int = 128, L: float = 2 * np.pi, c: float = 1.0):
        self.nx = nx
        self.L = L
        self.c = c
        self.dx = L / nx
        self.x = np.linspace(0, L, nx, endpoint=False)
        # Fourier wavenumbers
        self.k = 2 * np.pi * np.fft.fftfreq(nx, d=self.dx)

    def step(self, u: np.ndarray, dt: float) -> np.ndarray:
        """One time step of spectral advection."""
        # u_hat = FFT(u); u_hat * exp(-i c k dt); IFFT
        u_hat = np.fft.fft(u)
        u_hat *= np.exp(-1j * self.c * self.k * dt)
        return np.real(np.fft.ifft(u_hat))

    def simulate(self, u0: np.ndarray, T: float, dt: float) -> Dict:
        u = u0.copy()
        n_steps = int(np.ceil(T / dt))
        for _ in range(n_steps):
            u = self.step(u, dt)
        # Analytical solution: u(x, T) = u₀(x - cT)
        exact = np.interp(
            (self.x - self.c * T) % self.L, self.x, u0
        )
        l2_error = float(np.linalg.norm(u - exact) / np.linalg.norm(exact))
        return {
            "final_state": u,
            "exact_solution": exact,
            "l2_relative_error": l2_error,
            "n_steps": n_steps,
        }

    def demo(self) -> Dict:
        """Gaussian pulse advected once around the periodic domain."""
        u0 = np.exp(-((self.x - np.pi) ** 2) / 0.5)
        result = self.simulate(u0, T=self.L / self.c, dt=0.01)
        return {
            "nx": self.nx,
            "n_steps": result["n_steps"],
            "l2_relative_error": result["l2_relative_error"],
        }
