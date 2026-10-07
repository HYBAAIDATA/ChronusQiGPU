"""Q8 — the field Q(zeta_8) = Q(i, sqrt 2) on integer coordinates.

An element is (a + b*sqrt2 + i*(c + d*sqrt2)) / den with integers a..d and
den > 0, kept in lowest terms, so equality is tuple equality. This is the
same field as :class:`kellogg.exact_tensor.F4`; ``Q8.from_f4`` and
``Q8.to_f4`` convert exactly. Q8 is the working representation of the exact
tensor-network engine because integer coordinates avoid the per-operation
Fraction allocations F4 makes.

Subfields: Q (b = c = d = 0), Q(i) (b = d = 0), Q(sqrt 2) (c = d = 0).
Order is defined on the real subfield Q(sqrt 2) only.
"""

from __future__ import annotations

from fractions import Fraction
from math import gcd, lcm
from typing import Tuple

from .exact_tensor import F4


class NotReal(ValueError):
    """An order comparison was requested for an element with an imaginary part."""


class Q8:
    __slots__ = ("a", "b", "c", "d", "den")

    def __init__(self, a: int = 0, b: int = 0, c: int = 0, d: int = 0, den: int = 1) -> None:
        if den == 0:
            raise ZeroDivisionError("Q8 denominator is zero")
        if den < 0:
            a, b, c, d, den = -a, -b, -c, -d, -den
        g = gcd(a, b, c, d, den)
        if g > 1:
            a, b, c, d, den = a // g, b // g, c // g, d // g, den // g
        self.a = a
        self.b = b
        self.c = c
        self.d = d
        self.den = den

    @classmethod
    def from_fractions(
        cls,
        a: Fraction | int = 0,
        b: Fraction | int = 0,
        c: Fraction | int = 0,
        d: Fraction | int = 0,
    ) -> "Q8":
        parts = [Fraction(v) for v in (a, b, c, d)]
        den = lcm(*(p.denominator for p in parts))
        return cls(*(int(p * den) for p in parts), den)

    @classmethod
    def from_f4(cls, value: F4) -> "Q8":
        return cls.from_fractions(value.a, value.b, value.c, value.d)

    @classmethod
    def coerce(cls, value: object) -> "Q8":
        if isinstance(value, Q8):
            return value
        if isinstance(value, F4):
            return cls.from_f4(value)
        if isinstance(value, (int, Fraction)) and not isinstance(value, bool):
            return cls.from_fractions(value)
        raise TypeError(f"{type(value).__name__} is not an exact Q(zeta_8) value")

    def to_f4(self) -> F4:
        den = self.den
        return F4(Fraction(self.a, den), Fraction(self.b, den), Fraction(self.c, den), Fraction(self.d, den))

    def key(self) -> Tuple[int, int, int, int, int]:
        return (self.a, self.b, self.c, self.d, self.den)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Q8):
            return (
                self.a == other.a
                and self.b == other.b
                and self.c == other.c
                and self.d == other.d
                and self.den == other.den
            )
        if isinstance(other, (int, Fraction, F4)) and not isinstance(other, bool):
            return self == Q8.coerce(other)
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.key())

    def __repr__(self) -> str:
        return f"Q8({self.a}, {self.b}, {self.c}, {self.d}, den={self.den})"

    def is_zero(self) -> bool:
        return self.a == 0 and self.b == 0 and self.c == 0 and self.d == 0

    def __bool__(self) -> bool:
        return not self.is_zero()

    def __add__(self, other: "Q8") -> "Q8":
        if not isinstance(other, Q8):
            other = Q8.coerce(other)
        if self.den == other.den:
            return Q8(self.a + other.a, self.b + other.b, self.c + other.c, self.d + other.d, self.den)
        p, q = self.den, other.den
        return Q8(
            self.a * q + other.a * p,
            self.b * q + other.b * p,
            self.c * q + other.c * p,
            self.d * q + other.d * p,
            p * q,
        )

    __radd__ = __add__

    def __neg__(self) -> "Q8":
        return Q8(-self.a, -self.b, -self.c, -self.d, self.den)

    def __sub__(self, other: "Q8") -> "Q8":
        if not isinstance(other, Q8):
            other = Q8.coerce(other)
        return self + (-other)

    def __rsub__(self, other: object) -> "Q8":
        return Q8.coerce(other) - self

    def __mul__(self, other: "Q8") -> "Q8":
        if not isinstance(other, Q8):
            other = Q8.coerce(other)
        a, b, c, d = self.a, self.b, self.c, self.d
        e, f, g, h = other.a, other.b, other.c, other.d
        # (x + i y)(u + i v) with x = a + b r, y = c + d r, u = e + f r, v = g + h r, r^2 = 2
        re_a = a * e + 2 * b * f - (c * g + 2 * d * h)
        re_b = a * f + b * e - (c * h + d * g)
        im_a = a * g + 2 * b * h + c * e + 2 * d * f
        im_b = a * h + b * g + c * f + d * e
        return Q8(re_a, re_b, im_a, im_b, self.den * other.den)

    __rmul__ = __mul__

    def conjugate(self) -> "Q8":
        return Q8(self.a, self.b, -self.c, -self.d, self.den)

    def norm2(self) -> "Q8":
        """|z|^2 in Q(sqrt 2)."""
        a, b, c, d = self.a, self.b, self.c, self.d
        return Q8(a * a + 2 * b * b + c * c + 2 * d * d, 2 * (a * b + c * d), 0, 0, self.den * self.den)

    def inverse(self) -> "Q8":
        if self.is_zero():
            raise ZeroDivisionError("Q8 division by zero")
        n = self.norm2()
        # 1 / (p + q r) = (p - q r) / (p^2 - 2 q^2), scaled by n.den
        p, q = n.a, n.b
        field_norm = p * p - 2 * q * q
        conj = self.conjugate()
        inv_n = Q8(p * n.den, -q * n.den, 0, 0, field_norm)
        return conj * inv_n

    def __truediv__(self, other: "Q8") -> "Q8":
        if not isinstance(other, Q8):
            other = Q8.coerce(other)
        return self * other.inverse()

    def is_real(self) -> bool:
        return self.c == 0 and self.d == 0

    def real(self) -> "Q8":
        return Q8(self.a, self.b, 0, 0, self.den)

    def imag(self) -> "Q8":
        return Q8(self.c, self.d, 0, 0, self.den)

    def sign(self) -> int:
        """Exact sign of a real element a + b*sqrt 2 (den > 0)."""
        if not self.is_real():
            raise NotReal("order is defined on Q(sqrt 2) only")
        a, b = self.a, self.b
        if b == 0:
            return (a > 0) - (a < 0)
        if a == 0:
            return (b > 0) - (b < 0)
        if (a > 0) == (b > 0):
            return 1 if a > 0 else -1
        left, right = a * a, 2 * b * b
        if left == right:
            return 0
        return (1 if a > 0 else -1) if left > right else (1 if b > 0 else -1)

    def __lt__(self, other: object) -> bool:
        return (self - Q8.coerce(other)).sign() < 0

    def __le__(self, other: object) -> bool:
        return (self - Q8.coerce(other)).sign() <= 0

    def __gt__(self, other: object) -> bool:
        return (self - Q8.coerce(other)).sign() > 0

    def __ge__(self, other: object) -> bool:
        return (self - Q8.coerce(other)).sign() >= 0

    def to_complex(self) -> complex:
        """One-way crossing into IEEE-754; never promoted back."""
        r = 2.0**0.5
        return complex((self.a + self.b * r) / self.den, (self.c + self.d * r) / self.den)

    def canonical(self) -> str:
        return f"{self.a},{self.b},{self.c},{self.d},{self.den}"


ZERO8 = Q8()
ONE8 = Q8(1)
I8 = Q8(0, 0, 1)
SQRT2_8 = Q8(0, 1)
INV_SQRT2_8 = Q8(0, 1, 0, 0, 2)
ZETA8_8 = Q8(0, 1, 0, 1, 2)


def zeta8_power(k: int) -> Q8:
    out = ONE8
    for _ in range(k % 8):
        out = out * ZETA8_8
    return out


__all__ = [
    "I8",
    "INV_SQRT2_8",
    "NotReal",
    "ONE8",
    "Q8",
    "SQRT2_8",
    "ZERO8",
    "ZETA8_8",
    "zeta8_power",
]
