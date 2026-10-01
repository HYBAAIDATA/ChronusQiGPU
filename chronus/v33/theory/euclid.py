# euclid.py -- Classical number theory and Euclidean geometry primitives.
#
# Implements only checkable mathematics often associated with the Elements:
#   - Euclidean algorithm (Elements Book VII): gcd
#   - Extended Euclidean algorithm: Bézout coefficients (later number theory)
#   - Golden ratio φ from the extreme-and-mean ratio (Elements II.11, VI.30)
#   - Euclidean metric primitives on R^n (distance, angle, unit vector)
#
# Historical note (see HISTORICAL_ANALOGIES.md): naming the module after
# Euclid records the traditional source of the division algorithm and φ
# construction. It does not claim that Euclid formulated Hilbert space,
# quantum mechanics, or this software architecture. Structural parallels
# between axiomatic exposition and test-driven code are metaphorical only.

from __future__ import annotations

from typing import Tuple

import numpy as np

# Extreme-and-mean ratio (Elements): whole:greater = greater:lesser
PHI: float = (1.0 + np.sqrt(5.0)) / 2.0
PSI: float = (1.0 - np.sqrt(5.0)) / 2.0  # conjugate; |ψ| < 1


def euclid_gcd(a: int, b: int) -> int:
    """Classical Euclidean algorithm: gcd(a, b).

    Matches the division algorithm of Elements Book VII Prop. 2:
    repeatedly replace (a, b) ← (b, a mod b) until b = 0.
    """
    a, b = abs(int(a)), abs(int(b))
    while b != 0:
        a, b = b, a % b
    return a


def extended_euclid(a: int, b: int) -> Tuple[int, int, int]:
    """Extended Euclidean algorithm: returns (g, x, y) with a x + b y = g = gcd(a,b).

    Bézout's identity — the constructive form of the Euclidean algorithm
    that produces integer coefficients, not only the divisor.
    """
    a0, b0 = int(a), int(b)
    old_r, r = a0, b0
    old_s, s = 1, 0
    old_t, t = 0, 1
    while r != 0:
        q = old_r // r
        old_r, r = r, old_r - q * r
        old_s, s = s, old_s - q * s
        old_t, t = t, old_t - q * t
    g = abs(old_r)
    # Sign-normalise so g >= 0 and the identity holds for original a, b
    if old_r < 0:
        old_s, old_t = -old_s, -old_t
    return g, old_s, old_t


def phi_exact() -> float:
    """φ = (1 + √5)/2 — Euclid's extreme-and-mean ratio."""
    return PHI


def binet_fibonacci(n: int) -> int:
    """nth Fibonacci number via Binet's formula, rounded to nearest int.

    F_n = (φ^n − ψ^n) / √5. Exact for all integer n in a wide range
    because |ψ^n/√5| < 1/2.
    """
    n = int(n)
    return int(round((PHI**n - PSI**n) / np.sqrt(5.0)))


def phi_power_via_lucas(n: int) -> float:
    """Exact algebraic identity: φ^n = (L_n + F_n √5) / 2.

    Cross-checks the floating φ^n used in manifold / phi_scaling against
    integer Lucas + Fibonacci sequences (same identity as phi_scaling.phi_power_exact).
    """
    n = int(n)
    # Lucas L_n: L_0=2, L_1=1, L_n = L_{n-1}+L_{n-2}
    if n == 0:
        return 1.0
    f_prev, f = 0, 1  # F_0, F_1
    l_prev, l = 2, 1  # L_0, L_1
    for _ in range(1, n):
        f_prev, f = f, f_prev + f
        l_prev, l = l, l_prev + l
    # For n>=1: F_n = f, L_n = l after the loop starting from (F0,F1)
    # Adjust: after k steps from (0,1) we have F_k
    return (l + f * np.sqrt(5.0)) / 2.0


def euclidean_distance(a: np.ndarray, b: np.ndarray) -> float:
    """‖a − b‖₂ — Euclidean metric on R^n."""
    a = np.asarray(a, dtype=np.float64).reshape(-1)
    b = np.asarray(b, dtype=np.float64).reshape(-1)
    return float(np.linalg.norm(a - b))


def euclidean_angle(u: np.ndarray, v: np.ndarray) -> float:
    """Angle between two vectors in radians, via the Euclidean inner product."""
    u = np.asarray(u, dtype=np.float64).reshape(-1)
    v = np.asarray(v, dtype=np.float64).reshape(-1)
    nu = np.linalg.norm(u)
    nv = np.linalg.norm(v)
    if nu < 1e-15 or nv < 1e-15:
        return 0.0
    c = float(np.clip(np.dot(u, v) / (nu * nv), -1.0, 1.0))
    return float(np.arccos(c))


def unit_vector(v: np.ndarray) -> np.ndarray:
    """Normalise to unit Euclidean length (point on the unit sphere)."""
    v = np.asarray(v, dtype=np.float64).reshape(-1)
    n = np.linalg.norm(v)
    if n < 1e-15:
        out = np.zeros_like(v)
        out[0] = 1.0
        return out
    return v / n


def _self_test() -> str:
    # Euclidean algorithm
    assert euclid_gcd(48, 18) == 6
    assert euclid_gcd(100, 35) == 5
    assert euclid_gcd(252, 105) == 21
    assert euclid_gcd(0, 7) == 7
    assert euclid_gcd(17, 0) == 17

    # Extended Euclidean / Bézout
    for a, b in [(48, 18), (240, 46), (17, 13), (1, 1)]:
        g, x, y = extended_euclid(a, b)
        assert g == euclid_gcd(a, b)
        assert a * x + b * y == g

    # Golden ratio identities
    assert abs(PHI - 1.618033988749895) < 1e-12
    assert abs(PHI * PHI - (PHI + 1.0)) < 1e-12  # φ² = φ + 1
    assert abs(1.0 / PHI - (PHI - 1.0)) < 1e-12  # 1/φ = φ − 1

    # Binet Fibonacci
    fibs = [0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55]
    for n, f in enumerate(fibs):
        assert binet_fibonacci(n) == f

    # φ^n via Lucas matches float φ^n
    for n in (1, 5, 10, 12, 15):
        exact = phi_power_via_lucas(n)
        approx = PHI**n
        assert abs(exact - approx) / approx < 1e-12

    # Geometry primitives
    assert abs(euclidean_distance([0, 0], [3, 4]) - 5.0) < 1e-12
    assert abs(euclidean_angle([1, 0], [0, 1]) - np.pi / 2) < 1e-12
    u = unit_vector([3.0, 4.0])
    assert abs(np.linalg.norm(u) - 1.0) < 1e-12

    return "theory.euclid._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())
