"""Golden ratio and Fibonacci/Lucas identities used by the tensor.

All integer-valued identities are computed exactly with Python bigints;
real-valued relations are verified to 100-digit Decimal precision.
"""

from __future__ import annotations
from decimal import Decimal, getcontext
from functools import lru_cache

getcontext().prec = 200

# High-precision phi
PHI = (Decimal(1) + Decimal(5).sqrt()) / Decimal(2)
PHI_STR_100 = str(PHI)[:102]  # "1." + 100 digits


@lru_cache(maxsize=None)
def fib(n: int) -> int:
    """F(0)=0, F(1)=1, F(n) = F(n-1) + F(n-2)."""
    if n < 0:
        raise ValueError("n must be >= 0")
    if n < 2:
        return n
    a, b = 0, 1
    for _ in range(n - 1):
        a, b = b, a + b
    return b


@lru_cache(maxsize=None)
def lucas(n: int) -> int:
    """L(0)=2, L(1)=1, L(n) = L(n-1) + L(n-2).  L(n) = round(phi^n) for n >= 2."""
    if n < 0:
        raise ValueError("n must be >= 0")
    if n == 0:
        return 2
    if n == 1:
        return 1
    a, b = 2, 1
    for _ in range(n - 1):
        a, b = b, a + b
    return b


def phi_power_identity_holds(n: int, tolerance: str = "1e-50") -> bool:
    """Verify phi^n = F(n) * phi + F(n-1) to Decimal precision."""
    if n < 1:
        raise ValueError("n must be >= 1")
    F_n = Decimal(fib(n))
    F_nm1 = Decimal(fib(n - 1))
    lhs = PHI**n
    rhs = F_n * PHI + F_nm1
    return abs(lhs - rhs) < Decimal(tolerance)


def lucas_equals_round_phi(n: int) -> bool:
    """Verify L(n) = round(phi^n) for n >= 2."""
    if n < 2:
        raise ValueError("n must be >= 2")
    return lucas(n) == int((PHI**n).quantize(Decimal("1"), rounding="ROUND_HALF_EVEN"))
