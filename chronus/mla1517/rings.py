"""Exact integer-coordinate algebraic rings used by MLA1517.

No floating roots are used here.  Each cubic ring is represented by a basis
(1, x, x²) and multiplication is reduced by its defining monic polynomial.
"""

from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class ZPhi:
    """Element a+bφ with φ²=φ+1."""

    a: int = 0
    b: int = 0

    def __add__(self, other: "ZPhi") -> "ZPhi":
        return ZPhi(self.a + other.a, self.b + other.b)

    def __mul__(self, other: "ZPhi") -> "ZPhi":
        return ZPhi(
            self.a * other.a + self.b * other.b,
            self.a * other.b + self.b * other.a + self.b * other.b,
        )

    def __pow__(self, n: int) -> "ZPhi":
        if n < 0:
            raise ValueError("negative powers are not integral ring elements")
        out, base = ZPhi(1, 0), self
        while n:
            if n & 1:
                out = out * base
            base, n = base * base, n >> 1
        return out

    def norm(self) -> int:
        return self.a * self.a + self.a * self.b - self.b * self.b


@dataclass(frozen=True)
class _ZCubic:
    """Base class for an exact cubic quotient ring."""

    coeffs: tuple[int, int, int] = (0, 0, 0)
    # relation x^3 = r0 + r1*x + r2*x²
    relation: tuple[int, int, int] = (0, 0, 0)

    def __post_init__(self) -> None:
        if len(self.coeffs) != 3:
            raise ValueError("cubic elements require three coefficients")

    def __add__(self, other: "_ZCubic") -> "_ZCubic":
        return type(self)(tuple(a + b for a, b in zip(self.coeffs, other.coeffs)))

    def __mul__(self, other: "_ZCubic") -> "_ZCubic":
        return type(self)(self._mul_coeffs(self.coeffs, other.coeffs))

    @classmethod
    def _mul_coeffs(
        cls, left: tuple[int, int, int], right: tuple[int, int, int]
    ) -> tuple[int, int, int]:
        raw = [0] * 5
        for i, a in enumerate(left):
            for j, b in enumerate(right):
                raw[i + j] += a * b
        r0, r1, r2 = cls.relation
        for k in range(4, 2, -1):
            value = raw[k]
            if value:
                raw[k - 3] += value * r0
                raw[k - 2] += value * r1
                raw[k - 1] += value * r2
        return (raw[0], raw[1], raw[2])

    def __pow__(self, n: int) -> "_ZCubic":
        if n < 0:
            raise ValueError("negative powers are not integral ring elements")
        out, base = type(self)((1, 0, 0)), self
        while n:
            if n & 1:
                out = out * base
            base, n = base * base, n >> 1
        return out

    def norm(self) -> int:
        a, b, c = self.coeffs
        columns = [
            self._mul_coeffs(self.coeffs, basis) for basis in ((1, 0, 0), (0, 1, 0), (0, 0, 1))
        ]
        m = tuple(zip(*columns))
        return (
            m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
            - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
            + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
        )


@dataclass(frozen=True)
class ZRho(_ZCubic):
    """Z[ρ], ρ³=ρ+1 (plastic/Pisot family)."""

    relation = (1, 1, 0)


@dataclass(frozen=True)
class ZPsi(_ZCubic):
    """Z[ψ], ψ³=ψ²+1 (supergolden family)."""

    relation = (1, 0, 1)


@dataclass(frozen=True)
class ZTau(_ZCubic):
    """Z[τ], τ³=τ²+τ+1 (tribonacci family)."""

    relation = (1, 1, 1)


def ring_powers(ring: type[_ZCubic], n: int) -> tuple[int, int, int]:
    return (ring((0, 1, 0)) ** n).coeffs
