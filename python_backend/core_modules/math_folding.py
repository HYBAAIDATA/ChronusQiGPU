"""Exact Zeckendorf, Binet, Cassini, PULVINI, and Pisot-Lucas contracts.

This module is the CPU exact-arithmetic reference. It contains no IEEE-754
sequence generation and makes no hardware-performance claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable

from chronus.mla1517.core import fib, lucas, zeckendorf, zeckendorf_decode


@dataclass(frozen=True)
class Quadratic5:
    """Exact element ``a + b*sqrt(5)`` over the rational field."""

    rational: Fraction = Fraction(0)
    sqrt5: Fraction = Fraction(0)

    def __add__(self, other: "Quadratic5") -> "Quadratic5":
        return Quadratic5(
            self.rational + other.rational,
            self.sqrt5 + other.sqrt5,
        )

    def __sub__(self, other: "Quadratic5") -> "Quadratic5":
        return Quadratic5(
            self.rational - other.rational,
            self.sqrt5 - other.sqrt5,
        )

    def __mul__(self, other: "Quadratic5") -> "Quadratic5":
        return Quadratic5(
            self.rational * other.rational + 5 * self.sqrt5 * other.sqrt5,
            self.rational * other.sqrt5 + self.sqrt5 * other.rational,
        )

    def inverse(self) -> "Quadratic5":
        norm = self.rational * self.rational - 5 * self.sqrt5 * self.sqrt5
        if norm == 0:
            raise ZeroDivisionError("zero algebraic norm")
        return Quadratic5(self.rational / norm, -self.sqrt5 / norm)

    def __pow__(self, exponent: int) -> "Quadratic5":
        if not isinstance(exponent, int):
            raise TypeError("exponent must be an integer")
        if exponent < 0:
            return self.inverse() ** (-exponent)
        result = Quadratic5(Fraction(1), Fraction(0))
        base = self
        power = exponent
        while power:
            if power & 1:
                result = result * base
            base = base * base
            power >>= 1
        return result

    def sign(self) -> int:
        """Return the exact real-embedding sign without evaluating sqrt(5)."""
        a, b = self.rational, self.sqrt5
        if b == 0:
            return (a > 0) - (a < 0)
        if a == 0:
            return (b > 0) - (b < 0)
        if a > 0 and b > 0:
            return 1
        if a < 0 and b < 0:
            return -1
        comparison = a * a - 5 * b * b
        if comparison == 0:
            return 0
        if a > 0:
            return 1 if comparison > 0 else -1
        return -1 if comparison > 0 else 1


PHI = Quadratic5(Fraction(1, 2), Fraction(1, 2))
PSI = Quadratic5(Fraction(1, 2), Fraction(-1, 2))
SQRT5 = Quadratic5(Fraction(0), Fraction(1))


def fibonacci_binet(n: int) -> int:
    """Return exact ``F_n`` through algebraic Binet evaluation."""
    if not isinstance(n, int) or n < 0:
        raise ValueError("n must be a non-negative integer")
    numerator = PHI**n - PSI**n
    quotient = numerator * SQRT5.inverse()
    if quotient.sqrt5 != 0 or quotient.rational.denominator != 1:
        raise ArithmeticError("Binet result did not collapse to an integer")
    return quotient.rational.numerator


def lucas_binet(n: int) -> int:
    """Return exact ``L_n`` through algebraic Binet evaluation."""
    if not isinstance(n, int) or n < 0:
        raise ValueError("n must be a non-negative integer")
    value = PHI**n + PSI**n
    if value.sqrt5 != 0 or value.rational.denominator != 1:
        raise ArithmeticError("Lucas Binet result did not collapse to an integer")
    return value.rational.numerator


def fibonacci_cassini(n: int) -> int:
    if not isinstance(n, int) or n < 1:
        raise ValueError("n must be at least one")
    return fib(n - 1) * fib(n + 1) - fib(n) ** 2


def lucas_cassini(n: int) -> int:
    if not isinstance(n, int) or n < 1:
        raise ValueError("n must be at least one")
    return lucas(n - 1) * lucas(n + 1) - lucas(n) ** 2


def verify_cassini(n: int) -> bool:
    return fibonacci_cassini(n) == (-1) ** n and lucas_cassini(n) == 5 * ((-1) ** (n - 1))


@dataclass(frozen=True)
class ZeckendorfAddress:
    linear_index: int
    mask: int
    fibonacci_indices: tuple[int, ...]

    @property
    def non_adjacent(self) -> bool:
        return (self.mask & (self.mask << 1)) == 0

    def verify(self) -> bool:
        return (
            self.linear_index >= 0
            and self.non_adjacent
            and zeckendorf_decode(self.mask) == self.linear_index
        )


def zeckendorf_address(index: int) -> ZeckendorfAddress:
    mask, indices = zeckendorf(index)
    address = ZeckendorfAddress(index, mask, indices)
    if not address.verify():
        raise ArithmeticError("non-canonical Zeckendorf address")
    return address


@dataclass(frozen=True)
class PulviniFold:
    """Exact pairwise unimodular fold using the Fibonacci Q-matrix.

    For each pair ``(a, b)``, the fold stores ``(a+b, a)``. The inverse is
    ``(x-y, y)``. This is a reversible structure, not a compression-ratio claim.
    """

    pairs: tuple[tuple[Fraction, Fraction], ...]
    original_length: int

    def unfold(self) -> tuple[Fraction, ...]:
        output: list[Fraction] = []
        for combined, left in self.pairs:
            output.extend((left, combined - left))
        return tuple(output[: self.original_length])


def pulvini_fold(values: Iterable[int | Fraction]) -> PulviniFold:
    exact = [Fraction(value) for value in values]
    original_length = len(exact)
    if original_length % 2:
        exact.append(Fraction(0))
    pairs = tuple(
        (exact[index] + exact[index + 1], exact[index]) for index in range(0, len(exact), 2)
    )
    folded = PulviniFold(pairs=pairs, original_length=original_length)
    if folded.unfold() != tuple(exact[:original_length]):
        raise ArithmeticError("PULVINI round-trip invariant failed")
    return folded


def pisot_threshold(n: int) -> Quadratic5:
    """Return exact ``phi**(-n) == abs(phi**n - L_n)``."""
    if not isinstance(n, int) or n < 0:
        raise ValueError("n must be a non-negative integer")
    return PHI ** (-n)


def below_pisot_threshold(value: int | Fraction, n: int) -> bool:
    exact = Fraction(value)
    if exact < 0:
        raise ValueError("singular values must be non-negative")
    return (pisot_threshold(n) - Quadratic5(exact, Fraction(0))).sign() > 0


@dataclass(frozen=True)
class PisotTruncation:
    retained: tuple[Fraction, ...]
    discarded: tuple[Fraction, ...]
    discarded_weight: Fraction
    threshold: Quadratic5


def truncate_pisot(
    singular_values: Iterable[int | Fraction],
    n: int,
) -> PisotTruncation:
    retained: list[Fraction] = []
    discarded: list[Fraction] = []
    for value in singular_values:
        if isinstance(value, float):
            raise TypeError("floating-point singular values violate the exact contract")
        exact = Fraction(value)
        target = discarded if below_pisot_threshold(exact, n) else retained
        target.append(exact)
    return PisotTruncation(
        retained=tuple(retained),
        discarded=tuple(discarded),
        discarded_weight=sum((value * value for value in discarded), Fraction(0)),
        threshold=pisot_threshold(n),
    )
