"""Exact crystallographic root families for cross-domain geometry discovery.

E8 is a rank-eight root system with 240 roots; the 248-dimensional
number refers to the corresponding Lie algebra, NOT its root vectors.
Leech is a distinct rank-24 lattice and is deliberately not fabricated
from an E8 coordinate pad or an arbitrary 24D slice.
"""
from __future__ import annotations

from fractions import Fraction
from itertools import combinations, product

Vector = tuple[Fraction, ...]


def _validate(roots: tuple[Vector, ...], dimension: int,
              expected_count: int, squared_norm: int = 2) -> None:
    if len(roots) != expected_count or len(set(roots)) != expected_count:
        raise AssertionError("root-system cardinality / uniqueness failure")
    if any(len(v) != dimension or sum(x*x for x in v) != squared_norm
           for v in roots):
        raise AssertionError("root squared-length invariant failed")
    s = set(roots)
    if any(tuple(-x for x in v) not in s for v in roots):
        raise AssertionError("root system missing negatives")


def roots_a(rank: int) -> tuple[Vector, ...]:
    """A_n roots e_i-e_j in the n+1-dimensional sum-zero hyperplane."""
    if type(rank) is not int or not 1 <= rank <= 24:
        raise ValueError("A_n rank must be between 1 and 24")
    n = rank + 1
    roots = set()
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            v = [Fraction(0)] * n
            v[i], v[j] = Fraction(1), Fraction(-1)
            roots.add(tuple(v))
    out = tuple(sorted(roots))
    _validate(out, n, rank*(rank+1))
    return out


def roots_d(rank: int) -> tuple[Vector, ...]:
    """D_n roots ±e_i±e_j (n >= 4)."""
    if type(rank) is not int or not 4 <= rank <= 24:
        raise ValueError("D_n rank must be between 4 and 24")
    roots = set()
    for i, j in combinations(range(rank), 2):
        for s, t in product((-1, 1), repeat=2):
            v = [Fraction(0)] * rank
            v[i], v[j] = Fraction(s), Fraction(t)
            roots.add(tuple(v))
    out = tuple(sorted(roots))
    _validate(out, rank, 2*rank*(rank-1))
    return out


def roots_e8() -> tuple[Vector, ...]:
    """240 E8 roots using the two standard exact coordinate families."""
    roots = set(roots_d(8))  # 112 roots
    for signs in product((-1, 1), repeat=8):
        if sum(x < 0 for x in signs) % 2 == 0:
            roots.add(tuple(Fraction(x, 2) for x in signs))
    out = tuple(sorted(roots))
    _validate(out, 8, 240)
    if any(sum(a*b for a, b in zip(x, y)).denominator != 1
           for x in out for y in out):
        raise AssertionError("E8 lattice roots lack integral pairing")
    return out


def catalog() -> dict[str, dict[str, object]]:
    """Exact root cardinalities and ambient dimensions for candidate selection."""
    return {
        "A3": {"rank": 3, "ambient_dimension": 4, "roots": 12},
        "D4": {"rank": 4, "ambient_dimension": 4, "roots": 24},
        "E8": {"rank": 8, "ambient_dimension": 8, "roots": 240},
        "H4": {"rank": 4, "ambient_dimension": 4, "roots": 120,
               "field": "Q(sqrt(5))", "crystallographic": False},
        "Leech": {"rank": 24, "ambient_dimension": 24,
                  "construction": "UNAVAILABLE_NOT_IMPLEMENTED"},
    }
