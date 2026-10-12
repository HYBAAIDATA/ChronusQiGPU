"""Exact metallic integers a+b*mu_n, mu_n**2 = n*mu_n+1.

LUCAS WIRING: metallic recurrence extension, integer coefficient arithmetic.
No conversion to floats, no QSqrt5 assertion for unrelated radicands.
"""

from __future__ import annotations

from dataclasses import dataclass


def _integer(value: int, name: str, minimum: int) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer")
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")


@dataclass(frozen=True)
class MetallicElement:
    """Unique a+b*mu_n with mu_n=(n+sqrt(n*n+4))/2 and n>=1."""

    n: int
    a: int = 0
    b: int = 0

    def __post_init__(self) -> None:
        _integer(self.n, "n", 1)
        if type(self.a) is not int or type(self.b) is not int:
            raise TypeError("integer coefficients required")

    def __mul__(self, other: MetallicElement) -> MetallicElement:
        if not isinstance(other, MetallicElement):
            return NotImplemented
        if self.n != other.n:
            raise ArithmeticError("different metallic fields")
        return MetallicElement(
            self.n,
            self.a * other.a + self.b * other.b,
            self.a * other.b + self.b * other.a + self.n * self.b * other.b,
        )

    def __pow__(self, exponent: int) -> MetallicElement:
        _integer(exponent, "exponent", 0)
        result, base = MetallicElement(self.n, 1), self
        while exponent:
            if exponent & 1:
                result = result * base
            exponent >>= 1
            if exponent:
                base = base * base
        return result

    def conjugate(self) -> MetallicElement:
        return MetallicElement(self.n, self.a + self.n * self.b, -self.b)

    def norm(self) -> int:
        return self.a * self.a + self.n * self.a * self.b - self.b * self.b


def metallic_exact(n: int) -> MetallicElement:
    return MetallicElement(n, 0, 1)


def metallic(n: int) -> MetallicElement:
    return metallic_exact(n)


def metallic_fast_doubling(n: int, k: int) -> MetallicElement:
    """Binary exact powering; the API name does not imply a recurrence shortcut."""
    return metallic_exact(n) ** k


def metallic_ladder(n: int, rungs: list[int]) -> list[MetallicElement]:
    generator = metallic_exact(n)
    return [generator**r for r in rungs]


def silver() -> MetallicElement:
    return metallic_exact(2)


def bronze() -> MetallicElement:
    return metallic_exact(3)


def copper() -> MetallicElement:
    return metallic_exact(4)
