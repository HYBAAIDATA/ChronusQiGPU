"""Base-φ expansion and Z-order interleave."""

from __future__ import annotations

import math
from typing import List, Tuple

PHI = (1 + math.sqrt(5)) / 2


def phi_expansion(x: float, precision: int) -> List[int]:
    digits: List[int] = []
    current = abs(x) % 1.0
    for _ in range(precision):
        current *= PHI
        digit = int(math.floor(current))
        if digit > 1:
            digit = 1
        digits.append(digit)
        current -= digit
    return digits


def morton_step(t: Tuple[float, float], precision: int) -> int:
    xd = phi_expansion(t[0], precision)
    yd = phi_expansion(t[1], precision)
    key = 0
    for i in range(precision):
        key = (key << 2) | ((xd[i] & 1) << 1) | (yd[i] & 1)
    return key
