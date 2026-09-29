"""Lucas / Fibonacci from the companion matrix of φ."""

from __future__ import annotations

from typing import List, Tuple

from phi_rotation.rotation import R, rotate_n


def lucas(n: int) -> int:
    """L_n with L_0=2, L_1=1, extended to negative indices.

    The recurrence L_{n} = L_{n-1} + L_{n-2} inverts for negative indices as
    L_{n-2} = L_n - L_{n-1}, so L_{-1} = L_1 - L_0 = 1 - 2 = -1 and generally
    L_{-k} = (-1)^k * L_k. Extending here (rather than leaving the loop to fall
    through and return b) is required by the Cassini identity, which evaluates
    L_{n-1} and so touches L_{-1} at n = 0.
    """
    if n < 0:
        return (-1) ** (-n) * lucas(-n)
    if n == 0:
        return 2
    if n == 1:
        return 1
    a, b = 2, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b


def fibonacci(n: int) -> int:
    """F_n with F_0=0, F_1=1, extended to negative indices via F_{-k}=(-1)^{k+1}F_k."""
    if n < 0:
        return (-1) ** (-n + 1) * fibonacci(-n)
    if n == 0:
        return 0
    if n == 1:
        return 1
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b


def lucas_wind(seed: Tuple[float, float], steps: int) -> List[Tuple[float, float]]:
    orbit = [seed]
    cur = seed
    for _ in range(steps):
        cur = R.apply(*cur)
        orbit.append(cur)
    return orbit


def lucas_is_trace(n: int) -> bool:
    return lucas(n) == rotate_n(n).trace()
