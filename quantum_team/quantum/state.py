"""Postulates 1 and 2 only.

1. A state is a unit vector in C^N over N candidate outcomes.
2. Measurement probability of outcome i is |<i|psi>|^2 (Born rule).

This module contains the ONLY nonlinearity in the entire system:
the squaring in probs(). Everything else in the package is linear
algebra on amplitudes.
"""

from __future__ import annotations

import numpy as np


class State:
    __slots__ = ("amps",)

    def __init__(self, n_or_amps: "int | np.ndarray"):
        if isinstance(n_or_amps, int):
            a = np.zeros(n_or_amps, dtype=complex)
            a[0] = 1.0                       # definite initial outcome
            self.amps = a
        else:
            self.amps = np.asarray(n_or_amps, dtype=complex)

    @staticmethod
    def uniform(n: int) -> "State":
        """Maximal-entropy state given no prior information."""
        return State(np.full(n, 1.0 / np.sqrt(n), dtype=complex))

    def normalize(self) -> "State":
        norm = np.linalg.norm(self.amps)
        if norm == 0:
            raise ZeroDivisionError("null state: all amplitude annihilated")
        self.amps = self.amps / norm
        return self

    def probs(self) -> np.ndarray:
        """Born rule: P(i) = |c_i|^2. The only place amplitudes become
        probabilities. Not a heuristic — it is the measurement postulate."""
        return np.abs(self.amps) ** 2

    def measure(self, rng: "np.random.Generator | None" = None) -> int:
        """Collapse: sample one outcome from the Born distribution."""
        rng = rng or np.random.default_rng()
        return int(rng.choice(len(self.amps), p=self.probs()))

    def copy(self) -> "State":
        return State(self.amps.copy())

    def __len__(self) -> int:
        return len(self.amps)
