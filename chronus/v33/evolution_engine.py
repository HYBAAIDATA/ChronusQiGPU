# evolution_engine.py
# Chronos GPU -- Evolution Engine v3.0 (gap-close pass, 4 Aug 2026)
#
# History:
#   v1.0 returned an unrelated random vector.
#   v2.0 exact ground state via dense eigh + power-iteration loss curve.
#   v3.0 closes the Enhanced-Pseudocode mathematical gaps that are
#   hardware-agnostic:
#     - optional time-dependent H(t) via piecewise-constant Trotter
#       (animation keyframes → schedule of Hamiltonians)
#     - optional weak-measurement + EMP closed loop (density-matrix channel,
#       fidelity gating, Kalman denoise, Bayesian observer-effect
#       compensation, conditional-Gaussian field extrapolation)
#   The default path remains exact ground-state diagonalisation so existing
#   callers and validated baseline energies are unchanged.

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .emp import ErrorMitigationProcessor, EMPReport


@dataclass
class RenderResult:
    final_state: np.ndarray
    distribution: np.ndarray
    energy: float
    parameters: np.ndarray
    loss_curve: List[float]
    expectation_values: Dict[str, float]
    # v3.0 optional fields (None when the exact-ground-state path is used)
    emp_report: Optional[EMPReport] = None
    time_dependent: bool = False
    fidelity_to_ground: Optional[float] = None


def _hermitize(h: np.ndarray) -> np.ndarray:
    return 0.5 * (h + h.T.conj())


def _ground_state(h: np.ndarray) -> Tuple[float, np.ndarray]:
    h = _hermitize(h)
    eigvals, eigvecs = np.linalg.eigh(h)
    energy = float(eigvals[0])
    state = eigvecs[:, 0].astype(complex)
    peak = int(np.argmax(np.abs(state)))
    if state[peak].real < 0:
        state = -state
    return energy, state


def _unitary_evolve(rho_or_state: np.ndarray, h: np.ndarray, dt: float) -> np.ndarray:
    """Exact U = exp(-i H dt) applied to a state vector or density matrix."""
    h = _hermitize(h)
    eigvals, eigvecs = np.linalg.eigh(h)
    phases = np.exp(-1j * float(dt) * eigvals)
    u = (eigvecs * phases) @ eigvecs.conj().T
    if rho_or_state.ndim == 1:
        return u @ rho_or_state
    return u @ rho_or_state @ u.conj().T


def build_time_dependent_schedule(
    base_hamiltonian: np.ndarray,
    keyframes: Sequence[Tuple[float, float]],
    n_slices: int = 20,
) -> List[Tuple[float, np.ndarray]]:
    """Piecewise-constant H(t) from (time, scale) keyframes.

    Between keyframes the scale is linearly interpolated and applied as
    H(t) = scale(t) * base_hamiltonian. Returns a list of (dt, H_slice)
    covering t ∈ [t_min, t_max].
    """
    if not keyframes:
        return [(1.0, base_hamiltonian)]
    times = np.array([float(t) for t, _ in keyframes], dtype=np.float64)
    scales = np.array([float(s) for _, s in keyframes], dtype=np.float64)
    order = np.argsort(times)
    times, scales = times[order], scales[order]
    t0, t1 = float(times[0]), float(times[-1])
    if t1 <= t0:
        return [(1.0, float(scales[0]) * base_hamiltonian)]
    ts = np.linspace(t0, t1, n_slices + 1)
    schedule: List[Tuple[float, np.ndarray]] = []
    for i in range(n_slices):
        tc = 0.5 * (ts[i] + ts[i + 1])
        scale = float(np.interp(tc, times, scales))
        dt = float(ts[i + 1] - ts[i])
        schedule.append((dt, scale * base_hamiltonian))
    return schedule


class EvolutionEngine:
    def __init__(
        self,
        n_faces: int = 32,
        layers: int = 4,
        adjacency: Optional[np.ndarray] = None,
        enable_emp: bool = False,
        emp_fidelity_threshold: float = 0.95,
        emp_epsilon: float = 0.01,
        emp_readout_fraction: float = 0.25,
    ):
        self.n = n_faces
        self.layers = layers
        self.adjacency = adjacency if adjacency is not None else np.eye(n_faces)
        self.enable_emp = enable_emp
        self.emp_fidelity_threshold = emp_fidelity_threshold
        self.emp_epsilon = emp_epsilon
        self.emp_readout_fraction = emp_readout_fraction

    def _assemble_objective(
        self,
        hamiltonian_terms: List[np.ndarray],
        resonance_weights: Optional[np.ndarray],
    ) -> np.ndarray:
        objective = sum(hamiltonian_terms) if hamiltonian_terms else np.zeros((self.n, self.n))
        if resonance_weights is not None:
            objective = objective - np.diag(resonance_weights)
        return _hermitize(np.asarray(objective, dtype=np.float64))

    def evolve(
        self,
        hamiltonian_terms: List[np.ndarray],
        resonance_weights: Optional[np.ndarray],
        steps: int = 60,
        seed: int = 0,
        animation_keyframes: Optional[Sequence[Tuple[float, float]]] = None,
        enable_emp: Optional[bool] = None,
    ) -> RenderResult:
        objective = self._assemble_objective(hamiltonian_terms, resonance_weights)
        use_emp = self.enable_emp if enable_emp is None else enable_emp

        # ---- Path A: time-dependent piecewise evolution ----
        if animation_keyframes:
            return self._evolve_time_dependent(objective, animation_keyframes, steps, seed, use_emp)

        # ---- Path B: exact ground state (default, validated baseline) ----
        ground_energy, ground_state = _ground_state(objective)

        rng = np.random.default_rng(seed)
        theta = 0.1 * rng.standard_normal((self.layers, self.n, 3))

        shift = float(np.max(np.abs(np.linalg.eigvalsh(objective)))) + 1.0
        shifted = shift * np.eye(self.n) - objective
        v = rng.standard_normal(self.n)
        v = v / np.linalg.norm(v)
        loss_curve: List[float] = []
        for _ in range(steps):
            v = shifted @ v
            v = v / np.linalg.norm(v)
            loss_curve.append(float(v @ objective @ v))

        distribution = np.abs(ground_state) ** 2
        distribution = distribution / distribution.sum()

        emp_report = None
        fidelity = None
        final_state = ground_state
        if use_emp:
            emp_report, final_state, distribution, fidelity = self._run_emp_loop(
                ground_state, objective, seed
            )

        expectations = {
            "energy": ground_energy,
            "intensity": 1.0,
            "depth": float(np.mean(distribution)),
            "normal": float(np.std(distribution)),
        }
        return RenderResult(
            final_state=final_state,
            distribution=distribution,
            energy=ground_energy,
            parameters=theta,
            loss_curve=loss_curve,
            expectation_values=expectations,
            emp_report=emp_report,
            time_dependent=False,
            fidelity_to_ground=fidelity,
        )

    def _evolve_time_dependent(
        self,
        base_h: np.ndarray,
        keyframes: Sequence[Tuple[float, float]],
        steps: int,
        seed: int,
        use_emp: bool,
    ) -> RenderResult:
        schedule = build_time_dependent_schedule(base_h, keyframes, n_slices=max(steps, 2))
        # Start in the ground state of the first slice
        _, state = _ground_state(schedule[0][1])
        loss_curve: List[float] = []
        for dt, h_slice in schedule:
            state = _unitary_evolve(state, h_slice, dt)
            state = state / np.linalg.norm(state)
            loss_curve.append(float(np.real(state.conj() @ h_slice @ state)))

        # Final energy = expectation under the last slice (and under base_h)
        final_energy = float(np.real(state.conj() @ base_h @ state))
        distribution = np.abs(state) ** 2
        distribution = distribution / distribution.sum()

        emp_report = None
        fidelity = None
        if use_emp:
            emp_report, state, distribution, fidelity = self._run_emp_loop(state, base_h, seed)

        rng = np.random.default_rng(seed)
        theta = 0.1 * rng.standard_normal((self.layers, self.n, 3))
        expectations = {
            "energy": final_energy,
            "intensity": 1.0,
            "depth": float(np.mean(distribution)),
            "normal": float(np.std(distribution)),
        }
        return RenderResult(
            final_state=state,
            distribution=distribution,
            energy=final_energy,
            parameters=theta,
            loss_curve=loss_curve,
            expectation_values=expectations,
            emp_report=emp_report,
            time_dependent=True,
            fidelity_to_ground=fidelity,
        )

    def _run_emp_loop(
        self,
        state: np.ndarray,
        hamiltonian: np.ndarray,
        seed: int,
    ) -> Tuple[EMPReport, np.ndarray, np.ndarray, float]:
        """Closed weak-measurement + EMP loop with readout budget."""
        n_probes = max(1, int(round(self.emp_readout_fraction * self.n)))
        # Prioritise faces by Born probability (information-gain proxy)
        p = np.abs(state) ** 2
        p = p / p.sum()
        # Deterministic top-n_probes by probability, tie-broken by index
        order = np.argsort(-p, kind="stable")
        probe_indices = sorted(int(i) for i in order[:n_probes])

        emp = ErrorMitigationProcessor(
            n_faces=self.n,
            fidelity_threshold=self.emp_fidelity_threshold,
            epsilon=self.emp_epsilon,
        )
        report = emp.run_session(
            initial_state=state,
            probe_indices=probe_indices,
            reference=state,
            hamiltonian=hamiltonian,
            dt=0.01,
            evolve_steps_between_measures=1,
        )
        # Prefer EMP-extrapolated field as the rendering distribution
        distribution = report.extrapolated_field
        # Reconstruct a pure-state amplitude proxy from compensated ρ diagonal
        amp = np.sqrt(np.clip(report.compensated_distribution, 0.0, None))
        # Match global phase of original state on its peak component
        peak = int(np.argmax(np.abs(state)))
        if abs(amp[peak]) > 1e-15 and abs(state[peak]) > 1e-15:
            phase = np.exp(1j * (np.angle(state[peak]) - np.angle(amp[peak] + 0j)))
            amp = amp * phase
        amp = amp / np.linalg.norm(amp)
        fidelity = report.final_fidelity_to_reference
        return report, amp.astype(complex), distribution, fidelity


def _self_test() -> str:
    n = 8
    h = np.diag(np.linspace(-2.0, 2.0, n))
    eng = EvolutionEngine(n_faces=n, layers=2)

    # Default path: exact ground state
    r = eng.evolve([h], None, steps=10, seed=0)
    assert np.isclose(r.energy, -2.0)
    assert np.isclose(r.distribution.sum(), 1.0)
    assert r.emp_report is None
    assert r.time_dependent is False

    # EMP path
    eng_emp = EvolutionEngine(n_faces=n, layers=2, enable_emp=True, emp_readout_fraction=0.5)
    r2 = eng_emp.evolve([h], None, steps=10, seed=0)
    assert r2.emp_report is not None
    assert r2.fidelity_to_ground is not None
    assert 0.0 <= r2.fidelity_to_ground <= 1.0
    assert np.isclose(r2.distribution.sum(), 1.0)

    # Time-dependent path
    keyframes = [(0.0, 1.0), (1.0, 0.5), (2.0, 1.0)]
    r3 = eng.evolve([h], None, steps=12, seed=0, animation_keyframes=keyframes)
    assert r3.time_dependent is True
    assert len(r3.loss_curve) >= 2
    assert np.isfinite(r3.energy)

    # Determinism
    r4 = eng.evolve([h], None, steps=10, seed=0)
    assert r.energy == r4.energy
    assert np.allclose(r.distribution, r4.distribution)

    return "evolution_engine._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())
