"""Cassini: L_{n-1} L_{n+1} - L_n^2 = 5(-1)^(n+1) for L_0=2, L_1=1.

The exponent carries the +1 because this Lucas sequence starts at L_0=2,
L_1=1: at n=0 the identity evaluates L_{-1} L_1 - L_0^2 = -1 - 4 = -5.
"""

from __future__ import annotations

from phi_rotation.lucas import lucas
from phi_rotation.rotation import rotate_n


def cassini(n: int) -> int:
    return lucas(n - 1) * lucas(n + 1) - lucas(n) ** 2


def cassini_identity(n: int) -> bool:
    """L_{n-1} L_{n+1} - L_n^2 = 5(-1)^(n+1) for L_0=2, L_1=1.

    The exponent is n+1, not n: with this indexing the n=0 case evaluates
    L_{-1} L_1 - L_0^2 = (-1)(1) - 4 = -5, so the sequence starts negative.
    """
    return cassini(n) == 5 * ((-1) ** (n + 1))


def det_power(n: int) -> int:
    return rotate_n(n).det()
