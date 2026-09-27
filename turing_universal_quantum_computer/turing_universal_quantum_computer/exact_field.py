"""Field-only helpers for TOE's exact scalar field.

The square-root operation intentionally lives here, outside the training
pipeline. It is available for algebra tests and explicit field proofs; the
TOE training path uses center-only or range preprocessing and never calls it.
"""

from __future__ import annotations

import math
from fractions import Fraction

from .exact_tensor import F4


def _q_sqrt(value: Fraction) -> Fraction | None:
    if value < 0:
        return None
    numerator = math.isqrt(value.numerator)
    denominator = math.isqrt(value.denominator)
    if numerator * numerator == value.numerator and denominator * denominator == value.denominator:
        return Fraction(numerator, denominator)
    return None


def sqrt_f(value: F4) -> F4:
    """Exact square root when the result is representable in F4."""
    if value.c != 0 or value.d != 0 or value.real.sign() < 0:
        raise ValueError("value is not a non-negative real square in F4")
    rational_root = _q_sqrt(value.real.a) if value.real.b == 0 else None
    if rational_root is not None:
        return F4(rational_root)
    scaled_root = _q_sqrt(value.real.a / 2) if value.real.b == 0 else None
    if scaled_root is not None:
        return F4(0, scaled_root)
    raise ValueError("square root is not representable in Q(sqrt(2))")


__all__ = ["sqrt_f"]
