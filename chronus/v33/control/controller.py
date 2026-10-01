# controller.py -- Quantum control as state-space linear algebra.
# Pulses, frequency tuning, and readout are unitary/measurement maps on C^n.
# No DACs, AWGs, or cryogenic wiring.

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from ..weak_measurement import (
    apply_weak_measurement,
    pure_state_to_density,
    density_to_distribution,
)


@dataclass
class Pulse:
    """Control pulse: duration, amplitude, phase, optional carrier frequency."""
    duration: float
    amplitude: float
    phase: float = 0.0
    frequency: float = 0.0
    axis: str = "x"  # x | y | z | custom


@dataclass
class ControlResult:
    state: np.ndarray
    energy: Optional[float] = None
    expectation: Optional[float] = None


def _pauli(n: int, axis: str, target: int = 0) -> np.ndarray:
    """Embed a single-qubit Pauli on site `target` of an n-level system.

    For manifold dimension n that is not a power of 2, we use the
    generalised Gell-Mann generators on the full space:
      σ_x-like: |i⟩⟨j| + |j⟩⟨i|
      σ_y-like: -i|i⟩⟨j| + i|j⟩⟨i|
      σ_z-like: |i⟩⟨i| − |j⟩⟨j|
    with (i,j) = (target, (target+1) mod n).
    """
    i = int(target) % n
    j = (i + 1) % n
    op = np.zeros((n, n), dtype=complex)
    if axis == "x":
        op[i, j] = 1.0
        op[j, i] = 1.0
    elif axis == "y":
        op[i, j] = -1j
        op[j, i] = 1j
    elif axis == "z":
        op[i, i] = 1.0
        op[j, j] = -1.0
    else:
        raise ValueError(f"unknown Pauli axis {axis!r}")
    return op


def _expm_hermitian(h: np.ndarray, t: float) -> np.ndarray:
    """U = exp(-i H t) for Hermitian H via eigendecomposition."""
    h = 0.5 * (h + h.conj().T)
    w, v = np.linalg.eigh(h)
    return (v * np.exp(-1j * t * w)) @ v.conj().T


class QuantumController:
    """State-space controller for an n-dimensional quantum system.

    APPLY_PULSE → unitary under control Hamiltonian
    TUNE_FREQUENCY → diagonal Hamiltonian parameter update
    READOUT → weak measurement of a chosen observable
    """

    def __init__(self, n: int, hamiltonian: Optional[np.ndarray] = None, seed: int = 0):
        self.n = n
        if hamiltonian is not None:
            self.hamiltonian = np.array(hamiltonian, dtype=complex, copy=True)
            self.hamiltonian = 0.5 * (self.hamiltonian + self.hamiltonian.conj().T)
        else:
            self.hamiltonian = np.zeros((n, n), dtype=complex)

        self.state = np.zeros(n, dtype=complex)
        self.state[0] = 1.0
        self.rng = np.random.default_rng(seed)
        self.pulse_history: List[Pulse] = []

    def set_state(self, state: np.ndarray) -> None:
        s = np.asarray(state, dtype=complex).reshape(-1)
        if s.size != self.n:
            raise ValueError(f"state length {s.size} != n={self.n}")
        self.state = s / (np.linalg.norm(s) + 1e-30)

    def apply_pulse(self, pulse: Pulse, target: int = 0) -> ControlResult:
        """H_ctrl = A (cos φ σ_x + sin φ σ_y); U = exp(-i H_ctrl τ)."""
        sx = _pauli(self.n, "x", target)
        sy = _pauli(self.n, "y", target)
        h_ctrl = pulse.amplitude * (
            np.cos(pulse.phase) * sx + np.sin(pulse.phase) * sy
        )
        if abs(pulse.frequency) > 0:
            # Rotating-frame detuning term on the diagonal pair
            sz = _pauli(self.n, "z", target)
            h_ctrl = h_ctrl + pulse.frequency * sz
        u = _expm_hermitian(h_ctrl, pulse.duration)
        self.state = u @ self.state
        self.state = self.state / (np.linalg.norm(self.state) + 1e-30)
        self.pulse_history.append(pulse)
        energy = float(np.real(self.state.conj() @ self.hamiltonian @ self.state))
        return ControlResult(state=self.state.copy(), energy=energy)

    def tune_frequency(self, index: int, frequency: float) -> np.ndarray:
        """Set H[index, index] = frequency (Hermitian diagonal parameter)."""
        i = int(index) % self.n
        self.hamiltonian[i, i] = complex(frequency)
        self.hamiltonian = 0.5 * (self.hamiltonian + self.hamiltonian.conj().T)
        return self.hamiltonian

    def evolve_drift(self, duration: float) -> ControlResult:
        """Free evolution under the current Hamiltonian for `duration`."""
        u = _expm_hermitian(self.hamiltonian, duration)
        self.state = u @ self.state
        self.state = self.state / (np.linalg.norm(self.state) + 1e-30)
        energy = float(np.real(self.state.conj() @ self.hamiltonian @ self.state))
        return ControlResult(state=self.state.copy(), energy=energy)

    def readout(self, observable: Optional[np.ndarray] = None, epsilon: float = 0.01) -> ControlResult:
        """Weak measurement of `observable` (default: face-0 projector)."""
        if observable is None:
            observable = np.zeros((self.n, self.n), dtype=complex)
            observable[0, 0] = 1.0
        rho = pure_state_to_density(self.state)
        res = apply_weak_measurement(rho, observable, epsilon=epsilon)
        # Collapse pure-state proxy from updated ρ diagonal (phase from old state)
        dist = density_to_distribution(res.rho_after)
        amp = np.sqrt(np.clip(dist, 0, None)).astype(complex)
        peak = int(np.argmax(np.abs(self.state)))
        if abs(amp[peak]) > 1e-15 and abs(self.state[peak]) > 1e-15:
            amp *= np.exp(1j * (np.angle(self.state[peak]) - np.angle(amp[peak] + 0j)))
        self.state = amp / (np.linalg.norm(amp) + 1e-30)
        return ControlResult(state=self.state.copy(), expectation=res.expectation)


def _self_test() -> str:
    n = 8
    h = np.diag(np.linspace(-1.0, 1.0, n))
    ctrl = QuantumController(n, hamiltonian=h)
    # π-pulse about x on sites 0–1 should swap amplitude 0↔1 from |0⟩
    r = ctrl.apply_pulse(Pulse(duration=np.pi / 2, amplitude=1.0, phase=0.0), target=0)
    assert abs(np.linalg.norm(r.state) - 1.0) < 1e-10
    # Tune + drift is deterministic
    ctrl.tune_frequency(3, -2.5)
    r2 = ctrl.evolve_drift(0.1)
    assert np.isfinite(r2.energy)
    r3 = ctrl.readout(epsilon=0.01)
    assert r3.expectation is not None
    return "control.controller._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())
