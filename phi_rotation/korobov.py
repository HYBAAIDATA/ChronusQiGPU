"""Fibonacci / Korobov lattice on T²."""

from __future__ import annotations

from typing import List, Optional, Tuple

from phi_rotation.lucas import fibonacci


def korobov_point(i: int, n: int, gen: Optional[int] = None) -> Tuple[float, float]:
    if n <= 0:
        raise ValueError("n > 0")
    g = fibonacci(max(2, n.bit_length())) if gen is None else gen
    return (i / n) % 1.0, ((i * g) / n) % 1.0


def fibonacci_lattice(k: int) -> List[Tuple[float, float]]:
    n = max(1, fibonacci(k))
    gen = fibonacci(max(0, k - 1))
    return [korobov_point(i, n, gen) for i in range(n)]


def three_distance_gaps(alpha: float, n: int) -> int:
    pts = sorted((i * alpha) % 1.0 for i in range(n))
    pts.append(pts[0] + 1.0)
    gaps = [round(pts[i + 1] - pts[i], 12) for i in range(n)]
    return len(set(gaps))
