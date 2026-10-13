"""
Comparison helpers for the sampling family.
Compares approximability of φ vs other irrationals.
"""

from decimal import Decimal
from ..constants import PHI_D, SQRT5_D


def best_approximation_quality(alpha: Decimal, max_q: int = 1000) -> float:
    """Find min over p/q of q² · |α - p/q|.

    A higher value means the number is harder to approximate (more irrational).
    """
    best = float('inf')
    for q in range(1, max_q + 1):
        # Best p is the nearest integer to alpha*q
        p = int((alpha * q).to_integral_value())
        if p == 0:
            p = 1
        error = abs(float(alpha) - p / q)
        quality = q * q * error
        if quality < best:
            best = quality
    return best


def compare_approximability(max_q: int = 1000) -> tuple[float, float, float, float]:
    """Compare approximation quality of φ, √2, π, and √5.

    Returns (phi_quality, sqrt2_quality, pi_quality, sqrt5_quality) where higher = more irrational.
    """
    phi_q = best_approximation_quality(PHI_D, max_q)
    sqrt2_q = best_approximation_quality(Decimal(2).sqrt(), max_q)
    sqrt5_q = best_approximation_quality(SQRT5_D, max_q)

    # π as Decimal (computed to high precision)
    from ..constants import getcontext
    pi_d = Decimal(0)
    # Use math.pi and convert
    import math
    pi_d = Decimal(str(math.pi))

    pi_q = best_approximation_quality(pi_d, max_q)

    return (phi_q, sqrt2_q, pi_q, sqrt5_q)
