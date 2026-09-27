"""Exact Fibonacci/Lucas arithmetic for the Aethel storage layer.

Two independent evaluation paths are provided on purpose:

* ``fibonacci`` / ``lucas`` — iterative fast-doubling recurrences.
* ``BinetIndex`` — Binet's closed form ``F_n = (phi^n - psi^n)/sqrt(5)``
  evaluated *exactly* in the quadratic field Q(sqrt(5)): phi^n is kept as
  ``(p + q*sqrt(5))/2`` with integer p, q, so ``F_n = q`` with zero
  floating-point drift at any index.

Contract B3 (closed-form == recursive, exact integer equality) is therefore
a real cross-check between two different algorithms, not a tautology.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import Optional, Tuple


# ---------------------------------------------------------------------------
# Recursive path (fast doubling)
# ---------------------------------------------------------------------------


def fibonacci(n: int) -> int:
    """F_n via exact fast doubling.

    Precondition: ``n >= 0``.  Postcondition: returns the exact n-th
    Fibonacci number with F_0 = 0, F_1 = 1.  Thread-safe (pure).
    """
    if n < 0:
        raise ValueError("fibonacci index must be non-negative")
    a, b = 0, 1
    for bit in range(n.bit_length() - 1, -1, -1):
        c = a * ((b << 1) - a)
        d = a * a + b * b
        if (n >> bit) & 1:
            a, b = d, c + d
        else:
            a, b = c, d
    return a


def lucas(n: int) -> int:
    """L_n via exact fast doubling.  L_0 = 2, L_1 = 1.  Pure."""
    if n < 0:
        raise ValueError("lucas index must be non-negative")
    if n == 0:
        return 2
    f_n = fibonacci(n)
    f_np1 = fibonacci(n + 1)
    return 2 * f_np1 - f_n


def _is_perfect_square(x: int) -> bool:
    if x < 0:
        return False
    r = math.isqrt(x)
    return r * r == x


def is_fibonacci(value: int) -> bool:
    """True iff ``value`` is a Fibonacci number.

    Uses the exact criterion: v is Fibonacci iff 5v^2 + 4 or 5v^2 - 4 is a
    perfect square.  Pure; thread-safe.
    """
    if value < 0:
        return False
    probe = 5 * value * value
    return _is_perfect_square(probe + 4) or _is_perfect_square(probe - 4)


def fibonacci_index(value: int) -> Optional[int]:
    """Return n with F_n = value, or None when value is not Fibonacci.

    Postcondition: if the result is not None, ``fibonacci(result) ==
    value``.  Exact for arbitrary precision integers.  Pure.
    """
    if value < 0 or not is_fibonacci(value):
        return None
    if value == 0:
        return 0
    if value == 1:
        return 1  # F_1 = F_2 = 1; canonical index is 1
    # Estimate n from Binet's leading term: n ~ log_phi(v * sqrt(5)).
    # The estimate is only used to seed a local scan; membership is exact.
    bit_len = value.bit_length()
    approx = bit_len / math.log2((1.0 + math.sqrt(5.0)) / 2.0)
    lo = max(1, int(approx) - 8)
    hi = int(approx) + 16
    n = lo
    f = fibonacci(n)
    while f < value and n < hi:
        n += 1
        f = fibonacci(n)
    while f > value and n > lo:
        n -= 1
        f = fibonacci(n)
    return n if f == value else None


# ---------------------------------------------------------------------------
# Cassini quadruples — the address-transition invariant
# ---------------------------------------------------------------------------


def cassini_quadruple(n: int) -> Tuple[int, int, int, int]:
    """Return (F_{n-1}, F_n, F_{n+1}, (-1)^n) for index n.

    Precondition: ``n >= 1`` (F_{n-1} must exist; the ledger starts at
    index 1).  Postcondition: the quadruple satisfies
    ``F_{n-1} * F_{n+1} - F_n^2 == (-1)^n``.  Pure.
    """
    if n < 1:
        raise ValueError("cassini quadruples require n >= 1")
    return (
        fibonacci(n - 1),
        fibonacci(n),
        fibonacci(n + 1),
        (-1) ** n,
    )


def cassini_holds(quadruple: Tuple[int, int, int, int]) -> bool:
    """Check F_{n-1} * F_{n+1} - F_n^2 == parity.  Pure."""
    f_prev, f_n, f_next, parity = quadruple
    return f_prev * f_next - f_n * f_n == parity


# ---------------------------------------------------------------------------
# Binet closed form — exact evaluation in Q(sqrt(5))
# ---------------------------------------------------------------------------


def _phi_power_exact(n: int) -> Tuple[int, int]:
    """Return (p, q) such that phi^n = (p + q*sqrt(5)) / 2, exactly.

    Multiplication in Z[sqrt(5)]/2:
        ((p1 + q1 s)/2)((p2 + q2 s)/2)
            = ((p1 p2 + 5 q1 q2) + (p1 q2 + q1 p2) s) / 4
    Halves stay integral because p, q share parity along the recurrence.
    """
    # base element phi^1 = (1 + sqrt(5)) / 2
    rp, rq = 1, 0  # result = phi^0 = 1 = (2 + 0 s)/2 -> tracked as (2, 0)
    rp, rq = 2, 0
    bp, bq = 1, 1  # base = phi^1
    e = n
    while e > 0:
        if e & 1:
            # result *= base : ((rp + rq s)/2)((bp + bq s)/2)
            np_ = (rp * bp + 5 * rq * bq) // 2
            nq = (rp * bq + rq * bp) // 2
            rp, rq = np_, nq
        # base = base^2
        bp, bq = (bp * bp + 5 * bq * bq) // 2, (2 * bp * bq) // 2
        e >>= 1
    return rp, rq


def binet_fibonacci(n: int) -> int:
    """Binet's closed form F_n = (phi^n - psi^n)/sqrt(5), exact integer.

    Evaluated in Q(sqrt(5)): with phi^n = (p + q sqrt(5))/2 and
    psi^n = (p - q sqrt(5))/2, the difference over sqrt(5) is exactly q.
    Precondition: ``n >= 0``.  Postcondition: result == fibonacci(n).
    Pure; thread-safe.
    """
    if n < 0:
        raise ValueError("binet index must be non-negative")
    if n == 0:
        return 0
    _p, q = _phi_power_exact(n)
    return q


def binet_approx(n: int) -> int:
    """Floating-point Binet evaluation for small n (diagnostic path).

    Uses Decimal at precision scaled to the magnitude of F_n; intended for
    cross-checking the exact quadratic-field path on moderate indices.
    """
    if n < 0:
        raise ValueError("binet index must be non-negative")
    digits = max(50, int(n * math.log10((1 + math.sqrt(5)) / 2)) + 10)
    with localcontext() as ctx:
        ctx.prec = digits
        sqrt5 = Decimal(5).sqrt()
        phi = (1 + sqrt5) / 2
        psi = (1 - sqrt5) / 2
        value = (phi**n - psi**n) / sqrt5
        return int(value.to_integral_value())


@dataclass(frozen=True)
class BinetIndex:
    """A closed-form index into the Fibonacci sequence.

    ``BinetIndex(n).value`` is F_n computed by Binet's closed form (exact,
    quadratic-field arithmetic — no float drift at any n).
    ``BinetIndex.of(v)`` recovers the index of a Fibonacci value or raises.
    """

    index: int

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError("BinetIndex requires a non-negative index")

    @property
    def value(self) -> int:
        """F_index via the exact closed form."""
        return binet_fibonacci(self.index)

    @classmethod
    def of(cls, value: int) -> "BinetIndex":
        """Recover the index of a Fibonacci value.

        Raises ``ValueError`` when ``value`` is not on the true Fibonacci
        sequence — the encoding layer's forgery check.
        """
        n = fibonacci_index(value)
        if n is None:
            raise ValueError(f"{value} is not a Fibonacci number")
        return cls(n)


__all__ = [
    "BinetIndex",
    "binet_approx",
    "binet_fibonacci",
    "cassini_holds",
    "cassini_quadruple",
    "fibonacci",
    "fibonacci_index",
    "is_fibonacci",
    "lucas",
]
