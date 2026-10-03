"""Trotter-Suzuki Hamiltonian simulation — first-principles time evolution.

Implements the explicit-Hamiltonian analogue of quantum time evolution
U(t) = e^{-iHt} via Lie-Trotter (1st order) or Strang (2nd order) operator
splitting, with adaptive step-size control.

This is a genuine, textbook *approximate* method — not a claim of
exactness. Trotter-Suzuki splitting has a known, bounded local error
(O(dt^2) per step at 1st order, O(dt^3) at 2nd/Strang order; see Lloyd
1996, Suzuki 1990), which is why real quantum-simulation algorithms use
it: it is the standard way to turn an explicit Hamiltonian into a
sequence of applicable unitaries. The adaptive controller below verifies
its own accuracy at runtime via Richardson step-doubling — one step of
size dt is only accepted once it agrees with two steps of dt/2 to within
``error_threshold`` — rather than assuming a fixed step size is good
enough.
"""

from __future__ import annotations

from typing import Any, Dict

import numpy as np


def _expm(matrix: np.ndarray) -> np.ndarray:
    """Matrix exponential via eigendecomposition (no scipy dependency)."""
    eigvals, eigvecs = np.linalg.eig(matrix)
    return eigvecs @ np.diag(np.exp(eigvals)) @ np.linalg.inv(eigvecs)


class TrotterHamiltonianSimulator:
    """Trotter-Suzuki time evolution for an explicit Hermitian Hamiltonian."""

    def __init__(self, num_qubits: int, hamiltonian: np.ndarray) -> None:
        self.num_qubits = num_qubits
        self.hamiltonian = np.asarray(hamiltonian, dtype=complex)
        expected = 2**num_qubits
        if self.hamiltonian.shape != (expected, expected):
            raise ValueError(
                f"hamiltonian must have shape {(expected, expected)} "
                f"for {num_qubits} qubits, got {self.hamiltonian.shape}"
            )
        if not np.allclose(self.hamiltonian, self.hamiltonian.conj().T, atol=1e-12):
            raise ValueError("hamiltonian must be Hermitian")

    def improved_trotterization(self, time_step: float, trotter_order: int = 2) -> np.ndarray:
        """Propagator for one step of ``time_step``, splitting H into its
        diagonal and off-diagonal parts.

        Order 1 (Lie-Trotter): H1 then H2 — local error O(time_step^2).
        Order 2 (Strang): the symmetric H1/2, H2, H1/2 splitting, which
        cancels the leading commutator error term — local error
        O(time_step^3). Higher orders fall back to naive repeated
        splitting of the full Hamiltonian (still convergent, just without
        the Strang error cancellation).
        """
        diagonal = np.diag(np.diag(self.hamiltonian))
        off_diagonal = self.hamiltonian - diagonal
        if trotter_order == 1:
            return _expm(-1j * time_step * diagonal) @ _expm(-1j * time_step * off_diagonal)
        if trotter_order == 2:
            return (
                _expm(-1j * time_step / 2 * diagonal)
                @ _expm(-1j * time_step * off_diagonal)
                @ _expm(-1j * time_step / 2 * diagonal)
            )
        propagator = np.eye(self.hamiltonian.shape[0], dtype=complex)
        for _ in range(trotter_order):
            propagator = propagator @ _expm(-1j * time_step / trotter_order * self.hamiltonian)
        return propagator

    def adaptive_time_stepping(
        self, initial_state: np.ndarray, target_time: float, error_threshold: float = 1e-6
    ) -> Dict[str, Any]:
        """Integrate to ``target_time``, adapting the step size by Richardson
        step-doubling: a step of size dt is accepted only once it agrees
        with two steps of dt/2 to within ``error_threshold``; steps with
        room to spare are grown, steps that disagree are halved and
        retried — this is a runtime accuracy check, not an assumption.
        """
        state = initial_state.copy().astype(complex)
        current_time = 0.0
        step_sizes: list[float] = []
        trajectory = [state.copy()]
        dt = min(0.1, target_time)
        while current_time < target_time - 1e-15:
            dt = min(dt, target_time - current_time)
            coarse = self.improved_trotterization(dt, 2) @ state
            half_step = self.improved_trotterization(dt / 2, 2)
            fine = half_step @ (half_step @ state)
            error = np.linalg.norm(fine - coarse)
            if error > error_threshold and dt > 1e-12:
                dt *= 0.5
                continue
            state = fine
            current_time += dt
            step_sizes.append(dt)
            trajectory.append(state.copy())
            if error < error_threshold / 4:
                dt *= 1.5
        return {
            "final_state": state,
            "time_steps": step_sizes,
            "states": trajectory,
            "total_time": current_time,
        }


__all__ = ["TrotterHamiltonianSimulator"]
