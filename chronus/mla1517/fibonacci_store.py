"""Exact Fibonacci recurrence store.

The preferred exact representation is the recurrence pair ``(F_n, F_{n+1})``,
NOT a floating-point Binet evaluation. Binet loses integer exactness at
moderate n; the recurrence pair never does. ``binet_view`` exposes the
algebraic form for presentation, and this module is the authority for it.

Fast doubling gives O(log n) exact integer arithmetic:

    F(2k)   = F_k * (2*F_{k+1} - F_k)
    F(2k+1) = F_k^2 + F_{k+1}^2
"""

from __future__ import annotations

__all__ = [
    "fib_pair",
    "fib",
    "fib_sequence",
    "lucas_pair",
    "lucas",
    "zeckendorf_indices",
    "fib_from_zeckendorf",
    "is_valid_fib_state",
]


def fib_pair(n: int) -> tuple[int, int]:
    """Exact ``(F_n, F_{n+1})`` by fast doubling. No tables, no floats."""
    if n < 0:
        raise ValueError("Fibonacci index must be non-negative")
    if n == 0:
        return (0, 1)
    a, b = 0, 1
    for bit in bin(n)[2:]:
        c = a * (2 * b - a)
        d = a * a + b * b
        if bit == "0":
            a, b = c, d
        else:
            a, b = d, c + d
    return (a, b)


def fib(n: int) -> int:
    """Exact ``F_n``."""
    return fib_pair(n)[0]


def lucas_pair(n: int) -> tuple[int, int]:
    """Exact ``(L_n, L_{n+1})``. ``L_n = F_{n-1} + F_{n+1}``."""
    if n < 0:
        raise ValueError("Lucas index must be non-negative")
    if n == 0:
        return (2, 1)
    f_n, f_np1 = fib_pair(n)
    f_nm1 = fib_pair(n - 1)[0] if n >= 1 else 1
    return (f_nm1 + f_np1, f_n + f_np1)


def lucas(n: int) -> int:
    """Exact ``L_n``."""
    return lucas_pair(n)[0]


def fib_sequence(count: int) -> list[int]:
    """``[F_0 .. F_{count-1}]``."""
    if count < 0:
        raise ValueError("count must be non-negative")
    return [fib(i) for i in range(count)]


def zeckendorf_indices(n: int) -> list[int]:
    """Greedy Zeckendorf decomposition: non-adjacent Fibonacci indices.

    Each value has a unique representation as a sum of non-adjacent
    Fibonacci numbers, so this is a bijection between integers and
    non-adjacent index sets.
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    if n == 0:
        return []
    out: list[int] = []
    remaining = n
    # Largest k with F_k <= remaining, searched downward.
    k = 1
    while fib(k + 1) <= remaining:
        k += 1
    while remaining > 0:
        while k >= 2 and fib(k) > remaining:
            k -= 1
        fk = fib(k)
        if fk <= remaining:
            out.append(k)
            remaining -= fk
            k -= 2  # non-adjacency: skip the next index
        else:
            k -= 1
    return sorted(out)


def fib_from_zeckendorf(indices: list[int]) -> int:
    """Inverse of :func:`zeckendorf_indices`.

    Refuses adjacent indices, because a non-adjacent set is the canonical
    form and admitting adjacency would make the encoding non-unique.
    """
    ordered = sorted(indices)
    for a, b in zip(ordered, ordered[1:]):
        if b - a < 2:
            raise ValueError(f"Zeckendorf indices must be non-adjacent: {a} and {b} are not")
    return sum(fib(k) for k in ordered)


def is_valid_fib_state(f_n: int, f_next: int) -> bool:
    """True when ``(f_n, f_next)`` is a genuine consecutive Fibonacci pair.

    Checks the Cassini storage seal, which detects a corrupted or truncated
    state without needing the original index.
    """
    if f_n < 0 or f_next < 0:
        return False
    if f_n == 0:
        return f_next == 1
    f_prev = f_next - f_n
    if f_prev < 0:
        return False
    seal = f_prev * f_next - f_n * f_n
    return seal in (1, -1)
