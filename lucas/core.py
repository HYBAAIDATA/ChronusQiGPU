"""Exact Lucas and Fibonacci numbers via fast doubling.

O(log n) integer arithmetic. No floating point. No tables.
"""

from __future__ import annotations


def _fib_lucas_pair(n: int) -> tuple[int, int]:
    """Return (F_n, L_n) by simultaneous fast doubling."""
    if n < 0:
        raise ValueError("Lucas/Fibonacci index must be non-negative")
    if n == 0:
        return (0, 2)
    if n == 1:
        return (1, 1)

    # Recursively obtain (F_k, L_k) for k = n // 2.
    f_k, l_k = _fib_lucas_pair(n >> 1)

    # Double-angle identities:
    #   F_{2k}   = F_k * L_k
    #   L_{2k}   = L_k^2 - 2*(-1)^k
    f_2k = f_k * l_k
    l_2k = l_k * l_k - 2 * (1 if (n & 2) == 0 else -1)

    if n & 1:
        # Odd case from the doubled values:
        #   F_{2k+1} = (F_{2k} + L_{2k}) / 2
        #   L_{2k+1} = (5*F_{2k} + L_{2k}) / 2
        f_next = (f_2k + l_2k) >> 1
        l_next = (5 * f_2k + l_2k) >> 1
        return (f_next, l_next)
    return (f_2k, l_2k)


def lucas(n: int) -> int:
    """Exact Lucas number L_n."""
    return _fib_lucas_pair(n)[1]


def fibonacci(n: int) -> int:
    """Exact Fibonacci number F_n."""
    return _fib_lucas_pair(n)[0]


def lucas_sequence(count: int) -> list[int]:
    """Return [L_0, L_1, ..., L_{count-1}]."""
    return [lucas(i) for i in range(count)]
