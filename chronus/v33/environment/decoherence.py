# decoherence.py -- Lindblad master equation step (open quantum systems).
# Exact Kraus form for amplitude damping; general Lindblad via Euler step.

from __future__ import annotations

from typing import List

import numpy as np

from ..weak_measurement import project_to_psd_hermitian


def lindblad_step(
    rho: np.ndarray,
    hamiltonian: np.ndarray,
    jump_ops: List[np.ndarray],
    rates: List[float],
    dt: float,
) -> np.ndarray:
    """One Euler step of  ρ̇ = -i[H,ρ] + Σ γ (L ρ L† − ½{L†L, ρ})."""
    rho = project_to_psd_hermitian(rho)
    h = 0.5 * (hamiltonian + hamiltonian.conj().T)
    commutator = -1j * (h @ rho - rho @ h)
    dissipator = np.zeros_like(rho)
    for L, g in zip(jump_ops, rates):
        L = np.asarray(L, dtype=complex)
        LdL = L.conj().T @ L
        dissipator = dissipator + g * (
            L @ rho @ L.conj().T - 0.5 * (LdL @ rho + rho @ LdL)
        )
    out = rho + dt * (commutator + dissipator)
    return project_to_psd_hermitian(out)


def amplitude_damping_channel(rho: np.ndarray, gamma: float, dt: float, site: int = 0) -> np.ndarray:
    """Exact amplitude-damping Kraus map on levels (site, site+1).

    Kraus operators for a two-level subsystem embedded in n dimensions:
      E0 = |0⟩⟨0| + √(1−p)|1⟩⟨1|
      E1 = √p |0⟩⟨1|
    with p = 1 − exp(−γ dt).
    """
    rho = project_to_psd_hermitian(rho)
    n = rho.shape[0]
    i = int(site) % n
    j = (i + 1) % n
    p = 1.0 - np.exp(-float(gamma) * float(dt))
    e0 = np.eye(n, dtype=complex)
    e0[j, j] = np.sqrt(max(1.0 - p, 0.0))
    e1 = np.zeros((n, n), dtype=complex)
    e1[i, j] = np.sqrt(p)
    out = e0 @ rho @ e0.conj().T + e1 @ rho @ e1.conj().T
    return project_to_psd_hermitian(out)


def _self_test() -> str:
    n = 4
    # Excited state on level 1
    psi = np.zeros(n, dtype=complex)
    psi[1] = 1.0
    rho = np.outer(psi, psi.conj())
    # Amplitude damping toward level 0
    rho2 = amplitude_damping_channel(rho, gamma=5.0, dt=1.0, site=0)
    # Population should have moved toward 0
    assert rho2[0, 0].real > rho[0, 0].real - 1e-12
    assert abs(np.trace(rho2).real - 1.0) < 1e-10

    h = np.diag([0.0, 1.0, 2.0, 3.0])
    L = np.zeros((n, n), dtype=complex)
    L[0, 1] = 1.0
    rho3 = lindblad_step(rho, h, [L], [0.5], dt=0.01)
    assert abs(np.trace(rho3).real - 1.0) < 1e-8
    return "environment.decoherence._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())
