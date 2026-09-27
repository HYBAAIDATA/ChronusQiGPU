"""Lucas 15 Attractor: the fixed point of the Poincare-Cassini ontology.

L_15 = 1364
phi^15 = 1364.000733...
Drift = 7.33 x 10^-4
Zeckendorf: 8 non-consecutive Fibonacci numbers
Cassini: F_14 * F_16 - F_15^2 = (-1)^15 = -1
"""

# LUCAS WIRING: declared substrate peer -- computes exact Fibonacci/Lucas
# invariants and scores values against the Lucas 15 attractor.
# Substrate route: lucas

from __future__ import annotations

import math
from typing import Any, Dict, List


PHI = (1.0 + math.sqrt(5.0)) / 2.0
PHI_INV = 1.0 / PHI


class LucasAttractor:
    """Lucas 15 as the attractor of the Poincare-Cassini ontology."""

    def __init__(self, n: int = 15) -> None:
        self.n = int(n)
        self.L_n = self._lucas(self.n)
        self.phi_n = float(PHI**self.n)
        self.drift = abs(self.phi_n - self.L_n)
        self.zeckendorf = self._zeckendorf(self.L_n)
        self.cassini = self._cassini(self.n)

    @staticmethod
    def _lucas(n: int) -> int:
        if n == 0:
            return 2
        if n == 1:
            return 1
        a, b = 2, 1
        for _ in range(n - 1):
            a, b = b, a + b
        return b

    @staticmethod
    def _fib(n: int) -> int:
        if n <= 0:
            return 0
        if n == 1:
            return 1
        a, b = 0, 1
        for _ in range(n - 1):
            a, b = b, a + b
        return b

    def _zeckendorf(self, n: int) -> List[int]:
        """Compute canonical Zeckendorf decomposition (greedy descending)."""
        target = int(abs(n))
        if target == 0:
            return []
        fibs = [1, 2]
        while fibs[-1] < target:
            fibs.append(fibs[-1] + fibs[-2])
        result = []
        for f in reversed(fibs):
            if f <= target:
                result.append(f)
                target -= f
        return result

    def _cassini(self, n: int) -> int:
        """Cassini identity: F_{n-1} * F_{n+1} - F_n^2 = (-1)^n."""
        return self._fib(n - 1) * self._fib(n + 1) - self._fib(n) ** 2

    def attractor_score(self, value: float) -> float:
        """Higher score = closer to Lucas 15 resonance. Range: (0, 1]."""
        distance = abs(float(value) - self.L_n)
        normalized = distance / max(self.drift, 1e-15)
        return float(1.0 / (1.0 + normalized))

    def zeckendorf_score(self, value: int) -> float:
        """Higher score = closer to L_15 Zeckendorf term count. Range: (0, 1]."""
        zeck = self._zeckendorf(int(value))
        target_len = len(self.zeckendorf)
        return float(1.0 / (1.0 + abs(len(zeck) - target_len)))

    def phi_resonance(self, value: float) -> float:
        """Higher score = closer to golden ratio power resonance. Range: [0, 1]."""
        v = abs(float(value))
        if self.phi_n <= 0.0:
            return 0.0
        ratio = v / self.phi_n
        return float(max(0.0, 1.0 - abs(ratio - 1.0)))

    def total_score(self, value: float) -> float:
        """Combined harmonic attractor score in [0.0, 1.0]."""
        v = float(value)
        return (
            self.attractor_score(v) + self.zeckendorf_score(int(round(v))) + self.phi_resonance(v)
        ) / 3.0

    def state(self) -> Dict[str, Any]:
        """Return diagnostic state dictionary."""
        return {
            "n": self.n,
            "L_n": self.L_n,
            "phi_n": self.phi_n,
            "drift": self.drift,
            "zeckendorf": list(self.zeckendorf),
            "cassini": self.cassini,
            "theorem_proven": False,
        }


__all__ = ["PHI", "PHI_INV", "LucasAttractor"]
