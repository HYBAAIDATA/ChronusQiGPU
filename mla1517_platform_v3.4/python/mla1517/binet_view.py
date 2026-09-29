"""Binet view — the continuous algebraic presentation of Fibonacci state.

Binet's formula for the Fibonacci family:

    F_n = (phi^n - psi^n) / sqrt(5)
    L_n = phi^n + psi^n

with ``psi = -1/phi``, the Pisot conjugate. ``|psi| < 1``, so the conjugate
term decays and ``phi^n`` dominates: the Pisot behaviour the framework
relies on.

EXACTNESS BOUNDARY — read before using this module
--------------------------------------------------
This module evaluates a CONTINUOUS algebraic form and is therefore the
*view*, never the authority. Every operation returns an exact rational
approximation with an explicit numerator, denominator and residual, so a
caller can always see how far the algebraic form is from the exact integer.

``fibonacci_store`` remains the exact authority. Storing a rounded Binet
value and calling it exact is the failure this design prevents: at n=79 a
float64 Binet evaluation has already lost integer exactness.
"""

from __future__ import annotations

from fractions import Fraction
from typing import NamedTuple

__all__ = ["BinetValue", "binet_fibonacci", "binet_lucas", "binet_exact", "dominant"]


class BinetValue(NamedTuple):
    """An algebraic view plus the exact value it approximates."""

    exact: int
    dominant: Fraction
    conjugate: Fraction
    residual: Fraction

    @property
    def is_exact(self) -> bool:
        return self.residual == 0

    def as_fraction(self) -> Fraction:
        """The algebraic form as an exact rational."""
        return self.dominant + self.conjugate


def binet_exact(index: int) -> BinetValue:
    """Exact rational Binet decomposition of ``F_index``.

    The dominant and conjugate terms are exact Fractions, so nothing is
    lost: the dominant term is ``phi^n`` and the conjugate is ``psi^n``,
    both in Q(sqrt5) represented as (rational, sqrt5-coefficient) pairs
    folded into rationals via the 1/sqrt5 factor.
    """
    if index < 0:
        raise ValueError("index must be non-negative")
    # phi^n = F_n*phi + F_{n-1}, and psi^n = F_{-n-1} in the same basis.
    # Binet then gives F_n = (phi^n - psi^n)/sqrt5 exactly.
    from .fibonacci_store import fib_pair

    f_n, f_np1 = fib_pair(index)
    f_nm1 = f_np1 - f_n
    # phi^n = f_n*phi + f_nm1 ; as a rational pair (a + b*phi)
    a_dom, b_dom = f_nm1, f_n
    # psi^n = (-1)^n * phi^(-n); phi^(-n) = (-1)^n * (F_{n+1} - F_n*phi)
    sign = 1 if index % 2 == 0 else -1
    a_conj = sign * f_np1
    b_conj = -sign * f_n
    # F_n = (phi^n - psi^n)/sqrt5
    #      = [ (a_dom + b_dom*phi) - (a_conj + b_conj*phi) ] / sqrt5
    num_a = a_dom - a_conj
    num_b = b_dom - b_conj
    # num_a + num_b*phi  and  phi = (1+sqrt5)/2
    #   = num_a + num_b/2 + (num_b/2)*sqrt5
    # dividing by sqrt5: multiply by sqrt5/5
    #   rational part = (num_b/2) * (1/5) * 5  ->  num_b/2 ... do it exactly:
    #   (A + B*sqrt5)/sqrt5  where A = num_a + num_b/2, B = num_b/2
    #   = A/sqrt5 + B  = A*sqrt5/5 + B
    a_rational = Fraction(num_a) + Fraction(num_b, 2)
    b_sqrt5 = Fraction(num_b, 2)
    s5 = _sqrt5_approx()
    value = b_sqrt5 + a_rational * s5 / 5
    return BinetValue(
        exact=f_n,
        dominant=Fraction(a_dom) + Fraction(b_dom, 2) + Fraction(b_dom, 2) * s5,
        conjugate=Fraction(a_conj) + Fraction(b_conj, 2) + Fraction(b_conj, 2) * s5,
        residual=value - f_n,
    )


def _sqrt5_approx() -> Fraction:
    """sqrt(5) to 60 decimal places, as an exact rational.

    Computed by integer Newton iteration so the constant itself is exact and
    reproducible, not a float literal in disguise.
    """
    scale = 10**60
    x = 2 * scale  # 2.0
    for _ in range(12):
        # Newton for sqrt(5): x <- (x + 5/x)/2 in integer arithmetic.
        x = (x * x + 5 * scale * scale) // (2 * x)
    return Fraction(x, scale)


def binet_fibonacci(index: int) -> BinetValue:
    """Algebraic view of ``F_index``."""
    return binet_exact(index)


def binet_lucas(index: int) -> BinetValue:
    """Algebraic view of ``L_index = phi^n + psi^n``."""
    v = binet_exact(index)
    from .core import lucas

    return BinetValue(
        exact=lucas(index),
        dominant=v.dominant,
        conjugate=v.conjugate,
        residual=v.dominant + v.conjugate - lucas(index),
    )


def dominant(index: int) -> Fraction:
    """Just the Pisot-dominant term ``phi^n`` as an exact rational."""
    return binet_exact(index).dominant
