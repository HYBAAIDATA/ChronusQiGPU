"""Canonical mathematical constants for resonance intelligence."""

from __future__ import annotations

import math

PHI: float = (1.0 + math.sqrt(5.0)) / 2.0
PHI_I: float = 1.0 / PHI
PHI_INV: float = PHI_I
DELTA: float = 3.0 - PHI


def _fibonacci(count: int = 32) -> tuple[int, ...]:
    values: list[int] = []
    a, b = 0, 1
    for _ in range(count):
        values.append(b)
        a, b = b, a + b
    return tuple(values)


FIBS: tuple[int, ...] = _fibonacci()

__all__ = ["PHI", "PHI_I", "PHI_INV", "DELTA", "FIBS"]
