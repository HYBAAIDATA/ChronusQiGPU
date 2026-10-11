"""Exact Lucas-tier scaling planner.

A tier exponent names the Lucas rung L_n. For n>=2, nearest-integer Binet
identity gives round(phi**n) == L_n, so tier cardinality can be represented
without floating point. This module plans large tiers without attempting to
allocate an impossible dense manifold.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .lucas_engine import lucas


@dataclass(frozen=True)
class LucasTier:
    exponent: int
    lucas_value: int
    bit_length: int
    dense_matrix_elements: int
    dense_feasible: bool
    status: str


def tier(exponent: int, dense_face_limit: int = 4096) -> LucasTier:
    if not isinstance(exponent, int) or isinstance(exponent, bool) or exponent < 0:
        raise ValueError("exponent must be a non-negative integer")
    value = lucas(exponent)
    elements = value * value
    return LucasTier(
        exponent=exponent,
        lucas_value=value,
        bit_length=value.bit_length(),
        dense_matrix_elements=elements,
        dense_feasible=value <= dense_face_limit,
        status="DENSE_REFERENCE_ELIGIBLE" if value <= dense_face_limit else "PLANNER_ONLY",
    )


def plan(exponents: Iterable[int] = (10, 12, 15, 18, 20, 31, 50, 76),
         dense_face_limit: int = 4096) -> list[LucasTier]:
    return [tier(n, dense_face_limit=dense_face_limit) for n in exponents]
