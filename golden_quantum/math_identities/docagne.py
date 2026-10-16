"""
d'Ocagne's Identity — cross-index distance in the Fibonacci lattice.

d'Ocagne's Identity:
    F_m * F_{n+1} - F_{m+1} * F_n = (-1)^n * F_{m-n}

This gives a signed topological distance between two Fibonacci-indexed nodes
using only local coordinates, with no centralized registry.

Supports negative indices via:
    F_{-k} = (-1)^{k+1} * F_k
"""

from ..sequences import fibonacci, fib_pair


def fib_signed(n: int) -> int:
    """Fibonacci number for any integer n (including negative).

    F_{-k} = (-1)^{k+1} * F_k
    """
    if n >= 0:
        return fibonacci(n)
    k = -n
    sign = 1 if k % 2 == 1 else -1  # (-1)^{k+1}
    return sign * fibonacci(k)


def docagne_identity(m: int, n: int) -> bool:
    """Verify d'Ocagne's identity for indices m, n.

    F_m * F_{n+1} - F_{m+1} * F_n == (-1)^n * F_{m-n}

    Uses exact Python integers — no float arithmetic.
    """
    F_m = fibonacci(m) if m >= 0 else fib_signed(m)
    F_m1 = fibonacci(m + 1) if m >= 0 else fib_signed(m + 1)
    F_n = fibonacci(n) if n >= 0 else fib_signed(n)
    F_n1 = fibonacci(n + 1) if n >= 0 else fib_signed(n + 1)

    lhs = F_m * F_n1 - F_m1 * F_n
    sign = 1 if n % 2 == 0 else -1
    rhs = sign * fib_signed(m - n)

    return lhs == rhs


def docagne_distance(m: int, n: int) -> int:
    """Compute signed Fibonacci distance F_{m-n} via d'Ocagne's identity.

    Uses the identity:
        F_{m-n} = (-1)^n * (F_m * F_{n+1} - F_{m+1} * F_n)

    This is exact integer arithmetic, not float division.
    """
    F_m = fibonacci(m) if m >= 0 else fib_signed(m)
    F_m1 = fibonacci(m + 1) if m >= 0 else fib_signed(m + 1)
    F_n = fibonacci(n) if n >= 0 else fib_signed(n)
    F_n1 = fibonacci(n + 1) if n >= 0 else fib_signed(n + 1)

    cross = F_m * F_n1 - F_m1 * F_n
    sign = 1 if n % 2 == 0 else -1

    return sign * cross
