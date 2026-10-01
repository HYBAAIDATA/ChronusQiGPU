# microwave.py -- AC driving / Rabi physics as time-dependent Hamiltonians.

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


def _embed_sigma_x(n: int, site: int = 0) -> np.ndarray:
    i = int(site) % n
    j = (i + 1) % n
    sx = np.zeros((n, n), dtype=complex)
    sx[i, j] = 1.0
    sx[j, i] = 1.0
    return sx


@dataclass
class MicrowaveField:
    frequency: float
    amplitude: float
    phase: float = 0.0

    def hamiltonian_at(self, t: float, n: int, site: int = 0) -> np.ndarray:
        """H(t) = Ω cos(ω t + φ) σ_x  on the (site, site+1) subspace."""
        sx = _embed_sigma_x(n, site)
        return self.amplitude * np.cos(self.frequency * t + self.phase) * sx


def rabi_evolve(
    state: np.ndarray,
    field: MicrowaveField,
    t_final: float,
    n_steps: int = 100,
    site: int = 0,
    drift: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Piecewise-constant integration of Schrödinger equation under H(t)+H_drift."""
    psi = np.asarray(state, dtype=complex).copy()
    psi = psi / (np.linalg.norm(psi) + 1e-30)
    n = psi.size
    dt = t_final / max(n_steps, 1)
    for k in range(n_steps):
        t = (k + 0.5) * dt
        h = field.hamiltonian_at(t, n, site=site)
        if drift is not None:
            h = h + 0.5 * (drift + drift.conj().T)
        h = 0.5 * (h + h.conj().T)
        w, v = np.linalg.eigh(h)
        u = (v * np.exp(-1j * dt * w)) @ v.conj().T
        psi = u @ psi
    return psi / (np.linalg.norm(psi) + 1e-30)


def _self_test() -> str:
    psi0 = np.array([1.0, 0.0], dtype=complex)
    # Resonant Rabi: H = Ω σ_x with Ω=1 → U=cos(Ωt)I - i sin(Ωt)σ_x;
    # full population transfer at Ωt = π/2.
    field = MicrowaveField(frequency=0.0, amplitude=1.0)
    psi = rabi_evolve(psi0, field, t_final=np.pi / 2, n_steps=80)
    assert abs(psi[1]) > 0.99, f"Rabi flip failed: {psi}"

    # Off-resonant should not fully invert over the same interval
    field2 = MicrowaveField(frequency=5.0, amplitude=1.0)
    psi2 = rabi_evolve(psi0, field2, t_final=np.pi / 2, n_steps=80)
    assert abs(psi2[1]) < 0.99
    return "fields.microwave._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())
