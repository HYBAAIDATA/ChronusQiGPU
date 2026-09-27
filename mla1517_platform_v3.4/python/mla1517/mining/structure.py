"""Phi-structure score for a candidate window.

s is in [0, 1]. The headless chooser treats s >= 1/phi as a structured
M32 lane and anything below that as flat exhaustive search.

This is an ordering signal only. It does not change the SHA256d target
check and it is not a Yang-Mills mass gap.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

PHI: float = (1.0 + math.sqrt(5.0)) / 2.0
INV_PHI: float = 1.0 / PHI


class PhiStructureAnalyzer:
    """Quantify phi-structure in a set of integers."""

    def __init__(self) -> None:
        self.phi = PHI
        self.inv_phi = INV_PHI
        self.phi15 = PHI**15

    def _uniformity_bias(self, values: Iterable[float]) -> float:
        vals = sorted(float(v) % 1.0 for v in values)
        n = len(vals)
        if n == 0:
            return 0.0
        dev = 0.0
        for i, v in enumerate(vals):
            dev += abs(v - (i + 0.5) / n)
        return min(1.0, dev / (n * 0.5))

    def compute_structure_parameter(
        self, problem_instance: Iterable[int], search_space=None
    ) -> float:
        values = [int(v) for v in problem_instance]
        if not values:
            return 0.0
        weyl = [(v * self.phi) % 1.0 for v in values]
        weyl_dev = self._uniformity_bias(weyl)
        pisot = [(v / self.phi15) % 1.0 for v in values]
        pisot_dev = self._uniformity_bias(pisot)
        ordered = sorted(values)
        steps = [(ordered[i + 1] - ordered[i]) % (2**32) for i in range(len(ordered) - 1)]
        step_frac = [(step * self.inv_phi) % 1.0 for step in steps] if steps else [0.0]
        step_dev = self._uniformity_bias(step_frac)
        return min(1.0, (weyl_dev * 0.4 + pisot_dev * 0.35 + step_dev * 0.25) * 2.2)


def phi_structure_strength(values: Iterable[int]) -> float:
    return PhiStructureAnalyzer().compute_structure_parameter(values)
