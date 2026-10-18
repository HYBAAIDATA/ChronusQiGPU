"""
chronus/theory/emergent_time.py -- Page-Wootters Mechanism & Coppo Magnetic Clock.

Pure, hardware-agnostic mathematical formulation of relational time emerging from
quantum entanglement in a timeless universe (Wheeler-DeWitt constraint H_tot |Psi> = 0).

Based on:
- Page, D. N. & Wootters, W. K. "Evolution without evolution: Dynamics described by
  stationary observables." Physical Review D 27, 2885 (1983).
- Coppo, A., Cuccoli, A., & Verrucchi, P. "Entanglement and the emergence of classical
  time from quantum mechanics." Physical Review A 109, 052212 (2024).
"""

from __future__ import annotations

import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

from dataclasses import dataclass
from typing import Dict, List, Tuple
import numpy as np


def von_neumann_entropy(psi: np.ndarray, dim_C: int, dim_S: int) -> float:
    """Compute the bipartite Von Neumann entanglement entropy S(rho_S) in nats."""
    psi_matrix = psi.reshape((dim_C, dim_S))
    # Reduced density matrix rho_S = Tr_C(|Psi><Psi|) = psi_matrix.conj().T @ psi_matrix
    rho_S = psi_matrix.conj().T @ psi_matrix
    eigvals = np.linalg.eigvalsh(rho_S)
    probs = eigvals[eigvals > 1e-14]
    probs /= np.sum(probs)
    return float(-np.sum(probs * np.log(probs)))


@dataclass
class PageWoottersSystem:
    """
    Substrate-agnostic Page-Wootters timeless universe partitioned into Clock (C) and System (S).
    Global state satisfies Wheeler-DeWitt stationary constraint:
        (H_C (x) I_S + I_C (x) H_S) |Psi> = 0
    """
    dim_C: int
    dim_S: int
    energies_S: np.ndarray
    energies_C: np.ndarray
    H_S: np.ndarray
    H_C: np.ndarray
    H_tot: np.ndarray

    @classmethod
    def create(cls, dim_S: int = 8, omega_S: float = 1.0) -> PageWoottersSystem:
        dim_C = dim_S
        # Harmonic oscillator spectrum for System: E_S = omega * (n + 0.5)
        energies_S = np.array([omega_S * (n + 0.5) for n in range(dim_S)], dtype=float)
        H_S = np.diag(energies_S)

        # Clock spectrum mirrors system to ensure Wheeler-DeWitt constraint sum E_C + E_S = 0
        energies_C = -energies_S
        H_C = np.diag(energies_C)

        H_tot = np.kron(H_C, np.eye(dim_S)) + np.kron(np.eye(dim_C), H_S)
        return cls(
            dim_C=dim_C,
            dim_S=dim_S,
            energies_S=energies_S,
            energies_C=energies_C,
            H_S=H_S,
            H_C=H_C,
            H_tot=H_tot,
        )

    def create_entangled_stationary_state(self) -> np.ndarray:
        """
        Construct maximally entangled stationary state |Psi>:
            |Psi> = (1/sqrt(dim)) sum_n |E_n>_C (x) |e_n>_S
        """
        psi = np.zeros(self.dim_C * self.dim_S, dtype=complex)
        norm_factor = 1.0 / np.sqrt(self.dim_S)
        for n in range(min(self.dim_C, self.dim_S)):
            idx = n * self.dim_S + n
            psi[idx] = norm_factor
        return psi

    def project_at_time(self, psi_global: np.ndarray, t: float) -> Tuple[np.ndarray, np.ndarray, float]:
        """
        Condition global state |Psi> on clock reading <t|_C:
            |psi_S(t)> = (<t|_C (x) I_S) |Psi>
        where |t>_C = (1/sqrt(dim_C)) sum_k exp(-i E_C[k] t) |E_k>_C.
        Returns:
            (projected_state, theoretical_schrodinger_state, fidelity)
        """
        clock_t = np.array(
            [np.exp(-1j * self.energies_C[k] * t) / np.sqrt(self.dim_C) for k in range(self.dim_C)],
            dtype=complex,
        )
        psi_matrix = psi_global.reshape((self.dim_C, self.dim_S))
        projected = np.conj(clock_t) @ psi_matrix
        projected /= np.linalg.norm(projected)

        # Baseline Schrödinger state: exp(-i H_S t) |psi_S(0)>
        clock_0 = np.array([1.0 / np.sqrt(self.dim_C)] * self.dim_C, dtype=complex)
        psi_S_0 = np.conj(clock_0) @ psi_matrix
        psi_S_0 /= np.linalg.norm(psi_S_0)

        schrodinger = np.exp(-1j * self.energies_S * t) * psi_S_0
        schrodinger /= np.linalg.norm(schrodinger)

        fidelity = float(np.abs(np.vdot(schrodinger, projected)) ** 2)
        return projected, schrodinger, fidelity


def test_zero_entanglement_absence_of_time(dim_S: int = 8) -> Dict[str, float]:
    """
    Evaluate unentangled product state satisfying H_tot |Psi> = 0.
    Proves that zero entanglement results in zero observable time dynamics.
    """
    sys = PageWoottersSystem.create(dim_S=dim_S)
    # Single eigenstate pair with E_C[2] + E_S[2] = 0
    psi_C = np.zeros(sys.dim_C, dtype=complex)
    psi_C[2] = 1.0
    psi_S = np.zeros(sys.dim_S, dtype=complex)
    psi_S[2] = 1.0
    psi_product = np.kron(psi_C, psi_S)

    entropy = von_neumann_entropy(psi_product, sys.dim_C, sys.dim_S)

    # Observable X = a + a^\dagger (position-like off-diagonal operator)
    obs_x = np.diag(np.ones(dim_S - 1), 1) + np.diag(np.ones(dim_S - 1), -1)

    exp_values = []
    times = [0.0, 1.0, 2.0, 3.0, 4.0]
    for t in times:
        clock_t = np.array(
            [np.exp(-1j * sys.energies_C[k] * t) / np.sqrt(sys.dim_C) for k in range(sys.dim_C)],
            dtype=complex,
        )
        psi_matrix = psi_product.reshape((sys.dim_C, sys.dim_S))
        proj = np.conj(clock_t) @ psi_matrix
        norm = np.linalg.norm(proj)
        if norm > 1e-12:
            proj /= norm
            exp_val = float(np.real(np.vdot(proj, obs_x @ proj)))
            exp_values.append(exp_val)
        else:
            exp_values.append(0.0)

    dynamics_variance = float(np.var(exp_values))
    return {
        "entanglement_entropy": entropy,
        "dynamics_variance": dynamics_variance,
        "is_static": float(dynamics_variance < 1e-12),
    }


class CoppoMagneticClock:
    """
    Coppo, Cuccoli & Verrucchi (2024) bounded physical magnetic clock model.
    Clock is a large spin J precessing in an external magnetic field.
    System is a quantum harmonic oscillator (dimension n_max <= J).
    Proves continuous time coordinate emerges as J -> infinity with O(n^2/J) error.
    """

    @staticmethod
    def simulate_scaling(J: int, n_max: int = 5, steps: int = 16) -> Dict[str, float]:
        """
        Evaluate fidelity between Coppo equatorial coherent state projection
        and ideal continuous Schrödinger time evolution.
        """
        c_n = np.ones(n_max) / np.sqrt(n_max)
        phi_vals = np.linspace(0.0, 2.0 * np.pi, steps, endpoint=False)
        fidelities = []

        # Exact ratio sqrt(comb(2J, J - n) / comb(2J, J)) computed iteratively
        ratios = np.zeros(n_max, dtype=float)
        for n in range(n_max):
            val = 1.0
            for k in range(1, n + 1):
                val *= (J - k + 1.0) / (J + k * 1.0)
            ratios[n] = np.sqrt(val)

        for phi in phi_vals:
            t = phi  # Unit angular frequency omega = 1
            # Ideal Schrödinger target
            schrodinger = np.array([c_n[n] * np.exp(-1j * n * t) for n in range(n_max)], dtype=complex)
            schrodinger /= np.linalg.norm(schrodinger)

            # Projected state from magnetic clock coherent readout
            weights = np.array([ratios[n] * np.exp(-1j * n * phi) * c_n[n] for n in range(n_max)], dtype=complex)
            coppo = weights / np.linalg.norm(weights)

            fid = float(np.abs(np.vdot(schrodinger, coppo)) ** 2)
            fidelities.append(fid)

        return {
            "spin_J": float(J),
            "mean_fidelity": float(np.mean(fidelities)),
            "min_fidelity": float(np.min(fidelities)),
            "relative_error": float(1.0 - np.mean(fidelities)),
        }


def _self_test() -> str:
    # 1. Page-Wootters Entangled System
    pw = PageWoottersSystem.create(dim_S=8)
    psi = pw.create_entangled_stationary_state()

    # Wheeler-DeWitt constraint verification: H_tot |Psi> = 0
    h_psi = pw.H_tot @ psi
    stationary_err = float(np.linalg.norm(h_psi))
    assert stationary_err < 1e-12, f"Wheeler-DeWitt constraint violated: {stationary_err}"

    # Entanglement entropy must be non-zero
    entropy = von_neumann_entropy(psi, pw.dim_C, pw.dim_S)
    assert entropy > 2.0, f"Expected non-zero entropy, got {entropy}"

    # Verify Schrödinger emergence across time
    for t in [0.0, 0.5, 1.0, 2.0]:
        _, _, fid = pw.project_at_time(psi, t)
        assert abs(fid - 1.0) < 1e-10, f"Fidelity at t={t} drifted: {fid}"

    # 2. Zero-Entanglement Absence of Dynamics
    zero_ent = test_zero_entanglement_absence_of_time(dim_S=8)
    assert zero_ent["entanglement_entropy"] < 1e-12, "Product state must have zero entropy"
    assert zero_ent["dynamics_variance"] < 1e-12, "Zero entanglement must yield zero dynamics"

    # 3. Coppo Magnetic Clock Scaling
    res_small = CoppoMagneticClock.simulate_scaling(J=10, n_max=5)
    res_large = CoppoMagneticClock.simulate_scaling(J=1000, n_max=5)
    assert res_large["mean_fidelity"] > res_small["mean_fidelity"], "Fidelity must improve with larger clock spin"
    assert res_large["mean_fidelity"] > 0.9999, f"Macroscopic clock must approach 1.0: {res_large['mean_fidelity']}"

    return "emergent_time._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())
