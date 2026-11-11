"""The exact scalar fields used by every routine in :mod:`turing.tensor`.

A field is any object with the small protocol :class:`Field`: the constants
``zero`` and ``one`` and the methods ``from_int``, ``coerce``, ``add``, ``sub``,
``neg``, ``mul``, ``div`` (exact division by a nonzero element), ``is_zero``,
``eq`` and ``conj`` (complex conjugation). Every tensor, factorisation and
matrix-product routine in this package performs its arithmetic through these
methods only, so the same code runs over any exact field.

Two fields are provided:

* :data:`QQ`, the rationals, with :class:`fractions.Fraction` elements;
* :func:`cyclotomic` (n), the cyclotomic field Q(zeta_n), with elements of
  :class:`turing.algebra.CyclotomicElement` (exact rational coordinates in the
  power basis, reduced modulo the n-th cyclotomic polynomial).

There is no floating point anywhere: ``coerce`` accepts Python ints,
Fractions and field elements only and refuses floats with ``TypeError``.
"""

from __future__ import annotations

import operator
from fractions import Fraction
from math import gcd, isqrt
from typing import Any, Optional, Protocol, runtime_checkable

from ..algebra.cyclotomic import CyclotomicElement, CyclotomicField, factorize

__all__ = [
    "QQ",
    "CyclotomicNumberField",
    "Field",
    "RationalField",
    "cyclotomic",
]


@runtime_checkable
class Field(Protocol):
    """Structural type of an exact field (duck typing; no base class is required)."""

    zero: Any
    one: Any

    def from_int(self, value: int) -> Any: ...

    def coerce(self, value: object) -> Any: ...

    def add(self, a: Any, b: Any) -> Any: ...

    def sub(self, a: Any, b: Any) -> Any: ...

    def neg(self, a: Any) -> Any: ...

    def mul(self, a: Any, b: Any) -> Any: ...

    def div(self, a: Any, b: Any) -> Any: ...

    def is_zero(self, a: Any) -> bool: ...

    def eq(self, a: Any, b: Any) -> bool: ...

    def conj(self, a: Any) -> Any: ...


def _check_int(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an int, got {type(value).__name__}")
    return value


def _division(a: Any, b: Any) -> Any:
    if not b:
        raise ZeroDivisionError("exact division by zero")
    return a / b


def _check_positive_int(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{name} must be a positive int, got {value!r}")
    return value


_conjugate = operator.methodcaller("conjugate")


class RationalField:
    """The field Q of rational numbers; elements are :class:`fractions.Fraction`."""

    __slots__ = ()
    _instance = None

    zero = Fraction(0)
    one = Fraction(1)
    add = staticmethod(operator.add)
    sub = staticmethod(operator.sub)
    neg = staticmethod(operator.neg)
    mul = staticmethod(operator.mul)
    div = staticmethod(_division)
    is_zero = staticmethod(operator.not_)
    eq = staticmethod(operator.eq)
    conj = staticmethod(_conjugate)

    def __new__(cls) -> "RationalField":
        if cls._instance is None:
            cls._instance = object.__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "QQ"

    def __reduce__(self):
        return (RationalField, ())

    def from_int(self, value: int) -> Fraction:
        return Fraction(_check_int(value, "value"))

    def coerce(self, value: object) -> Fraction:
        """Return ``value`` as an element of Q: an int, a Fraction or a rational CyclotomicElement.

        Floats, bools and every other type are refused with TypeError.
        """
        if type(value) is Fraction:
            return value
        if isinstance(value, int) and not isinstance(value, bool):
            return Fraction(value)
        if isinstance(value, Fraction):
            return Fraction(value.numerator, value.denominator)
        if isinstance(value, CyclotomicElement) and value.is_rational():
            return value.to_rational()
        raise TypeError(f"an element of Q must be an int or a fractions.Fraction, got {type(value).__name__}")

    def positive_sqrt(self, value: int) -> Optional[Fraction]:
        """The positive square root of a positive integer if it is rational, else None."""
        _check_positive_int(value, "value")
        root = isqrt(value)
        return Fraction(root) if root * root == value else None


QQ = RationalField()


class CyclotomicNumberField:
    """The cyclotomic field Q(zeta_n) in the protocol of :class:`Field`.

    Backed by :class:`turing.algebra.CyclotomicField`; obtain instances with
    :func:`cyclotomic`, so that ``cyclotomic(8) is cyclotomic(8)``.
    """

    __slots__ = ("_algebra", "_order", "zero", "one")

    add = staticmethod(operator.add)
    sub = staticmethod(operator.sub)
    neg = staticmethod(operator.neg)
    mul = staticmethod(operator.mul)
    div = staticmethod(_division)
    is_zero = staticmethod(operator.not_)
    eq = staticmethod(operator.eq)
    conj = staticmethod(_conjugate)

    def __init__(self, n: int) -> None:
        algebra = CyclotomicField(n)
        self._algebra = algebra
        self._order = algebra.n
        self.zero = algebra.zero
        self.one = algebra.one

    def __repr__(self) -> str:
        return f"cyclotomic({self._order})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CyclotomicNumberField):
            return self._order == other._order
        return NotImplemented

    def __hash__(self) -> int:
        return hash(("cyclotomic", self._order))

    def __reduce__(self):
        return (cyclotomic, (self._order,))

    @property
    def order(self) -> int:
        """The n of Q(zeta_n)."""
        return self._order

    @property
    def algebra(self) -> CyclotomicField:
        """The underlying :class:`turing.algebra.CyclotomicField`."""
        return self._algebra

    def from_int(self, value: int) -> CyclotomicElement:
        return self._algebra.from_rational(_check_int(value, "value"))

    def coerce(self, value: object) -> CyclotomicElement:
        """Return ``value`` in Q(zeta_n): ints, Fractions, or elements of a subfield Q(zeta_m) with m | n."""
        if isinstance(value, CyclotomicElement):
            if value.field is self._algebra:
                return value
            if self._order % value.field.n:
                raise ValueError(f"{value!r} lies in Q(zeta_{value.field.n}), which this representation of "
                                 f"Q(zeta_{self._order}) does not contain; use cyclotomic(lcm)")
            return self._algebra.lift(value)
        if isinstance(value, Fraction) or (isinstance(value, int) and not isinstance(value, bool)):
            return self._algebra.from_rational(value)
        raise TypeError(f"an element of Q(zeta_{self._order}) must be an int, a fractions.Fraction or a "
                        f"CyclotomicElement, got {type(value).__name__}")

    def zeta(self, power: int = 1) -> CyclotomicElement:
        """zeta_n ** power, exactly."""
        return self._algebra.zeta(_check_int(power, "power") % self._order)

    def root_of_unity(self, order: int, power: int = 1) -> CyclotomicElement:
        """Return zeta_order ** power, or raise ValueError if this field does not contain it.

        Q(zeta_n) contains a primitive m-th root of unity exactly when m divides
        n, or n is odd and m divides 2n (then zeta_2n = -zeta_n^((n + 1) / 2)).
        """
        _check_int(order, "order")
        _check_int(power, "power")
        if order < 1:
            raise ValueError(f"the order of a root of unity must be positive, got {order}")
        common = gcd(order, power % order)
        primitive = order // common
        reduced = (power % order) // common
        n = self._order
        if n % primitive == 0:
            return self._algebra.zeta(reduced * (n // primitive) % n)
        if n % 2 and (2 * n) % primitive == 0:
            exponent = reduced * (2 * n // primitive)
            value = self._algebra.zeta(exponent * ((n + 1) // 2) % n)
            return -value if exponent % 2 else value
        raise ValueError(f"Q(zeta_{n}) does not contain a primitive {primitive}-th root of unity; "
                         f"use cyclotomic({n * primitive // gcd(n, primitive)})")

    def positive_sqrt(self, value: int) -> Optional[CyclotomicElement]:
        """The positive real square root of a positive integer as an element of Q(zeta_n), or None.

        Write value = s^2 * m with m squarefree. sqrt(m) lies in Q(zeta_n) exactly
        when the conductor of Q(sqrt(m)) (m if m = 1 mod 4, else 4m) divides n
        (2n when n is odd). It is then built from quadratic Gauss sums
        g_p = sum_a (a/p) zeta_p^a, which equal sqrt(p) for p = 1 mod 4 and
        i * sqrt(p) for p = 3 mod 4 with the standard embedding
        zeta_n = exp(2 pi i / n), and from sqrt(2) = zeta_8 + zeta_8^-1. Only the
        primes dividing n are tried, so no general factorisation is needed.
        """
        _check_positive_int(value, "value")
        root = isqrt(value)
        if root * root == value:
            return self.from_int(root)
        n = self._order
        span = n if n % 2 == 0 else 2 * n
        square, free, rest = 1, 1, value
        for p in factorize(span):
            exponent = 0
            while rest % p == 0:
                rest //= p
                exponent += 1
            square *= p ** (exponent // 2)
            if exponent % 2:
                free *= p
        cofactor = isqrt(rest)
        if cofactor * cofactor != rest:
            return None
        square *= cofactor
        conductor = free if free % 4 == 1 else 4 * free
        if span % conductor:
            return None
        result = self.one
        three_mod_four = 0
        for p in factorize(free):
            if p == 2:
                term = self.root_of_unity(8, 1) + self.root_of_unity(8, -1)
            else:
                term = self.zero
                for a in range(1, p):
                    symbol = pow(a, (p - 1) // 2, p)
                    root_term = self.root_of_unity(p, a)
                    term = term + root_term if symbol == 1 else term - root_term
                if p % 4 == 3:
                    three_mod_four += 1
            result = result * term
        result = result * self.root_of_unity(4, -three_mod_four)
        return result * square


_CYCLOTOMIC: dict[int, CyclotomicNumberField] = {}


def cyclotomic(n: int) -> CyclotomicNumberField:
    """The field Q(zeta_n) (one shared instance per n)."""
    _check_int(n, "n")
    if n < 1:
        raise ValueError(f"n must be a positive integer, got {n}")
    field = _CYCLOTOMIC.get(n)
    if field is None:
        field = CyclotomicNumberField(n)
        _CYCLOTOMIC[n] = field
    return field
