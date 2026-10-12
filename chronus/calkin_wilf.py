"""Exact one-based rational enumeration and reduced-positive inverse.

LUCAS WIRING: rational address substrate, not a quantum-execution claim.
"""

from __future__ import annotations

from fractions import Fraction
from math import gcd


def _positive(value: int) -> None:
    if type(value) is not int:
        raise TypeError("integer required")
    if value < 1:
        raise ValueError("positive integer required")


def _fraction(a: int, b: int) -> None:
    _positive(a)
    _positive(b)
    if gcd(a, b) != 1:
        raise ValueError("reduced fraction required")


def binary_path(n: int) -> list[int]:
    _positive(n)
    return [int(bit) for bit in bin(n)[3:]]


def calkin_wilf(n: int) -> tuple[int, int]:
    """Index 1 is 1/1; index 0 is rejected rather than aliasing the root."""
    a, b = 1, 1
    for bit in binary_path(n):
        if bit:
            a += b
        else:
            b += a
    return a, b


def calkin_wilf_index(a: int, b: int) -> int:
    """Inverse by Euclidean run lengths; index output can have Θ(a+b) bits."""
    _fraction(a, b)
    runs = []
    while a != b:
        if a > b:
            length = (a - 1) // b
            runs.append((1, length))
            a -= length * b
        else:
            length = (b - 1) // a
            runs.append((0, length))
            b -= length * a
    index = 1
    for bit, length in reversed(runs):
        index <<= length
        if bit:
            index |= (1 << length) - 1
    return index


def stern_brocot_neighbors(a: int, b: int) -> tuple[tuple[int, int], tuple[int, int]]:
    """Ordered mediant parents, permitting boundary endpoints 0/1 and 1/0."""
    _fraction(a, b)
    if b == 1:
        return (a - 1, 1), (1, 0)
    q = pow(a, -1, b)
    p = (a * q - 1) // b
    return (p, q), (a - p, b - q)


def phi_convergents(k: int) -> list[Fraction]:
    if type(k) is not int:
        raise TypeError("integer count required")
    if k < 0:
        raise ValueError("nonnegative count required")
    a, b = 1, 1
    result = []
    for _ in range(k):
        result.append(Fraction(b, a))
        a, b = b, a + b
    return result
