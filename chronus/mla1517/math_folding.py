"""Chronus compatibility surface for substrate-neutral exact golden algebra.

This module intentionally exposes Fibonacci/Binet/Cassini/Zeckendorf and exact
Q(sqrt(5)) helpers that are mathematical primitives shared across domains.

It does **not** export ``PulviniFold`` or ``pulvini_fold``. PULVINI/phi-fold is
the data transformation authority and must be consumed through the canonical
data surfaces, not through a mining compatibility import.
"""

from python_backend.core_modules.math_folding import (
    PHI,
    PSI,
    SQRT5,
    PisotTruncation,
    Quadratic5,
    ZeckendorfAddress,
    below_pisot_threshold,
    fibonacci_binet,
    fibonacci_cassini,
    lucas_binet,
    lucas_cassini,
    pisot_threshold,
    truncate_pisot,
    verify_cassini,
    zeckendorf_address,
)

__all__ = [
    "PHI",
    "PSI",
    "SQRT5",
    "Quadratic5",
    "fibonacci_binet",
    "lucas_binet",
    "fibonacci_cassini",
    "lucas_cassini",
    "verify_cassini",
    "ZeckendorfAddress",
    "zeckendorf_address",
    "pisot_threshold",
    "below_pisot_threshold",
    "PisotTruncation",
    "truncate_pisot",
]
