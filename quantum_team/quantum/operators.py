"""Postulate 3: every change of state is a unitary U, U†U = I.

Matrix-free by construction: phase application is elementwise (O(N)),
diffusion is a rank-1 reflection (O(N)). No N×N dense operator is ever
materialized at runtime; dense twins exist only for exact unitarity
verification in the test suite.

Fitness enters as PHASE only. Probability mass moves exclusively
through interference in the diffusion step: amplitudes in phase with
the mean are reinforced, anti-phase amplitudes are cancelled.
"""

from __future__ import annotations

import numpy as np

from .state import State


def apply_phase(state: State, fitness: np.ndarray) -> State:
    """U_f = diag(exp(i·pi·f_i)), f_i in [0,1]. |c_i| untouched:
    norm preservation is exact, not approximate."""
    f = np.asarray(fitness, dtype=float)
    if f.min() < 0 or f.max() > 1:
        raise ValueError("fitness must be pre-normalized to [0, 1]")
    out = state.copy()
    out.amps = out.amps * np.exp(1j * np.pi * f)
    return out


def apply_diffusion(state: State) -> State:
    """D = 2|s><s| - I, |s> = uniform. Matrix-free action:
    D psi = 2·mean(psi)·1 - psi.  O(N) time, O(1) extra memory.
    (D|s> = |s>, D|s^perp> = -|s^perp>: an exact reflection about
    the population mean, hence unitary.)"""
    out = state.copy()
    out.amps = 2.0 * out.amps.mean() - out.amps
    return out


def dense_phase(fitness: np.ndarray) -> np.ndarray:
    """Dense U_f for unitarity verification in tests only."""
    return np.diag(np.exp(1j * np.pi * np.asarray(fitness, dtype=float)))


def dense_diffusion(n: int) -> np.ndarray:
    """Dense D for unitarity verification in tests only."""
    s = np.full(n, 1.0 / np.sqrt(n), dtype=complex)
    return 2.0 * np.outer(s, s) - np.eye(n)
