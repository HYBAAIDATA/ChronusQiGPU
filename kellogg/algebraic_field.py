"""Exact rational cyclotomic fields with explicit conductor embeddings.

Polynomial residues modulo Phi_m define Q(zeta_m). No floating conversion,
root approximation or dependency on symbolic-expression zero tests is used.
The conductor bound is an admission limit, not a change in field semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from math import lcm


def _trim(p):
    while p and p[-1] == 0:
        p.pop()
    return p


def _add(a, b):
    return _trim(
        [
            (a[i] if i < len(a) else 0) + (b[i] if i < len(b) else 0)
            for i in range(max(len(a), len(b)))
        ]
    )


def _mul(a, b):
    out = [Fraction(0)] * max(0, len(a) + len(b) - 1)
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            out[i + j] += x * y
    return _trim(out)


def _divmod(a, b):
    a = _trim(list(a))
    b = _trim(list(b))
    if not b:
        raise ZeroDivisionError("zero polynomial")
    q = [Fraction(0)] * max(0, len(a) - len(b) + 1)
    while len(a) >= len(b):
        k, factor = len(a) - len(b), a[-1] / b[-1]
        q[k] = factor
        for j, x in enumerate(b):
            a[j + k] -= factor * x
        _trim(a)
    return _trim(q), a


@lru_cache(maxsize=256)
def cyclotomic_polynomial(order: int) -> tuple[Fraction, ...]:
    if type(order) is not int or not 1 <= order <= 256:
        raise ValueError("cyclotomic conductor must be an integer in 1..256")
    p = [Fraction(-1)] + [Fraction(0)] * (order - 1) + [Fraction(1)]
    for divisor in range(1, order):
        if order % divisor == 0:
            p, remainder = _divmod(p, cyclotomic_polynomial(divisor))
            if remainder:
                raise ArithmeticError("nonintegral cyclotomic factorization")
    return tuple(p)


@dataclass(frozen=True)
class Cyclotomic:
    order: int
    coefficients: tuple[Fraction, ...] = ()

    def __post_init__(self):
        modulus = cyclotomic_polynomial(self.order)
        if any(type(v) is not int and not isinstance(v, Fraction) for v in self.coefficients):
            raise TypeError("cyclotomic coefficients must be exact rationals")
        _, reduced = _divmod([Fraction(v) for v in self.coefficients], modulus)
        object.__setattr__(self, "coefficients", tuple(reduced))

    @classmethod
    def root(cls, order):
        return cls(order, (0, 1))

    def embed(self, order):
        cyclotomic_polynomial(order)
        if order % self.order:
            raise ValueError("embedding requires a multiple of the source conductor")
        step = order // self.order
        coefficients = [Fraction(0)] * (step * max(0, len(self.coefficients) - 1) + 1)
        for i, value in enumerate(self.coefficients):
            coefficients[i * step] = value
        return Cyclotomic(order, tuple(coefficients))

    def _pair(self, other):
        if type(other) is int or isinstance(other, Fraction):
            other = Cyclotomic(self.order, (other,))
        if not isinstance(other, Cyclotomic):
            raise TypeError("operand must belong to an exact cyclotomic field")
        order = lcm(self.order, other.order)
        return self.embed(order), other.embed(order)

    def __add__(self, other):
        a, b = self._pair(other)
        return Cyclotomic(a.order, tuple(_add(a.coefficients, b.coefficients)))

    __radd__ = __add__

    def __neg__(self):
        return Cyclotomic(self.order, tuple(-v for v in self.coefficients))

    def __sub__(self, other):
        a, b = self._pair(other)
        return a + -b

    def __mul__(self, other):
        a, b = self._pair(other)
        return Cyclotomic(a.order, tuple(_mul(a.coefficients, b.coefficients)))

    __rmul__ = __mul__

    def inverse(self):
        if not self.coefficients:
            raise ZeroDivisionError("zero field element")
        old_r, r = list(cyclotomic_polynomial(self.order)), list(self.coefficients)
        old_s, s = [], [Fraction(1)]
        while r:
            quotient, remainder = _divmod(old_r, r)
            old_r, r = r, remainder
            old_s, s = s, _add(old_s, [-v for v in _mul(quotient, s)])
        if len(old_r) != 1:
            raise ArithmeticError("cyclotomic modulus is not irreducible")
        return Cyclotomic(self.order, tuple(v / old_r[0] for v in old_s))

    def __truediv__(self, other):
        a, b = self._pair(other)
        return a * b.inverse()

    def __pow__(self, exponent):
        if type(exponent) is not int:
            raise TypeError("exponent must be integer")
        base = self if exponent >= 0 else self.inverse()
        result = Cyclotomic(self.order, (1,))
        exponent = abs(exponent)
        while exponent:
            if exponent & 1:
                result = result * base
            base = base * base
            exponent >>= 1
        return result

    def conjugate(self):
        inverse_root = Cyclotomic.root(self.order) ** (self.order - 1)
        result = Cyclotomic(self.order)
        for value in reversed(self.coefficients):
            result = result * inverse_root + value
        return result

    def is_zero(self):
        return not self.coefficients

    def same_value(self, other):
        a, b = self._pair(other)
        return a.coefficients == b.coefficients

    def to_dict(self):
        return {
            "conductor": self.order,
            "coefficients": [[v.numerator, v.denominator] for v in self.coefficients],
        }

    @classmethod
    def from_zphi(cls, a: int, b: int, *, order: int = 40):
        if type(a) is not int or type(b) is not int or order % 5:
            raise ValueError("golden embedding requires integers and conductor divisible by five")
        root = cls.root(5).embed(order)
        return a + b * (1 + root + root.conjugate())

    @classmethod
    def from_q8(cls, value, *, order: int = 8):
        from .cyclotomic import Q8

        if not isinstance(value, Q8) or order % 8:
            raise ValueError("Q8 embedding requires a conductor divisible by eight")
        root = cls.root(8).embed(order)
        sqrt2, imaginary = root + root.conjugate(), root**2
        return (value.a + value.b * sqrt2 + imaginary * (value.c + value.d * sqrt2)) / value.den
