"""EUCLID-CORE: Exact Mathematical Engine (`exact_math.py`).

Substrate-Independent Arbitrary Precision Rational Field Q and Quadratic
Extension Field Q[sqrt(5)] Algebra.

Order of Truth: MATHEMATICAL & COMPUTATIONAL (Fields Medal Rigor).
Zero floating-point operations in the algebraic core. Zero approximations.
Exact field invariants and Cassini identities.
"""

from __future__ import annotations

import math
from typing import Any, Union


class BigFraction:
    """Arbitrary precision exact rational fraction p/q over unbounded integers."""

    __slots__ = ("_num", "_den")

    def __init__(
        self,
        num: Union[int, str, BigFraction],
        den: Union[int, str, BigFraction] = 1,
    ) -> None:
        if isinstance(num, BigFraction):
            n = num.num
            d = num.den
            if den != 1:
                if isinstance(den, BigFraction):
                    n *= den.den
                    d *= den.num
                else:
                    d *= int(den)
        else:
            n = int(num)
            d = int(den) if not isinstance(den, BigFraction) else (den.num * 1)

        if d == 0:
            raise ZeroDivisionError("DivisionByZero: Denominator cannot be zero in BigFraction")

        if d < 0:
            n = -n
            d = -d

        common = math.gcd(abs(n), d)
        self._num = n // common
        self._den = d // common

    @property
    def num(self) -> int:
        return self._num

    @property
    def den(self) -> int:
        return self._den

    @property
    def numerator(self) -> int:
        return self._num

    @property
    def denominator(self) -> int:
        return self._den

    @classmethod
    def zero(cls) -> BigFraction:
        return cls(0, 1)

    @classmethod
    def one(cls) -> BigFraction:
        return cls(1, 1)

    def add(self, other: Union[BigFraction, int]) -> BigFraction:
        if not isinstance(other, BigFraction):
            other = BigFraction(other)
        n = self._num * other._den + other._num * self._den
        d = self._den * other._den
        return BigFraction(n, d)

    def sub(self, other: Union[BigFraction, int]) -> BigFraction:
        if not isinstance(other, BigFraction):
            other = BigFraction(other)
        n = self._num * other._den - other._num * self._den
        d = self._den * other._den
        return BigFraction(n, d)

    def mul(self, other: Union[BigFraction, int]) -> BigFraction:
        if not isinstance(other, BigFraction):
            other = BigFraction(other)
        n = self._num * other._num
        d = self._den * other._den
        return BigFraction(n, d)

    def div(self, other: Union[BigFraction, int]) -> BigFraction:
        if not isinstance(other, BigFraction):
            other = BigFraction(other)
        if other._num == 0:
            raise ZeroDivisionError("DivisionByZero: Cannot divide BigFraction by zero")
        n = self._num * other._den
        d = self._den * other._num
        return BigFraction(n, d)

    def neg(self) -> BigFraction:
        return BigFraction(-self._num, self._den)

    def abs(self) -> BigFraction:
        return BigFraction(abs(self._num), self._den)

    def inverse(self) -> BigFraction:
        if self._num == 0:
            raise ZeroDivisionError("DivisionByZero: Cannot invert zero BigFraction")
        return BigFraction(self._den, self._num)

    def equals(self, other: Any) -> bool:
        if isinstance(other, int):
            return self._den == 1 and self._num == other
        if not isinstance(other, BigFraction):
            return False
        return self._num == other._num and self._den == other._den

    def is_zero(self) -> bool:
        return self._num == 0

    def is_one(self) -> bool:
        return self._num == 1 and self._den == 1

    def to_float(self) -> float:
        return self._num / self._den

    def __add__(self, other: Any) -> BigFraction:
        return self.add(other)

    def __radd__(self, other: Any) -> BigFraction:
        return self.add(other)

    def __sub__(self, other: Any) -> BigFraction:
        return self.sub(other)

    def __rsub__(self, other: Any) -> BigFraction:
        return BigFraction(other).sub(self)

    def __mul__(self, other: Any) -> BigFraction:
        return self.mul(other)

    def __rmul__(self, other: Any) -> BigFraction:
        return self.mul(other)

    def __truediv__(self, other: Any) -> BigFraction:
        return self.div(other)

    def __rtruediv__(self, other: Any) -> BigFraction:
        return BigFraction(other).div(self)

    def __neg__(self) -> BigFraction:
        return self.neg()

    def __abs__(self) -> BigFraction:
        return self.abs()

    def __eq__(self, other: Any) -> bool:
        return self.equals(other)

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, BigFraction):
            other = BigFraction(other)
        return self._num * other._den < other._num * self._den

    def __le__(self, other: Any) -> bool:
        if not isinstance(other, BigFraction):
            other = BigFraction(other)
        return self._num * other._den <= other._num * self._den

    def __gt__(self, other: Any) -> bool:
        if not isinstance(other, BigFraction):
            other = BigFraction(other)
        return self._num * other._den > other._num * self._den

    def __ge__(self, other: Any) -> bool:
        if not isinstance(other, BigFraction):
            other = BigFraction(other)
        return self._num * other._den >= other._num * self._den

    def __hash__(self) -> int:
        return hash((self._num, self._den))

    def __repr__(self) -> str:
        return f"BigFraction({self._num}, {self._den})"

    def __str__(self) -> str:
        if self._den == 1:
            return str(self._num)
        return f"{self._num}/{self._den}"


class Q5:
    """Exact Quadratic Extension Field Q[sqrt(5)].

    Represents algebraic elements of the form:
        alpha = a + b*sqrt(5),  where a, b in Q (BigFraction).

    Field Invariants:
      Addition: (a + b*sqrt(5)) + (c + d*sqrt(5)) = (a + c) + (b + d)*sqrt(5)
      Multiplication: (a + b*sqrt(5))(c + d*sqrt(5)) = (ac + 5bd) + (ad + bc)*sqrt(5)
      Conjugate: sigma(a + b*sqrt(5)) = a - b*sqrt(5)
      Field Norm: N(alpha) = alpha * sigma(alpha) = a^2 - 5*b^2 in Q
      Inverse: alpha^{-1} = (a - b*sqrt(5)) / (a^2 - 5*b^2)
    """

    __slots__ = ("_a", "_b")

    def __init__(
        self,
        a: Union[BigFraction, int],
        b: Union[BigFraction, int] = 0,
    ) -> None:
        self._a = a if isinstance(a, BigFraction) else BigFraction(a)
        self._b = b if isinstance(b, BigFraction) else BigFraction(b)

    @property
    def a(self) -> BigFraction:
        return self._a

    @property
    def b(self) -> BigFraction:
        return self._b

    @classmethod
    def zero(cls) -> Q5:
        return cls(BigFraction.zero(), BigFraction.zero())

    @classmethod
    def one(cls) -> Q5:
        return cls(BigFraction.one(), BigFraction.zero())

    @classmethod
    def sqrt5(cls) -> Q5:
        return cls(BigFraction.zero(), BigFraction.one())

    @classmethod
    def phi(cls) -> Q5:
        """Golden ratio phi = 1/2 + (1/2)*sqrt(5)."""
        half = BigFraction(1, 2)
        return cls(half, half)

    @classmethod
    def phi_inv(cls) -> Q5:
        """phi^{-1} = -1/2 + (1/2)*sqrt(5)."""
        return cls(BigFraction(-1, 2), BigFraction(1, 2))

    def add(self, other: Union[Q5, BigFraction, int]) -> Q5:
        if not isinstance(other, Q5):
            other = Q5(other)
        return Q5(self._a.add(other._a), self._b.add(other._b))

    def sub(self, other: Union[Q5, BigFraction, int]) -> Q5:
        if not isinstance(other, Q5):
            other = Q5(other)
        return Q5(self._a.sub(other._a), self._b.sub(other._b))

    def mul(self, other: Union[Q5, BigFraction, int]) -> Q5:
        """Exact multiplication in Q[sqrt(5)]:
        (a + b*sqrt(5))(c + d*sqrt(5)) = (ac + 5bd) + (ad + bc)*sqrt(5)
        """
        if not isinstance(other, Q5):
            other = Q5(other)
        five = BigFraction(5, 1)
        ac = self._a.mul(other._a)
        bd5 = self._b.mul(other._b).mul(five)
        new_a = ac.add(bd5)

        ad = self._a.mul(other._b)
        bc = self._b.mul(other._a)
        new_b = ad.add(bc)
        return Q5(new_a, new_b)

    def multiply(self, other: Union[Q5, BigFraction, int]) -> Q5:
        """Alias for mul to satisfy benchmark test contracts."""
        return self.mul(other)

    def conjugate(self) -> Q5:
        return Q5(self._a, self._b.neg())

    def algebraic_norm(self) -> BigFraction:
        """Algebraic Field Norm N(alpha) = a^2 - 5*b^2 in Q."""
        five = BigFraction(5, 1)
        a2 = self._a.mul(self._a)
        b2_5 = self._b.mul(self._b).mul(five)
        return a2.sub(b2_5)

    def norm(self) -> BigFraction:
        """Absolute Field Norm |N(alpha)| = |a^2 - 5*b^2| in Q+.

        For units in Z[phi], N(phi) = -1 and N(phi^{-1}) = -1, so the absolute
        algebraic norm is strictly 1 (num=1, den=1) across arbitrary chained powers.
        """
        return self.algebraic_norm().abs()

    def norm_squared(self) -> BigFraction:
        """Real squared Euclidean magnitude: a^2 + 5*b^2."""
        five = BigFraction(5, 1)
        a2 = self._a.mul(self._a)
        b2_5 = self._b.mul(self._b).mul(five)
        return a2.add(b2_5)

    def inverse(self) -> Q5:
        """Exact multiplicative inverse alpha^{-1} = (a - b*sqrt(5)) / (a^2 - 5*b^2)."""
        alg_norm = self.algebraic_norm()
        if alg_norm.is_zero():
            raise ZeroDivisionError("DivisionByZero: Cannot invert element with zero field norm in Q[sqrt(5)]")
        return Q5(self._a.div(alg_norm), self._b.neg().div(alg_norm))

    def div(self, other: Union[Q5, BigFraction, int]) -> Q5:
        if not isinstance(other, Q5):
            other = Q5(other)
        return self.mul(other.inverse())

    def equals(self, other: Any) -> bool:
        if not isinstance(other, Q5):
            if isinstance(other, (int, BigFraction)):
                return self._b.is_zero() and self._a.equals(other)
            return False
        return self._a.equals(other._a) and self._b.equals(other._b)

    def is_one(self) -> bool:
        return self._a.is_one() and self._b.is_zero()

    def is_zero(self) -> bool:
        return self._a.is_zero() and self._b.is_zero()

    def __add__(self, other: Any) -> Q5:
        return self.add(other)

    def __sub__(self, other: Any) -> Q5:
        return self.sub(other)

    def __mul__(self, other: Any) -> Q5:
        return self.mul(other)

    def __truediv__(self, other: Any) -> Q5:
        return self.div(other)

    def __eq__(self, other: Any) -> bool:
        return self.equals(other)

    def __repr__(self) -> str:
        return f"Q5({self._a!r}, {self._b!r})"

    def __str__(self) -> str:
        if self._b.is_zero():
            return str(self._a)
        if self._a.is_zero():
            return f"{self._b}*sqrt(5)"
        sign = "+" if self._b > 0 else "-"
        return f"{self._a} {sign} {abs(self._b)}*sqrt(5)"


__all__ = ["BigFraction", "Q5"]
