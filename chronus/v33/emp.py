# emp.py
# Chronos GPU -- Error Mitigation Processor (production, 4 Aug 2026)
#
# Hardware-agnostic EMP: Kalman filtering of a measurement stream, Uhlmann
# fidelity gating, symplectic-style (unitary) correction pulses on the
# density matrix, and conditional-Gaussian extrapolation of unmeasured faces
# from the state's covariance structure.
#
# This is the mathematical core of the Enhanced Pseudocode's EMP, closed
# around a real weak-measurement stream (see weak_measurement.py). No
# lasers, cryogenics, or fabricated fidelity scores.

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .weak_measurement import (
    WeakMeasurementRecord,
    apply_weak_measurement,
    bayesian_inversion,
    density_to_distribution,
    face_probe_observables,
    project_to_psd_hermitian,
    pure_state_to_density,
    uhlmann_fidelity,
)


@dataclass
class MeasurementPoint:
    probe_id: int
    value: float
    time: float = 0.0


@dataclass
class EMPReport:
    fidelity_trace: List[float]
    corrections_applied: int
    denoised: List[MeasurementPoint]
    extrapolated_field: np.ndarray
    compensated_rho: np.ndarray
    compensated_distribution: np.ndarray
    final_fidelity_to_reference: float


class ScalarKalman:
    """1-D Kalman filter for denoising a scalar measurement stream.

    Standard predict/update with constant process/measurement noise.
    Deterministic given the sequence and (q, r) hyperparameters.
    """

    def __init__(self, process_var: float = 1e-4, meas_var: float = 1e-2, x0: float = 0.0, p0: float = 1.0):
        self.q = float(process_var)
        self.r = float(meas_var)
        self.x = float(x0)
        self.p = float(p0)

    def update(self, z: float) -> float:
        # Predict
        p_pred = self.p + self.q
        # Update
        k = p_pred / (p_pred + self.r)
        self.x = self.x + k * (z - self.x)
        self.p = (1.0 - k) * p_pred
        return self.x


class ErrorMitigationProcessor:
    """Closed EMP: fidelity monitor, unitary corrections, Kalman denoise,
    conditional-Gaussian fill of unmeasured probes."""

    def __init__(
        self,
        n_faces: int,
        fidelity_threshold: float = 0.95,
        epsilon: float = 0.01,
        process_var: float = 1e-4,
        meas_var: float = 1e-2,
    ):
        self.n = n_faces
        self.fidelity_threshold = float(fidelity_threshold)
        self.epsilon = float(epsilon)
        self.process_var = process_var
        self.meas_var = meas_var
        self._kalman: Dict[int, ScalarKalman] = {}
        self.corrections_applied = 0
        self.fidelity_trace: List[float] = []

    def _kalman_for(self, probe_id: int) -> ScalarKalman:
        if probe_id not in self._kalman:
            self._kalman[probe_id] = ScalarKalman(self.process_var, self.meas_var)
        return self._kalman[probe_id]

    def estimate_fidelity(self, rho: np.ndarray, reference: np.ndarray) -> float:
        return uhlmann_fidelity(rho, reference)

    def unitary_correction(self, rho: np.ndarray, generator: np.ndarray, angle: float) -> np.ndarray:
        """Apply U ρ U† with U = exp(-i θ G), G Hermitian (symplectic-style pulse).

        Exact via eigendecomposition of G — not a Trotter approximation.
        """
        g = 0.5 * (generator + generator.conj().T)
        eigvals, eigvecs = np.linalg.eigh(g)
        phases = np.exp(-1j * float(angle) * eigvals)
        u = (eigvecs * phases) @ eigvecs.conj().T
        out = u @ rho @ u.conj().T
        return project_to_psd_hermitian(out)

    def monitor_and_correct(
        self,
        rho: np.ndarray,
        reference: np.ndarray,
        generator: Optional[np.ndarray] = None,
        angle: float = 0.05,
    ) -> Tuple[np.ndarray, float]:
        """If fidelity to reference drops below threshold, apply one unitary pulse."""
        fid = self.estimate_fidelity(rho, reference)
        self.fidelity_trace.append(fid)
        if fid < self.fidelity_threshold:
            if generator is None:
                # Default: correct along the dominant eigen-direction of (ρ − ref)
                delta = project_to_psd_hermitian(rho) - project_to_psd_hermitian(reference)
                generator = 0.5 * (delta + delta.conj().T)
            rho = self.unitary_correction(rho, generator, angle)
            self.corrections_applied += 1
            fid = self.estimate_fidelity(rho, reference)
            self.fidelity_trace.append(fid)
        return rho, fid

    def denoise_stream(self, stream: Sequence[MeasurementPoint]) -> List[MeasurementPoint]:
        """Per-probe Kalman denoise of the weak-measurement stream."""
        out: List[MeasurementPoint] = []
        for pt in stream:
            kf = self._kalman_for(pt.probe_id)
            corrected = kf.update(pt.value)
            out.append(MeasurementPoint(probe_id=pt.probe_id, value=corrected, time=pt.time))
        return out

    def state_covariance(self, rho: np.ndarray) -> np.ndarray:
        """Classical covariance of the face-occupation random variable.

        For a projective measurement in the face basis,
            Cov_ij = δ_ij p_i − p_i p_j
        with p = diag(ρ). This is the exact second-moment structure used by
        the EMP's conditional-expectation interpolator.
        """
        p = density_to_distribution(rho)
        return np.diag(p) - np.outer(p, p)

    def extrapolate_unmeasured(
        self,
        rho: np.ndarray,
        measured: Sequence[MeasurementPoint],
        ridge: float = 1e-8,
    ) -> np.ndarray:
        """Conditional expectation E[X_k | X_measured] for every face k.

        Standard Gaussian conditional mean:
            μ_{u|m} = μ_u + Σ_{um} Σ_{mm}^{-1} (x_m − μ_m)
        with μ = diag(ρ), Σ from state_covariance. Ridge stabilises Σ_mm.
        """
        n = self.n
        mu = density_to_distribution(rho)
        cov = self.state_covariance(rho)
        field = mu.copy()

        if not measured:
            return field

        m_ids = [pt.probe_id for pt in measured]
        m_vals = np.array([pt.value for pt in measured], dtype=np.float64)
        # Unique probes (last value wins)
        uniq: Dict[int, float] = {}
        for i, v in zip(m_ids, m_vals):
            uniq[int(i)] = float(v)
        m_ids = sorted(uniq.keys())
        m_vals = np.array([uniq[i] for i in m_ids], dtype=np.float64)

        sigma_mm = cov[np.ix_(m_ids, m_ids)] + ridge * np.eye(len(m_ids))
        try:
            sigma_mm_inv = np.linalg.inv(sigma_mm)
        except np.linalg.LinAlgError:
            sigma_mm_inv = np.linalg.pinv(sigma_mm)

        residual = m_vals - mu[m_ids]
        for k in range(n):
            if k in uniq:
                field[k] = uniq[k]
            else:
                sigma_km = cov[k, m_ids]
                field[k] = mu[k] + float(sigma_km @ sigma_mm_inv @ residual)

        # Renormalise to a probability distribution
        field = np.clip(field, 0.0, None)
        s = field.sum()
        if s > 0:
            field = field / s
        return field

    def run_session(
        self,
        initial_state: np.ndarray,
        probe_indices: Sequence[int],
        reference: Optional[np.ndarray] = None,
        hamiltonian: Optional[np.ndarray] = None,
        dt: float = 0.01,
        evolve_steps_between_measures: int = 1,
    ) -> EMPReport:
        """Full EMP pipeline on a pure initial state:

        1. Optional short unitary evolution under H between probes
        2. Weak measurement of selected face probes
        3. Fidelity monitor + unitary correction against reference
        4. Kalman denoise of the stream
        5. Bayesian observer-effect compensation
        6. Conditional-Gaussian extrapolation to all faces
        """
        n = self.n
        rho = pure_state_to_density(initial_state) if initial_state.ndim == 1 else project_to_psd_hermitian(initial_state)
        if reference is None:
            reference = rho.copy()
        else:
            reference = (
                pure_state_to_density(reference)
                if reference.ndim == 1
                else project_to_psd_hermitian(reference)
            )

        probes = face_probe_observables(n)
        stream: List[MeasurementPoint] = []
        records: List[WeakMeasurementRecord] = []
        t = 0.0
        self.corrections_applied = 0
        self.fidelity_trace = []

        for pid in probe_indices:
            # Optional coherent evolution between measurements
            if hamiltonian is not None and evolve_steps_between_measures > 0:
                h = 0.5 * (hamiltonian + hamiltonian.conj().T)
                eigvals, eigvecs = np.linalg.eigh(h)
                for _ in range(evolve_steps_between_measures):
                    phases = np.exp(-1j * dt * eigvals)
                    u = (eigvecs * phases) @ eigvecs.conj().T
                    rho = project_to_psd_hermitian(u @ rho @ u.conj().T)
                    t += dt

            result = apply_weak_measurement(rho, probes[pid], self.epsilon, probe_id=int(pid))
            rho = result.rho_after
            records.append(result.record)
            stream.append(MeasurementPoint(probe_id=int(pid), value=result.expectation, time=t))

            rho, _ = self.monitor_and_correct(rho, reference, generator=h if hamiltonian is not None else None)

        denoised = self.denoise_stream(stream)
        compensated_rho = bayesian_inversion(rho, records)
        extrapolated = self.extrapolate_unmeasured(compensated_rho, denoised)
        final_fid = self.estimate_fidelity(compensated_rho, reference)

        return EMPReport(
            fidelity_trace=list(self.fidelity_trace),
            corrections_applied=self.corrections_applied,
            denoised=denoised,
            extrapolated_field=extrapolated,
            compensated_rho=compensated_rho,
            compensated_distribution=density_to_distribution(compensated_rho),
            final_fidelity_to_reference=final_fid,
        )


def _self_test() -> str:
    n = 16
    psi = np.zeros(n, dtype=complex)
    psi[3] = 1.0
    emp = ErrorMitigationProcessor(n_faces=n, fidelity_threshold=0.90, epsilon=0.02)

    # Path without inter-probe evolution: peak must stay on prepared face
    budget = list(range(0, n, 2))
    report0 = emp.run_session(psi, probe_indices=budget, hamiltonian=None)
    assert len(report0.denoised) == len(budget)
    assert report0.extrapolated_field.shape == (n,)
    assert abs(report0.extrapolated_field.sum() - 1.0) < 1e-8
    assert 0.0 <= report0.final_fidelity_to_reference <= 1.0
    peak = int(np.argmax(report0.compensated_distribution))
    assert peak == 3, f"expected peak at 3, got {peak}"
    assert np.all(np.isfinite(report0.extrapolated_field))

    # Path with coherent evolution between probes (non-trivial H)
    rng = np.random.default_rng(0)
    a = rng.normal(size=(n, n))
    h = 0.5 * (a + a.T)
    emp_h = ErrorMitigationProcessor(n_faces=n, fidelity_threshold=0.90, epsilon=0.02)
    report = emp_h.run_session(psi, probe_indices=budget, hamiltonian=h, dt=0.05)
    assert abs(report.extrapolated_field.sum() - 1.0) < 1e-8
    assert np.all(np.isfinite(report.extrapolated_field))

    # Determinism of the full EMP session
    emp2 = ErrorMitigationProcessor(n_faces=n, fidelity_threshold=0.90, epsilon=0.02)
    report2 = emp2.run_session(psi, probe_indices=budget, hamiltonian=h, dt=0.05)
    assert np.allclose(report.extrapolated_field, report2.extrapolated_field)

    return "emp._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())
