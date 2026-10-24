"""Canonical exact Lucas/Fibonacci arithmetic.

No floating point enters this module. All recurrence and composition operations
are arbitrary-precision integer operations.
"""
from __future__ import annotations

from typing import Tuple


def exact_lucas_fibonacci(n: int) -> Tuple[int, int]:
    """Return ``(L_n, F_n)`` exactly in O(log n) via fast doubling."""
    if n < 0:
        raise ValueError(f"index must be non-negative, got {n}")

    def fib_pair(k: int) -> Tuple[int, int]:
        if k == 0:
            return 0, 1
        a, b = fib_pair(k >> 1)
        c = a * ((b << 1) - a)
        d = a * a + b * b
        return (d, c + d) if k & 1 else (c, d)

    f_n, f_np1 = fib_pair(n)
    return 2 * f_np1 - f_n, f_n


def fast_doubling_call_count(n: int) -> int:
    """Return the exact recursive state count of the fast-doubling descent."""
    if n < 0:
        raise ValueError("index must be non-negative")
    count = 1
    while n:
        n >>= 1
        count += 1
    return count


def compose_add(idx_a: int, idx_b: int) -> int:
    la, fa = exact_lucas_fibonacci(idx_a)
    lb, fb = exact_lucas_fibonacci(idx_b)
    numerator = la * lb + 5 * fa * fb
    if numerator & 1:
        raise ValueError("Lucas addition parity invariant failed")
    return numerator // 2


def compose_sub(idx_a: int, idx_b: int) -> int:
    la, fa = exact_lucas_fibonacci(idx_a)
    lb, fb = exact_lucas_fibonacci(idx_b)
    numerator = la * lb - 5 * fa * fb
    if numerator & 1:
        raise ValueError("Lucas subtraction parity invariant failed")
    return ((-1 if idx_b & 1 else 1) * numerator) // 2


def compose_mul(idx_a: int, idx_b: int) -> int:
    return exact_lucas_fibonacci(idx_a)[0] * exact_lucas_fibonacci(idx_b)[0]


def pisano_period(modulus: int) -> int:
    """Return the Fibonacci period modulo ``modulus`` by exact state traversal."""
    if modulus < 1:
        raise ValueError("modulus must be positive")
    if modulus == 1:
        return 1
    a, b = 0, 1
    period = 0
    while True:
        a, b = b, (a + b) % modulus
        period += 1
        if (a, b) == (0, 1):
            return period


def lucas_period(modulus: int) -> int:
    """Return the least period of ``L_n mod modulus``."""
    if modulus < 1:
        raise ValueError("modulus must be positive")
    p = pisano_period(modulus)
    values = [exact_lucas_fibonacci(n)[0] % modulus for n in range(p)]
    for candidate in range(1, p + 1):
        if p % candidate == 0 and all(values[n] == values[(n + candidate) % p] for n in range(p)):
            return candidate
    raise ArithmeticError("Lucas period derivation failed")


def lucas_rank(modulus: int) -> int | None:
    """Return the least n>=1 with m|L_n, or None if no such n exists."""
    if modulus < 1:
        raise ValueError("modulus must be positive")
    period = lucas_period(modulus)
    for n in range(1, period + 1):
        if exact_lucas_fibonacci(n)[0] % modulus == 0:
            return n
    return None
