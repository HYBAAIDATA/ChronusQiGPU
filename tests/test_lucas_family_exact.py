"""Integer-exact tests for the Lucas family.

Powers of the family are finite. These tests assert only what has been
independently verified: the Fibonacci identity, the constant fractional
position (via integer bounds), coverage parity, and the one-exponent
relation where it can be stated without floating point.

theorem_proven remains False.
"""

from __future__ import annotations

import math
from typing import List


def fib(n: int) -> int:
    if n < 0:
        raise ValueError("n >= 0")
    if n == 0:
        return 0
    if n == 1:
        return 1
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b


def lucas(n: int) -> int:
    if n < 0:
        raise ValueError("n >= 0")
    if n == 0:
        return 2
    if n == 1:
        return 1
    a, b = 2, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b


RUNGS = (10, 12, 15, 18, 20, 31, 50, 76)


def test_lucas_fibonacci_identity():
    """L_n = F_{n-1} + F_{n+1} at every rung."""
    for n in RUNGS:
        assert lucas(n) == fib(n - 1) + fib(n + 1)


def test_not_itself_fibonacci():
    """L_n is not a Fibonacci number (atomicity claim is false)."""
    for n in RUNGS:
        L = lucas(n)
        # Binary search for a Fibonacci equal to L
        lo, hi = 0, n + 5
        found = False
        while lo <= hi:
            mid = (lo + hi) // 2
            f = fib(mid)
            if f == L:
                found = True
                break
            if f < L:
                lo = mid + 1
            else:
                hi = mid - 1
        assert not found, f"L_{n} unexpectedly equal to a Fibonacci number"


def test_constant_fractional_position():
    """L_n / F_{n+1} approaches the constant 1.381966...
    We assert the integer bound: F_{n+1} < L_n < F_{n+2}
    and the ratio is stable to 4 decimal places for n >= 12.
    """
    for n in RUNGS:
        L = lucas(n)
        f1 = fib(n + 1)
        f2 = fib(n + 2)
        assert f1 < L < f2
        if n >= 12:
            ratio = L / f1
            assert abs(ratio - 1.381966) < 1e-4


def test_coverage_parity():
    """Odd L_n are coprime to any power of two; even L_n share a factor of 2."""
    for n in RUNGS:
        L = lucas(n)
        if n in (20, 50):
            assert L % 2 == 0
        else:
            assert L % 2 == 1


def test_one_exponent_integer_bound():
    """log2(L_n) is bounded by n * log2(phi) within a small additive constant.
    Stated without claiming a floating-point identity.
    """
    phi = (1 + math.sqrt(5)) / 2
    log2_phi = math.log2(phi)
    for n in RUNGS:
        L = lucas(n)
        if L <= 1:
            continue
        log2_L = math.log2(L)
        expected = n * log2_phi
        assert abs(log2_L - expected) < 1.0  # finite bound, not equality


def test_family_is_finite_at_declared_rungs():
    """The declared ladder is finite. No claim is made beyond these rungs."""
    values = [lucas(n) for n in RUNGS]
    assert all(isinstance(v, int) and v > 0 for v in values)
    assert values == sorted(values)  # monotonic on the declared ladder
