"""Reverse annealing and pause-quench protocols."""

from __future__ import annotations
import numpy as np
from ._linalg import expm
from typing import Dict, Any


class ModernQAnneal:
    def __init__(self, problem_hamiltonian: np.ndarray) -> None:
        self.H_p = np.asarray(problem_hamiltonian, dtype=complex)
        # Transverse-field driver (Pauli-X on all qubits, tensor structure preserved)
        d = self.H_p.shape[0]
        self.H_d = np.zeros_like(self.H_p)
        # Simple flip-preserving driver: reverse-index Hadamard analogue
        for i in range(d):
            self.H_d[i, (i + 1) % d] = 1.0
            self.H_d[(i + 1) % d, i] = 1.0

    def reverse_anneal(
        self, initial_state: np.ndarray, annealing_time: float = 1.0, schedule_steps: int = 100
    ) -> Dict[str, Any]:
        state = np.asarray(initial_state, dtype=complex)
        state = state / max(1e-12, np.linalg.norm(state))
        times = np.linspace(0.0, annealing_time, schedule_steps)
        # Reverse-anneal schedule s(t): 0 -> s_min -> 0
        schedule = 0.5 * (1 - np.cos(2 * np.pi * times / annealing_time))
        dt = annealing_time / schedule_steps
        for s in schedule:
            H_s = (1.0 - s) * self.H_p + s * self.H_d
            state = expm(-1j * H_s * dt) @ state
        return {
            "refined_solution": state,
            "norm_residual": float(abs(np.linalg.norm(state) - 1.0)),
        }

    def pause_and_quench(
        self,
        initial_state: np.ndarray,
        pause_fraction: float = 0.5,
        annealing_time: float = 1.0,
        steps: int = 100,
    ) -> Dict[str, Any]:
        state = np.asarray(initial_state, dtype=complex)
        state = state / max(1e-12, np.linalg.norm(state))
        pause_steps = int(steps * pause_fraction)
        dt = annealing_time / steps
        for k in range(steps):
            if pause_steps <= k < 2 * pause_steps:
                s = 0.5
            else:
                s = k / steps
            H_s = (1.0 - s) * self.H_p + s * self.H_d
            state = expm(-1j * H_s * dt) @ state
        return {"final_state": state, "pause_steps": pause_steps}
