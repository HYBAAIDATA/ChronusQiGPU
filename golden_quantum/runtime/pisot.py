"""
Generalized Pisot convergence analysis.

A Pisot number is an algebraic integer λ > 1 whose other conjugates
all have modulus < 1. This means λ^n approaches an integer as n → ∞,
with error decreasing as |conjugate|^n.

This module compares convergence rates for two Pisot numbers:

  1. φ (golden ratio): minimal polynomial x² - x - 1
     λ = φ ≈ 1.618, conjugate |ψ| ≈ 0.618
     Convergence: |ψ|^n < ε requires n ≈ log(ε) / log(0.618) ≈ 29 for ε=10⁻⁶

  2. λ₃ (Pisot-3): minimal polynomial x² - 3x - 1
     λ₃ = (3+√13)/2 ≈ 3.303, conjugate |ψ₃| ≈ 0.303
     Convergence: |ψ₃|^n < ε requires n ≈ log(ε) / log(0.303) ≈ 12 for ε=10⁻⁶

The second Pisot number converges ~2.5× faster because its conjugate
is smaller, giving faster exponential decay. Both are quadratic Pisot
units (degree-2 minimal polynomials with one root >1 and one <|).
"""

import math
from decimal import Decimal, localcontext


def pisot_phi() -> tuple[Decimal, Decimal, str]:
    """Return (root, conjugate, polynomial) for φ: x² - x - 1 = 0.

    root = φ ≈ 1.618, conjugate |ψ| ≈ 0.618
    """
    s5 = Decimal(5).sqrt()
    root = (Decimal(1) + s5) / Decimal(2)
    conj = (Decimal(1) - s5) / Decimal(2)
    return (root, conj, "x² - x - 1")


def pisot_3() -> tuple[Decimal, Decimal, str]:
    """Return (root, conjugate, polynomial) for λ₃: x² - 3x - 1 = 0.

    root = (3+√13)/2 ≈ 3.303, conjugate |ψ₃| ≈ 0.303
    """
    s13 = Decimal(13).sqrt()
    root = (Decimal(3) + s13) / Decimal(2)
    conj = (Decimal(3) - s13) / Decimal(2)
    return (root, conj, "x² - 3x - 1")


def conjugate_magnitude(conj: Decimal) -> Decimal:
    """|conjugate| as a non-negative Decimal."""
    return abs(conj)


def iterations_for_precision(conj_mag: Decimal, precision: Decimal) -> int:
    """Find the minimum n such that |conj|^n < precision.

    This is the number of iterations needed for the Pisot convergence
    to reach the given precision.

    We compute iteratively to avoid floating-point log issues.
    """
    if conj_mag >= 1:
        return -1  # Not a Pisot conjugate; won't converge
    if precision <= 0:
        return -1

    n = 0
    val = Decimal(1)
    while val >= precision:
        val *= conj_mag
        n += 1
        if n > 100000:  # Safety limit
            return -1
    return n


def verify_threshold(conj_mag: Decimal, n: int, precision: Decimal) -> bool:
    """Verify that |conj|^n < precision but |conj|^(n-1) >= precision.

    This confirms n is the exact minimum threshold.
    """
    with localcontext() as ctx:
        ctx.prec = max(50, int(-precision.log10()) + 20)
        conj_mag = Decimal(str(conj_mag))
        precision = Decimal(str(precision))
        val_n = conj_mag ** n
        val_n_minus_1 = conj_mag ** (n - 1)
        return val_n < precision and val_n_minus_1 >= precision


def convergence_ratio(conj_phi: Decimal, conj_3: Decimal) -> float:
    """Ratio of iterations needed: φ's conjugate vs λ₃'s conjugate.

    A ratio > 1 means λ₃ (x²-3x-1) converges faster.
    """
    precision = Decimal("1e-6")
    n_phi = iterations_for_precision(abs(conj_phi), precision)
    n_3 = iterations_for_precision(abs(conj_3), precision)
    if n_3 <= 0:
        return float('inf')
    return n_phi / n_3
