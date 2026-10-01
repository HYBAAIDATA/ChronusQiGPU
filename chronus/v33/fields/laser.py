# laser.py -- Lasers as coherent states + displacement operators.
# |α⟩ = e^{-|α|²/2} Σ α^n/√(n!) |n⟩ on a truncated Fock space.

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def coherent_state(alpha: complex, n_max: int) -> np.ndarray:
    """Truncated coherent state on Fock levels 0..n_max-1, renormalised."""
    alpha = complex(alpha)
    n = np.arange(n_max, dtype=np.float64)
    # log ψ_n = -|α|²/2 + n log α - ½ log(n!)
    log_psi = -0.5 * abs(alpha) ** 2 + n * np.log(alpha + 0j) - 0.5 * np.array(
        [np.sum(np.log(np.arange(1, k + 1))) if k > 0 else 0.0 for k in range(n_max)]
    )
    psi = np.exp(log_psi)
    # Handle alpha=0 cleanly
    if abs(alpha) < 1e-15:
        psi = np.zeros(n_max, dtype=complex)
        psi[0] = 1.0
        return psi
    psi = psi / (np.linalg.norm(psi) + 1e-30)
    return psi.astype(complex)


def annihilation(n_max: int) -> np.ndarray:
    a = np.zeros((n_max, n_max), dtype=complex)
    for k in range(1, n_max):
        a[k - 1, k] = np.sqrt(k)
    return a


def displacement_operator(alpha: complex, n_max: int) -> np.ndarray:
    """D(α) = exp(α a† − α* a) via dense eigendecomposition of the generator."""
    a = annihilation(n_max)
    gen = alpha * a.conj().T - np.conj(alpha) * a
    # gen is anti-Hermitian; i*gen is Hermitian
    # Actually D = exp(G) with G = αa†−α*a anti-Hermitian: G† = -G
    # Use scaling-and-squaring style via eig of iG (Hermitian)
    g = 0.5 * (gen - gen.conj().T)  # enforce anti-Hermitian
    ih = 1j * g  # Hermitian
    w, v = np.linalg.eigh(ih)
    return (v * np.exp(-1j * w)) @ v.conj().T


@dataclass
class CoherentLaser:
    alpha: complex
    n_max: int = 32

    def state(self) -> np.ndarray:
        return coherent_state(self.alpha, self.n_max)

    def pulse_unitary(self, duration: float) -> np.ndarray:
        """Displacement with integrated amplitude α * duration."""
        return displacement_operator(self.alpha * duration, self.n_max)

    def apply_to(self, psi: np.ndarray, duration: float = 1.0) -> np.ndarray:
        u = self.pulse_unitary(duration)
        out = u @ psi
        return out / (np.linalg.norm(out) + 1e-30)


def _self_test() -> str:
    # Vacuum
    vac = coherent_state(0.0, 16)
    assert abs(vac[0] - 1.0) < 1e-12
    assert abs(np.linalg.norm(vac) - 1.0) < 1e-12

    # Mean photon number ≈ |α|² for moderate α
    alpha = 1.5 + 0.5j
    psi = coherent_state(alpha, 40)
    n_op = np.diag(np.arange(40, dtype=np.float64))
    nbar = float(np.real(psi.conj() @ n_op @ psi))
    assert abs(nbar - abs(alpha) ** 2) / abs(alpha) ** 2 < 0.05

    # Displacement of vacuum ≈ coherent state
    d = displacement_operator(alpha, 40)
    vac40 = np.zeros(40, dtype=complex)
    vac40[0] = 1.0
    displaced = d @ vac40
    # Overlap with coherent_state
    coh = coherent_state(alpha, 40)
    fid = abs(np.vdot(coh, displaced)) ** 2
    assert fid > 0.98, f"displacement fidelity {fid}"

    laser = CoherentLaser(alpha=0.8, n_max=24)
    out = laser.apply_to(vac40[:24] if False else np.eye(24, dtype=complex)[:, 0])
    assert abs(np.linalg.norm(out) - 1.0) < 1e-10
    return "fields.laser._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())
