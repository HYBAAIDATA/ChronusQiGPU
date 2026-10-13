"""
Fibonacci and Lucas sequences with arbitrary-precision Python integers.

Fast doubling gives O(log n) computation. Binet's formula uses Decimal
for exact nearest-integer recovery.
"""

import sys
from decimal import Decimal, ROUND_HALF_EVEN, getcontext


def fib_pair(n: int) -> tuple[int, int]:
    """Returns (F(n), F(n+1)) using fast doubling. F(0)=0, F(1)=1.

    Time complexity: O(log n) with arbitrary-precision integers.
    """
    if n == 0:
        return (0, 1)
    a, b = fib_pair(n >> 1)
    c = a * (2 * b - a)     # F(2k) = F(k) * (2*F(k+1) - F(k))
    d = a * a + b * b       # F(2k+1) = F(k)² + F(k+1)²
    if n & 1:
        return (d, c + d)
    return (c, d)


def fibonacci(n: int) -> int:
    """F(n) as Python int. F(0)=0, F(1)=1.

    Uses fast doubling: O(log n) multiplications.
    """
    if n < 0:
        return 0
    return fib_pair(n)[0]


def lucas(n: int) -> int:
    """L(n) as Python int. L(0)=2, L(1)=1.

    Uses the identity L(n) = 2*F(n+1) - F(n) for exact computation.
    """
    if n == 0:
        return 2
    if n == 1:
        return 1
    f_n, f_n1 = fib_pair(n)
    return 2 * f_n1 - f_n


def _compute_phi_psi_sqrt5(prec: int):
    """Recompute φ, ψ, √5 at a given precision using a local context."""
    from decimal import localcontext
    with localcontext() as ctx:
        ctx.prec = prec
        s5 = Decimal(5).sqrt()
        phi = (Decimal(1) + s5) / Decimal(2)
        psi = (Decimal(1) - s5) / Decimal(2)
        return s5, phi, psi


def binet_f(n: int) -> int:
    """Binet's formula: F(n) = (φ^n - ψ^n) / √5.

    Returns the exact integer via ROUND_HALF_EVEN.
    Uses a local Decimal context with precision scaled to n.
    """
    from decimal import localcontext, ROUND_HALF_EVEN
    needed = int(n * 0.21) + 100
    with localcontext() as ctx:
        ctx.prec = max(needed, getcontext().prec)
        s5 = Decimal(5).sqrt()
        phi = (Decimal(1) + s5) / Decimal(2)
        psi = (Decimal(1) - s5) / Decimal(2)
        val = (phi ** n - psi ** n) / s5
        return int(val.to_integral_value(rounding=ROUND_HALF_EVEN))


def binet_l(n: int) -> int:
    """Binet's formula for Lucas: L(n) = φ^n + ψ^n.

    Returns the exact integer via ROUND_HALF_EVEN.
    Uses a local Decimal context with precision scaled to n.
    """
    from decimal import localcontext, ROUND_HALF_EVEN
    needed = int(n * 0.21) + 100
    with localcontext() as ctx:
        ctx.prec = max(needed, getcontext().prec)
        s5 = Decimal(5).sqrt()
        phi = (Decimal(1) + s5) / Decimal(2)
        psi = (Decimal(1) - s5) / Decimal(2)
        val = phi ** n + psi ** n
        return int(val.to_integral_value(rounding=ROUND_HALF_EVEN))


def phi_power(n: int) -> Decimal:
    """φ^n as a Decimal with sufficient precision (local context)."""
    from decimal import localcontext
    needed = int(n * 0.21) + 100
    with localcontext() as ctx:
        ctx.prec = max(needed, getcontext().prec)
        s5 = Decimal(5).sqrt()
        phi = (Decimal(1) + s5) / Decimal(2)
        return phi ** n


def psi_power(n: int) -> Decimal:
    """ψ^n as a Decimal with sufficient precision (local context)."""
    from decimal import localcontext
    needed = int(n * 0.21) + 100
    with localcontext() as ctx:
        ctx.prec = max(needed, getcontext().prec)
        s5 = Decimal(5).sqrt()
        psi = (Decimal(1) - s5) / Decimal(2)
        return psi ** n
