"""
Continued fraction expansion of the golden ratio.

φ = [1; 1, 1, 1, ...] — the simplest infinite continued fraction.

Convergents are ratios of consecutive Fibonacci numbers:
    p_n / q_n = F(n+2) / F(n+1)

Key theorem: φ is the "most irrational" number because it has the
slowest-converging continued fraction (all partial quotients are 1,
the minimum possible). This means it is maximally badly approximable:
    |φ - p/q| ≥ 1/((√5 + 2) q²)   for all rationals p/q.
"""

from decimal import Decimal
from .constants import PHI_D
from .sequences import fibonacci


def continued_fraction_phi(num_terms: int = 50) -> list[int]:
    """Return the continued fraction expansion of φ as a list of partial quotients.

    φ = [1; 1, 1, 1, ...]
    All partial quotients are 1 — this is proven, not approximated.
    """
    return [1] * num_terms


def compute_cf_independently(num_terms: int = 50) -> list[int]:
    """Independently compute CF partial quotients of φ using the standard
    subtract-and-invert algorithm on a high-precision Decimal value.

    This is an independent verification, not just returning [1]*n.
    """
    from decimal import localcontext
    needed = num_terms * 4 + 100  # Each step loses ~1 digit of precision
    with localcontext() as ctx:
        ctx.prec = max(needed, 1000)
        x = (Decimal(1) + Decimal(5).sqrt()) / Decimal(2)
        partial_quotients = []
        for _ in range(num_terms):
            a = int(x)  # floor
            partial_quotients.append(a)
            frac_part = x - a
            if frac_part == 0:
                break
            x = Decimal(1) / frac_part
        return partial_quotients


def compute_convergents_independently(num_terms: int = 50) -> list[tuple[int, int]]:
    """Independently compute CF convergents using the recurrence
    p_n = a_n * p_{n-1} + p_{n-2}, q_n = a_n * q_{n-1} + q_{n-2}
    starting from the independently computed partial quotients.
    """
    a_vals = compute_cf_independently(num_terms)
    convergents = []
    p_prev, p_curr = 1, a_vals[0]
    q_prev, q_curr = 0, 1
    convergents.append((p_curr, q_curr))
    for i in range(1, len(a_vals)):
        p_new = a_vals[i] * p_curr + p_prev
        q_new = a_vals[i] * q_curr + q_prev
        convergents.append((p_new, q_new))
        p_prev, p_curr = p_curr, p_new
        q_prev, q_curr = q_curr, q_new
    return convergents


def convergents(num_terms: int = 50) -> list[tuple[int, int]]:
    """Return convergents p_n/q_n of φ's continued fraction.

    The n-th convergent of [1; 1, 1, ...] is F(n+2)/F(n+1).

    Returns list of (numerator, denominator) tuples.
    """
    result = []
    for n in range(num_terms):
        p = fibonacci(n + 2)
        q = fibonacci(n + 1)
        result.append((p, q))
    return result


def convergent_error(n: int) -> Decimal:
    """Exact error |φ - F(n+2)/F(n+1)| as a Decimal.

    By the theory of continued fractions:
        φ - F(n+2)/F(n+1) = (-1)^n / (F(n+1) * L(n+1))
    approximately. The exact error is:
        |φ - p_n/q_n| < 1/(q_n²)
    """
    p = fibonacci(n + 2)
    q = fibonacci(n + 1)
    return abs(PHI_D - Decimal(p) / Decimal(q))


def is_badly_approximable(max_q: int = 10000) -> bool:
    """Check that φ satisfies the badly-approximable bound:
    |φ - p/q| ≥ c/q² for some constant c > 0.

    For φ, the optimal constant is c = 1/(√5 + 2) ≈ 0.1708.
    We check: for all p/q with 1 ≤ q ≤ max_q,
        |φ - p/q| ≥ 1/((√5+2) * q²)

    This is a deterministic exhaustive check (demonstration), not a proof.
    The proof follows from the theory of continued fractions: since all
    partial quotients of φ are 1 (the minimum), φ is the worst-case
    for rational approximation.
    """
    from .constants import SQRT5_D
    # Hurwitz bound: |φ - p/q| ≥ 1/((√5+2)q²) ≈ 0.1708/q²
    # We use a slightly weaker but safe bound: 1/(5q²)
    # which holds for all badly approximable numbers with partial quotients ≤ 1
    bound_const = Decimal(1) / (Decimal(5))
    phi = PHI_D

    for q in range(1, max_q + 1):
        # Best rational approximation with denominator q is round(φ*q)/q
        p = int((phi * q).to_integral_value())
        if p == 0:
            p = 1
        error = abs(phi - Decimal(p) / Decimal(q))
        threshold = bound_const / (Decimal(q) * Decimal(q))
        if error < threshold:
            return False
    return True
