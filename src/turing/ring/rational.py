"""
Turing Exact Quantum Library — Exact Cyclotomic Field of Fractions Q(zeta_p)
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple, Union
from turing.errors import RingError
from turing.ring.utils import gcd
from turing.ring.zeta import ZetaP


@dataclass(frozen=True)
class RationalZetaP:
    """
    Exact element of the cyclotomic field of fractions Q(zeta_p) = Z[zeta_p] / Z.
    Represented as num / den where num in Z[zeta_p] and den in Z with den > 0.
    Canonicalized via gcd(den, gcd(num.coeffs)).
    """
    num: ZetaP
    den: int

    def __init__(self, num: ZetaP, den: int):
        if den == 0:
            raise ZeroDivisionError("Denominator cannot be zero in Q(zeta_p)")
        if den < 0:
            num = -num
            den = -den
        common = abs(den)
        for c in num.coeffs:
            common = gcd(common, abs(c))
        if common > 1:
            den //= common
            num = ZetaP(num.p, tuple(c // common for c in num.coeffs))
        object.__setattr__(self, 'num', num)
        object.__setattr__(self, 'den', den)

    @property
    def p(self) -> int:
        return self.num.p

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RationalZetaP):
            return False
        return self.num == other.num and self.den == other.den

    def __add__(self, other: Union['RationalZetaP', ZetaP, int]) -> 'RationalZetaP':
        if isinstance(other, int):
            other = RationalZetaP(ZetaP.from_int(other, self.p), 1)
        elif isinstance(other, ZetaP):
            other = RationalZetaP(other, 1)
        if not isinstance(other, RationalZetaP) or self.p != other.p:
            raise RingError("Field prime mismatch on addition")
        new_num = (self.num * other.den) + (other.num * self.den)
        new_den = self.den * other.den
        return RationalZetaP(new_num, new_den)

    def __sub__(self, other: Union['RationalZetaP', ZetaP, int]) -> 'RationalZetaP':
        if isinstance(other, int):
            other = RationalZetaP(ZetaP.from_int(other, self.p), 1)
        elif isinstance(other, ZetaP):
            other = RationalZetaP(other, 1)
        if not isinstance(other, RationalZetaP) or self.p != other.p:
            raise RingError("Field prime mismatch on subtraction")
        new_num = (self.num * other.den) - (other.num * self.den)
        new_den = self.den * other.den
        return RationalZetaP(new_num, new_den)

    def __neg__(self) -> 'RationalZetaP':
        return RationalZetaP(-self.num, self.den)

    def __mul__(self, other: Union['RationalZetaP', ZetaP, int]) -> 'RationalZetaP':
        if isinstance(other, int):
            return RationalZetaP(self.num * other, self.den)
        if isinstance(other, ZetaP):
            return RationalZetaP(self.num * other, self.den)
        if not isinstance(other, RationalZetaP) or self.p != other.p:
            raise RingError("Field prime mismatch on multiplication")
        return RationalZetaP(self.num * other.num, self.den * other.den)

    def __rmul__(self, other: Union[int, ZetaP]) -> 'RationalZetaP':
        if isinstance(other, (int, ZetaP)):
            return self * other
        return NotImplemented

    def inverse(self) -> 'RationalZetaP':
        if self.num == ZetaP.zero(self.p):
            raise ZeroDivisionError("Cannot invert zero in Q(zeta_p)")
        field_inv = self.num.field_inverse()
        return RationalZetaP(field_inv.num * self.den, field_inv.den)

    def to_tuple(self) -> Tuple[Tuple[int, ...], int]:
        return (self.num.coeffs, self.den)

    def __repr__(self) -> str:
        return f"RationalZetaP(num={self.num.coeffs}, den={self.den}, p={self.p})"
