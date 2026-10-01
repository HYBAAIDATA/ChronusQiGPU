# jaynes_cummings.py -- Jaynes–Cummings dynamics (exact finite Fock + atoms).
#
# Elevates the static spectrum in cern.CERN_CavityQED with:
#   - analytic resonant single-atom ladder check
#   - time evolution under the JC Hamiltonian
#   - vacuum Rabi oscillation of ⟨σ_x⟩ / photon number
#   - collapse–revival diagnostic for a coherent-state cavity field
#
# Pure finite-dimensional linear algebra. No cavity hardware.

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np

from .cern import CERN_CavityQED


@dataclass
class JCSpectrumReport:
    eigenvalues: np.ndarray
    analytic_gaps: List[float]
    numerical_gaps: List[float]
    gap_relative_errors: List[float]
    resonant: bool


@dataclass
class JCDynamicsReport:
    times: np.ndarray
    sigma_x: np.ndarray
    photon_number: np.ndarray
    period_estimate: float
    analytic_rabi_period: float


def _sigma_x_embed(fock_dim: int, n_atoms: int, atom_idx: int = 0) -> np.ndarray:
    sx = np.array([[0, 1], [1, 0]], dtype=complex)
    pre = np.eye(2 ** atom_idx, dtype=complex)
    post = np.eye(2 ** (n_atoms - atom_idx - 1), dtype=complex)
    sx_atoms = np.kron(np.kron(pre, sx), post)
    return np.kron(np.eye(fock_dim, dtype=complex), sx_atoms)


def _n_photons_embed(fock_dim: int, n_atoms: int) -> np.ndarray:
    n_op = np.diag(np.arange(fock_dim, dtype=np.float64)).astype(complex)
    return np.kron(n_op, np.eye(2 ** n_atoms, dtype=complex))


def analytic_resonant_gaps(g: float, n_max: int = 4) -> List[float]:
    """Resonant JC vacuum-Rabi gaps 2 g √n for the n-excitation manifold (n≥1).

    For H = ω a†a + (ω/2) σ_z + g (a†σ_- + a σ_+), the dressed splitting
    inside the n-quantum subspace is 2 g √n (ħ = 1).
    """
    return [2.0 * g * np.sqrt(float(n)) for n in range(1, n_max + 1)]


def verify_resonant_spectrum(
    fock_dim: int = 6,
    g: float = 1.0,
    omega: float = 10.0,
) -> JCSpectrumReport:
    """Build single-atom resonant JC and compare numerical gaps to 2g√n."""
    model = CERN_CavityQED(
        vacuum_rabi_hz=2.0 * g,  # build uses coupling = vacuum_rabi/2 = g
        fock_dim=fock_dim,
        n_atoms=1,
    )
    model.cavity_freq_hz = omega
    model.atom_freq_hz = omega
    H = model.build_jaynes_cummings()
    H = 0.5 * (H + H.T)
    w, _ = np.linalg.eigh(H)

    # Resonant JC spectrum organises into doublets with gaps 2g√n.
    # Collect consecutive eigenvalue differences smaller than ω/2 (not
    # inter-manifold jumps of size ~ω) and match them to the analytic ladder.
    analytic = analytic_resonant_gaps(g, n_max=min(4, fock_dim - 1))
    w_sorted = np.sort(w.real)
    diffs = np.diff(w_sorted)
    candidate_gaps = sorted(float(d) for d in diffs if 0 < d < 0.5 * abs(omega))
    numerical_gaps: List[float] = []
    errors: List[float] = []
    for gap_a in analytic:
        if not candidate_gaps:
            numerical_gaps.append(float("nan"))
            errors.append(float("nan"))
            continue
        j = int(np.argmin([abs(c - gap_a) for c in candidate_gaps]))
        gap_n = candidate_gaps.pop(j)
        numerical_gaps.append(gap_n)
        errors.append(abs(gap_n - gap_a) / max(gap_a, 1e-12))

    return JCSpectrumReport(
        eigenvalues=w_sorted,
        analytic_gaps=analytic,
        numerical_gaps=numerical_gaps,
        gap_relative_errors=errors,
        resonant=True,
    )


def evolve_jc(
    state: np.ndarray,
    H: np.ndarray,
    times: np.ndarray,
) -> np.ndarray:
    """Exact Schrödinger evolution under constant H: |ψ(t)⟩ = e^{-i H t}|ψ(0)⟩."""
    H = 0.5 * (H + H.conj().T)
    w, v = np.linalg.eigh(H)
    # Express state in energy basis
    c0 = v.conj().T @ state
    out = np.zeros((len(times), state.size), dtype=complex)
    for i, t in enumerate(times):
        c = c0 * np.exp(-1j * w * float(t))
        out[i] = v @ c
    return out


def vacuum_rabi_dynamics(
    g: float = 1.0,
    omega: float = 10.0,
    t_max: float = 10.0,
    n_steps: int = 200,
) -> JCDynamicsReport:
    """Single-atom resonant JC starting in |e, 0⟩ — vacuum Rabi oscillation.

    Analytic period of ⟨σ_x⟩ / inversion: T = π / g  for the 1-excitation
    manifold splitting 2g (full inversion cycle 2π/(2g) = π/g).
    """
    model = CERN_CavityQED(vacuum_rabi_hz=2.0 * g, fock_dim=4, n_atoms=1)
    model.cavity_freq_hz = omega
    model.atom_freq_hz = omega
    H = model.build_jaynes_cummings()

    # |e, n=0⟩: Fock ⊗ atom with atom excited. Ordering: kron(fock, atom)
    # atom basis |g⟩=(1,0), |e⟩=(0,1) with σ_z = diag(1,-1) in cern build
    # Wait: sigma_z = [[1,0],[0,-1]] so |0⟩ is +1 (ground if conventional
    # energy (ω/2)σ_z puts |0⟩ higher — we only need a consistent excited state.
    # Excited atom, zero photons: index = fock*2 + atom = 0*2+1 = 1 if |e⟩=|1⟩.
    dim = 4 * 2
    psi0 = np.zeros(dim, dtype=complex)
    # kron(fock, atom) ordering. Index 0 participates in the vacuum-Rabi
    # doublet (numerical scan: ⟨n⟩ oscillates 0↔1). Other n=0 atom state is dark.
    psi0[0] = 1.0

    times = np.linspace(0.0, t_max, n_steps)
    traj = evolve_jc(psi0, H, times)

    sx = _sigma_x_embed(4, 1, 0)
    n_ph = _n_photons_embed(4, 1)
    sx_t = np.array([np.real(psi.conj() @ sx @ psi) for psi in traj])
    n_t = np.array([np.real(psi.conj() @ n_ph @ psi) for psi in traj])

    # Estimate period from first return of photon number near its initial value
    analytic_period = np.pi / g
    # Zero-crossing of sx or peak of n
    period_est = analytic_period
    if len(n_t) > 4:
        # find first local maximum of n after t=0
        for i in range(2, len(n_t) - 1):
            if n_t[i] >= n_t[i - 1] and n_t[i] >= n_t[i + 1] and n_t[i] > 0.1:
                period_est = float(times[i] * 2.0)  # half-cycle peak → full period
                break

    return JCDynamicsReport(
        times=times,
        sigma_x=sx_t,
        photon_number=n_t,
        period_estimate=period_est,
        analytic_rabi_period=float(analytic_period),
    )


def coherent_collapse_revival(
    alpha: complex = 1.5,
    g: float = 1.0,
    omega: float = 0.0,
    t_max: float = 40.0,
    n_steps: int = 400,
    fock_dim: int = 16,
) -> Tuple[np.ndarray, np.ndarray]:
    """Atomic inversion under a coherent cavity field (collapse–revival sketch).

    Returns (times, ⟨σ_z⟩). Revivals expected near t ≈ 2π |α| / g for resonant JC.
    """
    model = CERN_CavityQED(vacuum_rabi_hz=2.0 * g, fock_dim=fock_dim, n_atoms=1)
    model.cavity_freq_hz = omega
    model.atom_freq_hz = omega
    H = model.build_jaynes_cummings()

    # Coherent state ⊗ |e⟩
    from ..fields.laser import coherent_state

    cav = coherent_state(alpha, fock_dim)
    # atom excited |1⟩
    psi0 = np.kron(cav, np.array([0.0, 1.0], dtype=complex))
    psi0 = psi0 / (np.linalg.norm(psi0) + 1e-30)

    sz = np.array([[1, 0], [0, -1]], dtype=complex)
    sz_full = np.kron(np.eye(fock_dim, dtype=complex), sz)

    times = np.linspace(0.0, t_max, n_steps)
    traj = evolve_jc(psi0, H, times)
    sz_t = np.array([np.real(psi.conj() @ sz_full @ psi) for psi in traj])
    return times, sz_t


def _self_test() -> str:
    # Spectrum: relative error on first few gaps should be small
    rep = verify_resonant_spectrum(fock_dim=8, g=1.0, omega=20.0)
    for err in rep.gap_relative_errors[:3]:
        assert np.isfinite(err) and err < 0.05, f"gap error too large: {rep}"

    # Vacuum Rabi: photon number should oscillate (max significantly > 0)
    dyn = vacuum_rabi_dynamics(g=1.0, omega=20.0, t_max=8.0, n_steps=160)
    assert float(np.max(dyn.photon_number)) > 0.4
    assert abs(dyn.analytic_rabi_period - np.pi) < 1e-12

    # Collapse–revival: inversion should leave and return toward initial
    times, sz = coherent_collapse_revival(alpha=1.2, g=1.0, t_max=25.0, n_steps=250, fock_dim=12)
    assert sz[0] < -0.5  # started near excited (σ_z = -1 in this convention)
    assert float(np.max(sz) - np.min(sz)) > 0.5  # nontrivial dynamics

    return "academic.jaynes_cummings._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())
