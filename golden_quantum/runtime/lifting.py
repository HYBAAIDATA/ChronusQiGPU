"""
Golden-angle 3-shear integer lifting transform.

A reversible integer-to-integer wavelet using 3 shear operations
parameterized by golden-angle trigonometric coefficients:

    θ = 2π(1 - 1/φ)   (golden angle)

    Shear 1: x' = x + round(y · cos(θ))
    Shear 2: y' = y + round(x' · sin(θ))
    Shear 3: x'' = x' + round(y' · cos(θ))

The inverse reverses the shears in opposite order.

IMPORTANT: This is an integer lifting scheme. It is exactly reversible
ONLY when inputs are integers. Float inputs will accumulate rounding
errors and should be rejected.
"""

import math
from typing import Tuple

PHI = (1 + math.sqrt(5)) / 2
GOLDEN_ANGLE = 2 * math.pi * (1 - 1 / PHI)
COS_GA = math.cos(GOLDEN_ANGLE)
SIN_GA = math.sin(GOLDEN_ANGLE)


def _round_half_up(x: float) -> int:
    """Deterministic rounding: round half away from zero.

    Python's built-in round() uses banker's rounding (round half to even),
    which can break reversibility. We use round-half-away-from-zero for
    consistent invertibility.
    """
    if x >= 0:
        return int(x + 0.5)
    else:
        return int(x - 0.5)


def lift(x: int, y: int) -> Tuple[int, int]:
    """Apply golden-angle 3-shear lifting to an integer pair.

    Args:
        x, y: Integer coordinates.

    Returns:
        (x', y') — lifted integer coordinates.

    Raises:
        TypeError: if x or y is not an integer.
    """
    if not isinstance(x, int) or not isinstance(y, int):
        raise TypeError(
            f"Golden-angle lifting requires integer inputs, got ({type(x).__name__}, {type(y).__name__})"
        )

    # Shear 1: x' = x + round(y * cos(θ))
    x1 = x + _round_half_up(y * COS_GA)

    # Shear 2: y' = y + round(x' * sin(θ))
    y1 = y + _round_half_up(x1 * SIN_GA)

    # Shear 3: x'' = x' + round(y' * cos(θ))
    x2 = x1 + _round_half_up(y1 * COS_GA)

    return (x2, y1)


def unlift(x: int, y: int) -> Tuple[int, int]:
    """Inverse golden-angle 3-shear lifting.

    Reverses the shears in opposite order.

    Args:
        x, y: Lifted integer coordinates.

    Returns:
        (x_orig, y_orig) — original integer coordinates.

    Raises:
        TypeError: if x or y is not an integer.
    """
    if not isinstance(x, int) or not isinstance(y, int):
        raise TypeError(
            f"Golden-angle unlifting requires integer inputs, got ({type(x).__name__}, {type(y).__name__})"
        )

    # Undo Shear 3: x' = x - round(y * cos(θ))
    x1 = x - _round_half_up(y * COS_GA)

    # Undo Shear 2: y_orig = y - round(x' * sin(θ))
    y0 = y - _round_half_up(x1 * SIN_GA)

    # Undo Shear 1: x_orig = x' - round(y_orig * cos(θ))
    x0 = x1 - _round_half_up(y0 * COS_GA)

    return (x0, y0)


def lift_roundtrip(x: int, y: int) -> bool:
    """Verify that unlift(lift(x, y)) == (x, y)."""
    lifted = lift(x, y)
    unlifted = unlift(*lifted)
    return unlifted == (x, y)
