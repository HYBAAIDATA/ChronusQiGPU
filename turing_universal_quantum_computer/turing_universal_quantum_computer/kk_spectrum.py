# LUCAS WIRING: mtheory
# Substrate route: mtheory
"""Exact Kaluza-Klein tower of an 11-dimensional theory compactified on T^7.

What is implemented here is the exact lattice arithmetic of the KK mass
formula: for a mode vector ``n in Z^7`` on a rectangular 7-torus with
circle radii ``R_i`` (in units where the 11D Planck scale is 1),

    m^2(n) = sum_i n_i^2 / R_i^2 ,

computed entirely in ``fractions.Fraction`` — no floats, no approximation,
no simulation.  ``spectrum(n_max)`` is the exact multiset of squared masses
over the truncated lattice ``|n_i| <= n_max``; ``degeneracy`` counts exact
multiplicities.  ``verify_tower`` performs exact algebraic checks
(``==`` on Fractions), nothing statistical.

This is exact group/lattice arithmetic on truncated spectra — it is not a
claim about physical string dynamics.

Default radii
-------------
``SECTOR_RADII`` is derived deterministically from the repo's seven
Millennium sector invariants ``MILLENNIUM_BOUNDS = [1/1000, 15, 1/2, 2,
1, 1, 1]`` (see ``Intelligence/intelligences/quantum.py`` where the same
constants appear as ``[0.001, 15.0, 0.5, 2.0, 1.0, 1.0, 1.0]``).  Using the
sector invariants as the seven compact radii is this repository's
convention; any other 7-tuple of positive Fractions may be supplied.
"""

from __future__ import annotations

from collections import Counter
from fractions import Fraction
from itertools import product
from math import isqrt
from typing import Dict, Iterable, List, Tuple

# The repo's seven sector invariants (Millennium bounds), as exact Fractions.
# This tuple is the repo-wide convention for "the seven sectors".
MILLENNIUM_BOUNDS: Tuple[Fraction, ...] = (
    Fraction(1, 1000),
    Fraction(15),
    Fraction(1, 2),
    Fraction(2),
    Fraction(1),
    Fraction(1),
    Fraction(1),
)

# Default compact-circle radii: identified with MILLENNIUM_BOUNDS by the
# repo convention documented in the module docstring.
SECTOR_RADII: Tuple[Fraction, ...] = MILLENNIUM_BOUNDS

ModeVector = Tuple[int, ...]


class KKTower:
    """Exact KK mass tower on a rectangular T^7 with radii ``radii``.

    ``radii`` must be a 7-tuple of positive values convertible to Fraction
    (Fraction, int, or numeric strings).  All arithmetic is exact.
    """

    DIMENSION = 7

    def __init__(self, radii: Iterable[Fraction] = SECTOR_RADII):
        radii = tuple(Fraction(r) for r in radii)
        if len(radii) != self.DIMENSION:
            raise ValueError(f"KK tower needs exactly {self.DIMENSION} radii, got {len(radii)}")
        if any(r <= 0 for r in radii):
            raise ValueError("All compact radii must be positive")
        self.radii: Tuple[Fraction, ...] = radii
        # Exact inverse-square metric factors 1 / R_i^2.
        self._inv_sq: Tuple[Fraction, ...] = tuple(1 / (r * r) for r in radii)

    def mass_squared(self, n: ModeVector) -> Fraction:
        """Exact m^2(n) = sum_i n_i^2 / R_i^2 for ``n in Z^7``."""
        n = tuple(int(k) for k in n)
        if len(n) != self.DIMENSION:
            raise ValueError(f"mode vector must have {self.DIMENSION} components")
        return sum(
            ((k * k) * g for k, g in zip(n, self._inv_sq) if k),
            Fraction(0),
        )

    def lattice(self, n_max: int) -> Iterable[ModeVector]:
        """All mode vectors in the truncated lattice ``|n_i| <= n_max``."""
        if n_max < 0:
            raise ValueError("n_max must be non-negative")
        return product(range(-n_max, n_max + 1), repeat=self.DIMENSION)

    def spectrum(self, n_max: int) -> Counter:
        """Exact multiset of m^2 values over the truncated lattice.

        Returns a ``Counter`` mapping each exact Fraction m^2 to its
        degeneracy.  Use ``levels`` for the sorted level values.
        """
        return Counter(self.mass_squared(n) for n in self.lattice(n_max))

    def levels(self, n_max: int) -> List[Fraction]:
        """Sorted list of distinct m^2 values in the truncated tower."""
        return sorted(self.spectrum(n_max))

    def degeneracy(self, m2: Fraction, n_max: int | None = None) -> int:
        """Exact number of lattice modes with the given squared mass.

        With ``n_max`` given, counts within the truncated lattice
        ``|n_i| <= n_max``.  Without it, counts over the full integer
        lattice — exact and finite because m^2(n) >= (min_i 1/R_i^2) * |n|^2
        bounds the search box by ``|n_i|^2 <= m2 * R_i^2``.
        """
        m2 = Fraction(m2)
        if m2 < 0:
            return 0
        if n_max is not None:
            return self.spectrum(n_max)[m2]
        # Exact finite count: per-axis bound |n_i| <= floor(sqrt(m2 * R_i^2)).
        count = 0
        bounds = []
        for r in self.radii:
            lim = m2 * r * r
            bounds.append(_isqrt_floor(lim))
        for n in product(*(range(-b, b + 1) for b in bounds)):
            if self.mass_squared(n) == m2:
                count += 1
        return count

    def verify_tower(self, n_max: int = 1) -> Dict[str, bool]:
        """Exact structural checks on the truncated tower.

        * zero mode: m^2(0) == 0 exactly;
        * evenness: m^2(n) == m^2(-n) for every n in the truncated lattice
          (so every nonzero level's ±n degeneracy pairing is exact);
        * first level: the smallest nonzero m^2 in the truncated spectrum
          equals ``min_i 1/R_i^2`` computed directly.
        """
        zero = (0,) * self.DIMENSION
        checks = {
            "zero_mode": self.mass_squared(zero) == 0,
            "even_under_reflection": all(
                self.mass_squared(n) == self.mass_squared(tuple(-k for k in n))
                for n in self.lattice(n_max)
            ),
        }
        spec = self.spectrum(n_max)
        nonzero = sorted(m2 for m2 in spec if m2 != 0)
        first = nonzero[0] if nonzero else None
        direct = min(self._inv_sq)
        checks["first_level"] = first == direct
        checks["first_level_degeneracy_exact"] = (
            spec[first] == 2 * sum(1 for g in self._inv_sq if g == direct)
            if first is not None
            else False
        )
        return checks


def _isqrt_floor(x: Fraction) -> int:
    """Exact floor of sqrt(x) for non-negative Fraction ``x``.

    floor(sqrt(p/q)) == isqrt(floor(p/q)) for p, q > 0, so exact integer
    ``math.isqrt`` on ``p // q`` is the exact answer — no float involved.
    """
    if x < 0:
        raise ValueError("isqrt of negative")
    return isqrt(x.numerator // x.denominator)


__all__ = [
    "KKTower",
    "MILLENNIUM_BOUNDS",
    "SECTOR_RADII",
    "ModeVector",
]
