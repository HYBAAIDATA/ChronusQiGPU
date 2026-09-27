"""Cassini: L_{n-1} L_{n+1} − L_n² = 5(−1)^n."""

from __future__ import annotations

from phi_rotation.lucas import lucas
from phi_rotation.rotation import rotate_n


def cassini(n: int) -> int:
    return lucas(n - 1) * lucas(n + 1) - lucas(n) ** 2


def cassini_identity(n: int) -> bool:
    return cassini(n) == 5 * ((-1) ** n)


def det_power(n: int) -> int:
    return rotate_n(n).det()
