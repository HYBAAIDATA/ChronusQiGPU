"""φ is Pisot: φ > 1 and |ψ| < 1. Substitution matrix is R."""

from __future__ import annotations

import math
from typing import List, Tuple

from phi_rotation.rotation import R

PHI = (1 + math.sqrt(5)) / 2
PSI = (1 - math.sqrt(5)) / 2


def is_pisot_phi() -> bool:
    return PHI > 1.0 and abs(PSI) < 1.0


def pisot_substitution(t: Tuple[float, float]) -> Tuple[float, float]:
    return R.apply(*t)


def pisot_wind(seed: Tuple[float, float], steps: int) -> List[Tuple[float, float]]:
    orbit = [seed]
    cur = seed
    for _ in range(steps):
        cur = pisot_substitution(cur)
        orbit.append(cur)
    return orbit


def fibonacci_word(n: int) -> str:
    w = "0"
    for _ in range(n):
        w = w.replace("1", "x").replace("0", "01").replace("x", "0")
    return w
