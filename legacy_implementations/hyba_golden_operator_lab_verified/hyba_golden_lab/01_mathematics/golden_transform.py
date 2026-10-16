#!/usr/bin/env python3
"""
CANONICAL GOLDEN TRANSFORM — frozen mathematical core.

Rule: no performance claim enters the project unless the underlying
identity and transformation are independently verified here.

Integer arithmetic is primary. Float64 is a secondary diagnostic only.

M = [[1, 1], [n: 1, 0]]
M^n [1, 0]^T = [F_{n+1}, F_n]^T
M^n [1, 2]^T = [L_{n+1}, L_n]^T
eig(M) = {Φ, ψ}
Tr(M^n) = L_n
det(M^n) = (−1)^n
L_n F_n = F_{2n}
L_n² − 5 F_n² = 4(−1)^n
"""
from __future__ import annotations

import math
from typing import Dict, List, Sequence, Tuple

import numpy as np

PHI = (1.0 + math.sqrt(5.0)) / 2.0
PSI = (1.0 - math.sqrt(5.0)) / 2.0
SQRT5 = math.sqrt(5.0)
PHI_INV = 1.0 / PHI
M_INT = ((1, 1), (1, 0))


def fib(n: int) -> int:
    if n < 0:
        return ((-1) ** (n + 1)) * fib(-n)
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def lucas(n: int) -> int:
    if n < 0:
        return ((-1) ** n) * lucas(-n)
    a, b = 2, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def zeckendorf(n: int) -> List[int]:
    if n <= 0:
        return []
    fibs = [1, 2]
    while fibs[-1] <= n:
        fibs.append(fibs[-1] + fibs[-2])
    if fibs[-1] > n:
        fibs.pop()
    parts, remain = [], n
    for f in reversed(fibs):
        if f <= remain:
            parts.append(f)
            remain -= f
    return parts


def pisano(m: int) -> int:
    if m <= 0:
        raise ValueError("modulus must be positive")
    if m == 1:
        return 1
    prev, curr = 0, 1
    for i in range(m * m + 2):
        prev, curr = curr, (prev + curr) % m
        if prev == 0 and curr == 1:
            return i + 1
    return m * m


def cassini(n: int) -> int:
    return (-1) ** n


def cassini_raw(n: int) -> int:
    return fib(n + 1) * fib(n - 1) - fib(n) ** 2


def M_pow_int(n: int) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    """Exact integer M^n."""
    if n == 0:
        return ((1, 0), (0, 1))
    if n > 0:
        return ((fib(n + 1), fib(n)), (fib(n), fib(n - 1)))
    inv = ((0, 1), (1, -1))
    out = ((1, 0), (0, 1))
    for _ in range(-n):
        out = (
            (out[0][0] * inv[0][0] + out[0][1] * inv[1][0],
             out[0][0] * inv[0][1] + out[0][1] * inv[1][1]),
            (out[1][0] * inv[0][0] + out[1][1] * inv[1][0],
             out[1][0] * inv[0][1] + out[1][1] * inv[1][1]),
        )
    return out


def M_pow(n: int) -> np.ndarray:
    m = M_pow_int(n)
    return np.array([[m[0][0], m[0][1]], [m[1][0], m[1][1]]], dtype=float)


def lucas_matrix_int(n: int) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    return ((lucas(n + 1), lucas(n)), (lucas(n), lucas(n - 1)))


def eigenvectors() -> Dict[str, np.ndarray]:
    return {
        "phi": np.array([PHI, 1.0], dtype=float),
        "psi": np.array([PSI, 1.0], dtype=float),
        "eigenvalues": np.array([PHI, PSI], dtype=float),
    }


def project(x: float, y: float) -> Tuple[float, float]:
    """[x,y] = a[Φ,1] + b[ψ,1]."""
    a = (x - y * PSI) / SQRT5
    b = (y * PHI - x) / SQRT5
    return float(a), float(b)


def reconstruct(a: float, b: float) -> Tuple[float, float]:
    return float(a * PHI + b * PSI), float(a + b)


def coherence(x: float, y: float) -> float:
    a, b = project(x, y)
    if abs(b) < 1e-300:
        return float("inf")
    return abs(a / b)


def apply_Mn(x: float, y: float, n: int) -> Tuple[float, float]:
    v = M_pow(n) @ np.array([x, y], dtype=float)
    return float(v[0]), float(v[1])


def verify_identities(n: int) -> Dict[str, bool]:
    """Primary: exact integers. Secondary: float diagnostics."""
    cassini_int = cassini_raw(n)
    lucas_det_int = lucas(n + 1) * lucas(n - 1) - lucas(n) ** 2
    Mn = M_pow_int(n)
    return {
        "Mn_entries": Mn == ((fib(n + 1), fib(n)), (fib(n), fib(n - 1))),
        "cassini_det_Mn": cassini_int == ((-1) ** n),
        "lucas_det": lucas_det_int == 5 * ((-1) ** (n - 1)),
        "trace_Mn_is_Ln": (Mn[0][0] + Mn[1][1]) == lucas(n),
        "lucas_trace_5Fn": (lucas(n + 1) + lucas(n - 1)) == 5 * fib(n),
        "Ln_Fn_eq_F2n": lucas(n) * fib(n) == fib(2 * n),
        "cassini_lucas": lucas(n) ** 2 - 5 * fib(n) ** 2 == 4 * ((-1) ** n),
        "invertible": cassini_int != 0,
        "binet_Ln_plus_float": abs((lucas(n) + fib(n) * SQRT5) - 2 * (PHI ** n))
        < 1e-8 * max(1.0, abs(PHI ** n)),
    }


def all_identities_hold(ns: Sequence[int] = range(1, 21)) -> bool:
    return all(all(verify_identities(n).values()) for n in ns)
