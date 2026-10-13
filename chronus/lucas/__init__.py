"""Lucas Power Scaling pool — shared exact algebraic substrate."""

from __future__ import annotations

from .algebra import (
    ONE,
    PHI,
    ZERO,
    ZPhi,
    fibonacci as algebraic_fibonacci,
    lucas as algebraic_lucas,
    lucas_addition,
    lucas_matrix,
    lucas_subtraction,
    phi_power,
)
from .core import fibonacci, lucas, lucas_sequence
from .pool import available, get, register

__all__ = [
    "lucas",
    "fibonacci",
    "lucas_sequence",
    "get",
    "register",
    "available",
    "ONE",
    "PHI",
    "ZERO",
    "ZPhi",
    "algebraic_fibonacci",
    "algebraic_lucas",
    "lucas_addition",
    "lucas_matrix",
    "lucas_subtraction",
    "phi_power",
]

THEOREM_PROVEN = False

from .scale_model import capacity_bits, scale_ratio, stride_is_bijective, assert_stride_bijective
