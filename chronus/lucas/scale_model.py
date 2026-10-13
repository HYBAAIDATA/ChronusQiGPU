"""Lucas scale model — capacity ≡ precision.

Naming the rung names the state. log2(L_n) = n * log2(phi) to machine
precision on the declared ladder. This is a scale model, not an assignment
rule and not a budget convention.

theorem_proven: False
"""

from __future__ import annotations

import math
from typing import Final

from .core import lucas

PHI: Final[float] = (1 + math.sqrt(5)) / 2
LOG2_PHI: Final[float] = math.log2(PHI)

DECLARED_RUNGS: Final[tuple[int, ...]] = (10, 12, 15, 18, 20, 31, 50, 76)

# 0x9E3779B9 = 3^2 * 7 * 11 * 17 * 331 * 359
GOLDEN_STRIDE: Final[int] = 0x9E3779B9
STRIDE_FACTORS: Final[tuple[int, ...]] = (3, 3, 7, 11, 17, 331, 359)


def capacity_bits(n: int) -> float:
    """log2(L_n). Equals n * log2(phi) to machine precision on the ladder."""
    return math.log2(lucas(n))


def scale_ratio(n: int) -> float:
    """capacity_bits(n) / (n * log2(phi)). Converges to 1."""
    return capacity_bits(n) / (n * LOG2_PHI)


def stride_is_bijective(device_count: int) -> bool:
    """True iff gcd(GOLDEN_STRIDE, device_count) == 1.

    Parity is a special case. D=9 (odd) fails because it shares the factor 3.
    """
    from math import gcd
    return gcd(GOLDEN_STRIDE, device_count) == 1


def assert_stride_bijective(device_count: int) -> None:
    if not stride_is_bijective(device_count):
        raise ValueError(
            f"golden stride is not bijective over {device_count} devices; "
            f"gcd(0x9E3779B9, {device_count}) != 1"
        )
