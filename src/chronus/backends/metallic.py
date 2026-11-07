"""Exact arithmetic over the metallic means family Z[sigma_m].

The m-th metallic mean sigma_m = (m + sqrt(m^2 + 4)) / 2 is the PV root of
x^2 = m*x + 1; its conjugate has absolute value 1/sigma_m < 1, so powers
contract onto exact integers exactly as phi does for m = 1. Elements are
(a + b*sigma_m) / denominator with integer coefficients; multiplication uses
the fold rule sigma_m^2 = m*sigma_m + 1 with zero floating point:

    (a + b*s)(c + d*s) = (a*c + b*d) + (a*d + b*c + m*b*d)*s

m = 1 golden, m = 2 silver, m = 3 bronze. Trace and norm:
    Tr(a + b*s) = 2a + m*b,   N(a + b*s) = a^2 + m*a*b - b^2
"""

from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class MetallicElement:
    """An element (a + b*sigma_m) / denominator of the m-th metallic ring."""

    m: int
    a: int
    b: int
    denominator: int = 1

    def __post_init__(self):
        if not isinstance(self.m, int) or isinstance(self.m, bool) or self.m < 1:
            raise ValueError("metallic index m must be a positive integer")
        if any(
            not isinstance(v, int) or isinstance(v, bool)
            for v in (self.a, self.b, self.denominator)
        ):
            raise TypeError("coefficients must be integers")
        if self.denominator <= 0:
            raise ValueError("denominator must be positive")

    def multiply(self, other: "MetallicElement") -> "MetallicElement":
        if other.m != self.m:
            raise ValueError("cannot multiply elements of different metallic rings")
        m = self.m
        return MetallicElement(
            m,
            self.a * other.a + self.b * other.b,
            self.a * other.b + self.b * other.a + m * self.b * other.b,
            self.denominator * other.denominator,
        )

    def trace(self) -> Fraction:
        return Fraction(2 * self.a + self.m * self.b, self.denominator)

    def norm(self) -> Fraction:
        m = self.m
        return Fraction(
            self.a * self.a + m * self.a * self.b - self.b * self.b,
            self.denominator * self.denominator,
        )


def metallic_power(m: int, order: int) -> MetallicElement:
    """Return sigma_m**order as exact integer coefficients by fast doubling."""
    if not isinstance(order, int) or isinstance(order, bool) or order < 0:
        raise ValueError("order must be a non-negative integer")
    result, base = MetallicElement(m, 1, 0), MetallicElement(m, 0, 1)
    while order:
        if order & 1:
            result = result.multiply(base)
        order >>= 1
        if order:
            base = base.multiply(base)
    return result


def metallic_sequence(m: int, order: int) -> int:
    """The m-th metallic trace sequence value T_n = sigma_m^n + psi_m^n.

    Satisfies T_n = m*T_{n-1} + T_{n-2} with T_0 = 2, T_1 = m; for m = 1
    these are the Lucas numbers.
    """
    return metallic_power(m, order).trace().numerator  # denominator is 1
