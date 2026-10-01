# weak_measurement.py
# Chronos GPU -- weak measurement channel (production, 4 Aug 2026)
#
# Pure finite-dimensional quantum measurement theory on the manifold state.
# Hardware-agnostic: density matrices, Kraus maps, and Bayesian retrodiction
# only -- no lasers, detectors, or cryogenics.
#
# Implements the Enhanced Pseudocode's weak-measurement / observer-effect
# mathematics:
#   M_ε = I + ε O                         (weak measurement operator)
#   ρ  ↦  M ρ M† / Tr(M† M ρ)             (Kraus backaction)
#   ⟨M⟩ = Tr(ρ M)                         (pointer expectation)
#   Bayesian inversion of a sequence of M's to recover ρ_before
#     (observer-effect compensation / quantum state retrodiction)
#
# All operations are exact linear algebra on n×n Hermitian PSD density
# matrices (n = number of manifold faces). Deterministic given (ρ, O, ε).

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

import numpy as np


def pure_state_to_density(state: np.ndarray) -> np.ndarray:
    """|ψ⟩⟨ψ| from a state vector (column)."""
    v = np.asarray(state, dtype=complex).reshape(-1, 1)
    return v @ v.conj().T


def density_to_distribution(rho: np.ndarray) -> np.ndarray:
    """Born probabilities = diagonal of ρ (always real, non-negative)."""
    d = np.real(np.diag(rho))
    d = np.clip(d, 0.0, None)
    s = d.sum()
    return d / s if s > 0 else np.full(rho.shape[0], 1.0 / rho.shape[0])


def project_to_psd_hermitian(rho: np.ndarray, tol: float = 1e-14) -> np.ndarray:
    """Symmetrise and clip negative eigenvalues (numerical hygiene after updates)."""
    rho = 0.5 * (rho + rho.conj().T)
    eigvals, eigvecs = np.linalg.eigh(rho)
    eigvals = np.clip(eigvals, 0.0, None)
    out = (eigvecs * eigvals) @ eigvecs.conj().T
    tr = np.trace(out).real
    if tr > tol:
        out = out / tr
    return out


def weak_measurement_operator(observable: np.ndarray, epsilon: float) -> np.ndarray:
    """M_ε = I + ε O.  O must be Hermitian; M is not unitary for ε ≠ 0."""
    o = np.asarray(observable, dtype=complex)
    o = 0.5 * (o + o.conj().T)
    n = o.shape[0]
    return np.eye(n, dtype=complex) + float(epsilon) * o


@dataclass
class WeakMeasurementRecord:
    """One weak measurement event, retained for Bayesian retrodiction."""
    probe_id: int
    epsilon: float
    observable: np.ndarray
    expectation: float
    operator: np.ndarray  # M_ε used


@dataclass
class WeakMeasurementResult:
    expectation: float
    rho_after: np.ndarray
    record: WeakMeasurementRecord


def apply_weak_measurement(
    rho: np.ndarray,
    observable: np.ndarray,
    epsilon: float = 0.01,
    probe_id: int = 0,
) -> WeakMeasurementResult:
    """Apply one weak measurement: compute ⟨M⟩ and update ρ via Kraus map.

    Forward channel (exact, unnormalised then normalised):
        ρ' = M ρ M† / Tr(M† M ρ)
    with M = I + ε O.
    """
    rho = project_to_psd_hermitian(rho)
    o = 0.5 * (np.asarray(observable, dtype=complex) + np.asarray(observable, dtype=complex).conj().T)
    m = weak_measurement_operator(o, epsilon)
    # ⟨M⟩ = Tr(ρ M)  (complex in general; report real part for pointer)
    expectation = float(np.trace(rho @ m).real)
    # Kraus update
    m_rho_m = m @ rho @ m.conj().T
    norm = np.trace(m_rho_m).real
    if norm <= 1e-30:
        rho_after = rho.copy()
    else:
        rho_after = project_to_psd_hermitian(m_rho_m / norm)
    record = WeakMeasurementRecord(
        probe_id=probe_id,
        epsilon=float(epsilon),
        observable=o,
        expectation=expectation,
        operator=m,
    )
    return WeakMeasurementResult(expectation=expectation, rho_after=rho_after, record=record)


def bayesian_inversion(
    rho_after: np.ndarray,
    records: Sequence[WeakMeasurementRecord],
) -> np.ndarray:
    """Observer-effect compensation: recover the most likely ρ_before.

    For a single weak measurement with M = I + ε O and small ε,
        ρ_after = M ρ_before M† / Tr(...)
    so approximately
        ρ_before ∝ M^{-1} ρ_after (M†)^{-1},
    with M^{-1} ≈ I − ε O (first-order) or exact inverse when M is invertible.

    Records are applied in *reverse* chronological order (last measurement
    inverted first), matching the pseudocode's BAYESIAN_INVERSION.
    """
    rho = project_to_psd_hermitian(rho_after)
    for rec in reversed(list(records)):
        m = rec.operator
        # Prefer exact inverse; fall back to first-order I − ε O.
        try:
            m_inv = np.linalg.inv(m)
        except np.linalg.LinAlgError:
            m_inv = np.eye(m.shape[0], dtype=complex) - rec.epsilon * rec.observable
        rho = m_inv @ rho @ m_inv.conj().T
        rho = project_to_psd_hermitian(rho)
    return rho


def project_state_to_field(
    rho: np.ndarray,
    observables: Sequence[np.ndarray],
) -> np.ndarray:
    """⟨O_k⟩ = Tr(ρ O_k) for each probe observable — the classical field sample."""
    rho = project_to_psd_hermitian(rho)
    return np.array([float(np.trace(rho @ o).real) for o in observables], dtype=np.float64)


def face_probe_observables(n_faces: int) -> List[np.ndarray]:
    """Canonical probe set: one projector |k⟩⟨k| per manifold face."""
    probes = []
    for k in range(n_faces):
        o = np.zeros((n_faces, n_faces), dtype=complex)
        o[k, k] = 1.0
        probes.append(o)
    return probes


def uhlmann_fidelity(rho: np.ndarray, sigma: np.ndarray) -> float:
    """F(ρ, σ) = [Tr √(√ρ σ √ρ)]²  via Hermitian eigendecomposition (no scipy)."""
    def _sqrtm(a: np.ndarray) -> np.ndarray:
        a = 0.5 * (a + a.conj().T)
        w, v = np.linalg.eigh(a)
        w = np.clip(w, 0.0, None)
        return (v * np.sqrt(w)) @ v.conj().T

    rho = project_to_psd_hermitian(rho)
    sigma = project_to_psd_hermitian(sigma)
    sqrt_rho = _sqrtm(rho)
    inner = sqrt_rho @ sigma @ sqrt_rho
    val = np.trace(_sqrtm(inner)).real
    return float(np.clip(val ** 2, 0.0, 1.0))


@dataclass
class WeakMeasurementSession:
    """Accumulates a stream of weak measurements and supports retrodiction."""
    rho: np.ndarray
    epsilon: float = 0.01
    records: List[WeakMeasurementRecord] = field(default_factory=list)

    @classmethod
    def from_pure_state(cls, state: np.ndarray, epsilon: float = 0.01) -> "WeakMeasurementSession":
        return cls(rho=pure_state_to_density(state), epsilon=epsilon)

    def measure(self, observable: np.ndarray, probe_id: int = 0) -> float:
        result = apply_weak_measurement(self.rho, observable, self.epsilon, probe_id=probe_id)
        self.rho = result.rho_after
        self.records.append(result.record)
        return result.expectation

    def measure_face_probes(
        self,
        probe_indices: Optional[Sequence[int]] = None,
        n_faces: Optional[int] = None,
    ) -> List[float]:
        n = self.rho.shape[0] if n_faces is None else n_faces
        indices = list(range(n)) if probe_indices is None else list(probe_indices)
        probes = face_probe_observables(n)
        return [self.measure(probes[i], probe_id=i) for i in indices]

    def compensate_observer_effect(self) -> np.ndarray:
        """Return the Bayesian-inverted pre-measurement density matrix."""
        return bayesian_inversion(self.rho, self.records)

    def compensated_distribution(self) -> np.ndarray:
        return density_to_distribution(self.compensate_observer_effect())


def _self_test() -> str:
    n = 8
    # Pure computational-basis state |2⟩
    psi = np.zeros(n, dtype=complex)
    psi[2] = 1.0
    rho0 = pure_state_to_density(psi)
    assert abs(uhlmann_fidelity(rho0, rho0) - 1.0) < 1e-12

    # Weak measure σ_z-like observable on a single face projector
    o = np.zeros((n, n), dtype=complex)
    o[2, 2] = 1.0
    res = apply_weak_measurement(rho0, o, epsilon=0.05)
    assert 0.9 < res.expectation < 1.1 + 0.05  # near 1 + ε
    # State remains nearly pure and concentrated on face 2
    dist = density_to_distribution(res.rho_after)
    assert dist[2] > 0.9

    # Bayesian inversion recovers a state close to ρ0 for small ε
    session = WeakMeasurementSession.from_pure_state(psi, epsilon=0.01)
    probes = face_probe_observables(n)
    for i in (0, 2, 5):
        session.measure(probes[i], probe_id=i)
    rho_hat = session.compensate_observer_effect()
    fid = uhlmann_fidelity(rho0, rho_hat)
    assert fid > 0.98, f"retrodiction fidelity {fid} too low"

    # Distribution sums to 1
    d = session.compensated_distribution()
    assert abs(d.sum() - 1.0) < 1e-10

    return "weak_measurement._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())
