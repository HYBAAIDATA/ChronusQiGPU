"""Exact closed algebraic field for the TURING VQC backend layer.

The field is ``Q(sqrt(2)) + i*Q(sqrt(2))``.  It is *closed* under the standard
universal Clifford+T gate set:

    H  = 1/sqrt(2) * [[1, 1], [1, -1]]
    S  = diag(1, i)
    T  = diag(1, (1 + i)/sqrt(2))
    X, Y, Z, CNOT, CZ, SWAP

Every entry of every gate above lies in this field, and the field is closed
under addition and multiplication, so a state prepared from ``|0...0>`` by any
Clifford+T circuit has amplitudes in this field with **zero floating-point
error at every step**.  That is what lets this layer assert exactness rather
than approximate it: there is no tolerance anywhere in the arithmetic, only
``Fraction`` comparison.

Comparison is exact too.  ``Q(sqrt(2))`` is an ordered field embedded in the
reals, and :meth:`Q2.sign` decides the sign of ``p + q*sqrt(2)`` by comparing
``p**2`` against ``2*q**2``, so Born-probability ordering and cumulative
measurement thresholds never round.

This module depends only on the standard library.  It deliberately does *not*
import the sympy-backed ``exact_field`` module that ships in the parent
package: the backend layer must stay importable, testable and verifiable even
when the heavy symbolic stack is absent.
"""

from __future__ import annotations

import math
from fractions import Fraction

__all__ = ["Q2", "Exact", "ZERO", "ONE", "I", "SQRT2_HALF"]


class Q2:
    """An exact element ``p + q*sqrt(2)`` of ``Q(sqrt(2))``."""

    __slots__ = ("p", "q")

    def __init__(self, p: int | Fraction = 0, q: int | Fraction = 0) -> None:
        self.p = Fraction(p)
        self.q = Fraction(q)

    # -- arithmetic ---------------------------------------------------------
    def __add__(self, other: "Q2") -> "Q2":
        return Q2(self.p + other.p, self.q + other.q)

    def __sub__(self, other: "Q2") -> "Q2":
        return Q2(self.p - other.p, self.q - other.q)

    def __neg__(self) -> "Q2":
        return Q2(-self.p, -self.q)

    def __mul__(self, other: "Q2") -> "Q2":
        # (p1 + q1*r)(p2 + q2*r) = p1*p2 + 2*q1*q2 + (p1*q2 + q1*p2)*r,  r = sqrt(2)
        return Q2(
            self.p * other.p + 2 * self.q * other.q,
            self.p * other.q + self.q * other.p,
        )

    def inverse(self) -> "Q2":
        # 1/(p + q*r) = (p - q*r) / (p^2 - 2*q^2)
        denom = self.p * self.p - 2 * self.q * self.q
        if denom == 0:
            raise ZeroDivisionError("Q2 element is not invertible (norm is zero)")
        return Q2(self.p / denom, -self.q / denom)

    def __truediv__(self, other: "Q2") -> "Q2":
        return self * other.inverse()

    def is_zero(self) -> bool:
        return self.p == 0 and self.q == 0

    def sign(self) -> int:
        """Exact sign of ``p + q*sqrt(2)`` as -1, 0 or +1."""
        if self.q == 0:
            return (self.p > 0) - (self.p < 0)
        if self.p == 0:
            return (self.q > 0) - (self.q < 0)
        if self.p > 0 and self.q > 0:
            return 1
        if self.p < 0 and self.q < 0:
            return -1
        # Opposite signs: compare p^2 against 2*q^2.
        t = self.p * self.p - 2 * self.q * self.q
        t_sign = (t > 0) - (t < 0)
        return t_sign if self.p > 0 else -t_sign

    def approx(self) -> float:
        return float(self.p) + float(self.q) * math.sqrt(2.0)

    # -- protocol -----------------------------------------------------------
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Q2):
            return NotImplemented
        return self.p == other.p and self.q == other.q

    def __hash__(self) -> int:
        return hash((self.p, self.q))

    def __bool__(self) -> bool:
        return not self.is_zero()

    @staticmethod
    def _term(coeff: Fraction, radical: bool) -> str:
        if coeff == 1:
            body = "√2" if radical else "1"
        elif coeff == -1:
            body = "-√2" if radical else "-1"
        else:
            body = f"{coeff}√2" if radical else f"{coeff}"
        return body

    def __repr__(self) -> str:
        if self.q == 0:
            return Q2._term(self.p, False)
        if self.p == 0:
            return Q2._term(self.q, True)
        if self.q > 0:
            return f"{Q2._term(self.p, False)} + {Q2._term(self.q, True)}"
        return f"{Q2._term(self.p, False)} - {Q2._term(-self.q, True)}"

    __str__ = __repr__


class Exact:
    """An exact element ``re + im*i`` with ``re, im`` in ``Q(sqrt(2))``."""

    __slots__ = ("re", "im")

    def __init__(self, re: Q2 | int | Fraction = Q2(), im: Q2 | int | Fraction = Q2()) -> None:
        self.re = re if isinstance(re, Q2) else Q2(re)
        self.im = im if isinstance(im, Q2) else Q2(im)

    def __add__(self, other: "Exact") -> "Exact":
        return Exact(self.re + other.re, self.im + other.im)

    def __sub__(self, other: "Exact") -> "Exact":
        return Exact(self.re - other.re, self.im - other.im)

    def __neg__(self) -> "Exact":
        return Exact(-self.re, -self.im)

    def __mul__(self, other: "Exact") -> "Exact":
        # (a + bi)(c + di) = (ac - bd) + (ad + bc)i
        return Exact(
            self.re * other.re - self.im * other.im,
            self.re * other.im + self.im * other.re,
        )

    def conjugate(self) -> "Exact":
        return Exact(self.re, -self.im)

    def norm_sq(self) -> Q2:
        """``|z|^2``, exact, landing back in ``Q(sqrt(2))``."""
        return self.re * self.re + self.im * self.im

    def is_zero(self) -> bool:
        return self.re.is_zero() and self.im.is_zero()

    def approx(self) -> complex:
        return complex(self.re.approx(), self.im.approx())

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Exact):
            return NotImplemented
        return self.re == other.re and self.im == other.im

    def __hash__(self) -> int:
        return hash((self.re, self.im))

    def __bool__(self) -> bool:
        return not self.is_zero()

    def __repr__(self) -> str:
        if self.im.is_zero():
            return repr(self.re)
        if self.re.is_zero():
            if self.im == Q2(1):
                return "i"
            if self.im == Q2(-1):
                return "-i"
            return f"{self.im}i"
        if self.im.sign() > 0:
            return f"{self.re} + {self.im}i"
        return f"{self.re} - {(-self.im)}i"

    __str__ = __repr__


ZERO = Exact()
ONE = Exact(Q2(1))
I = Exact(Q2(0), Q2(1))
SQRT2_HALF = Q2(0, Fraction(1, 2))  # 1/sqrt(2)
