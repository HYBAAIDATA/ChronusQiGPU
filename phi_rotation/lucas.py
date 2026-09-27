"""Lucas / Fibonacci from the companion matrix of φ."""

from __future__ import annotations

from typing import List, Tuple

from phi_rotation.rotation import R, rotate_n


def lucas(n: int) -> int:
    if n == 0:
        return 2
    if n == 1:
        return 1
    a, b = 2, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b


def fibonacci(n: int) -> int:
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
