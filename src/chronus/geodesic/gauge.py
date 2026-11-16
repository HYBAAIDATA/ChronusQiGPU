"""Exact SU(2) lattice gauge links on the H4 triangle complex.

Curvature is encoded by plaquette holonomy U_ij U_jk U_ki rather than
by antisymmetrising a symmetric scalar product. These are discrete
Wilson loops with exact Gaussian-rational coefficients. They are NOT
a smooth Yang-Mills PDE or proof of any continuum mass gap.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Mapping


@dataclass(frozen=True)
class GaussianRational:
    re: Fraction
    im: Fraction = Fraction(0)

    def __post_init__(self) -> None:
        object.__setattr__(self, "re", Fraction(self.re))
        object.__setattr__(self, "im", Fraction(self.im))

    @staticmethod
    def of(x: "GaussianRational | int | Fraction") -> "GaussianRational":
        return x if isinstance(x, GaussianRational) else GaussianRational(Fraction(x))

    def __add__(self, other: "GaussianRational | int | Fraction") -> "GaussianRational":
        v = self.of(other)
        return GaussianRational(self.re + v.re, self.im + v.im)

    __radd__ = __add__

    def __neg__(self) -> "GaussianRational":
        return GaussianRational(-self.re, -self.im)

    def __sub__(self, other: "GaussianRational | int | Fraction") -> "GaussianRational":
        return self + -self.of(other)

    def __mul__(self, other: "GaussianRational | int | Fraction") -> "GaussianRational":
        v = self.of(other)
        return GaussianRational(self.re * v.re - self.im * v.im,
                                self.re * v.im + self.im * v.re)

    __rmul__ = __mul__

    def conj(self) -> "GaussianRational":
        return GaussianRational(self.re, -self.im)

    def norm2(self) -> Fraction:
        return self.re ** 2 + self.im ** 2


@dataclass(frozen=True)
class SU2Link:
    """Matrix [[a,b],[-conj(b),conj(a)]] with |a|^2+|b|^2=1."""
    a: GaussianRational
    b: GaussianRational

    def __post_init__(self) -> None:
        if self.a.norm2() + self.b.norm2() != 1:
            raise ValueError("SU(2) link must satisfy exact determinant-one unitarity")

    @classmethod
    def identity(cls) -> "SU2Link":
        return cls(GaussianRational(1), GaussianRational(0))

    def inverse(self) -> "SU2Link":
        return SU2Link(self.a.conj(), -self.b)

    def __mul__(self, other: "SU2Link") -> "SU2Link":
        if not isinstance(other, SU2Link):
            return NotImplemented
        # Exact multiplication of the SU2 parametrisation.
        return SU2Link(self.a * other.a - self.b * other.b.conj(),
                       self.a * other.b + self.b * other.a.conj())

    def trace(self) -> Fraction:
        return 2 * self.a.re


def directed_link(edges: Mapping[tuple[int, int], SU2Link],
                  i: int, j: int) -> SU2Link:
    if (i, j) in edges and (j, i) in edges:
        if edges[(j, i)] != edges[(i, j)].inverse():
            raise ValueError("edge reversal is inconsistent")
    if (i, j) in edges:
        return edges[(i, j)]
    if (j, i) in edges:
        return edges[(j, i)].inverse()
    raise KeyError(f"missing SU2 link for {(i, j)}")


def triangle_holonomy(face: tuple[int, int, int],
                      edges: Mapping[tuple[int, int], SU2Link]) -> SU2Link:
    """Exact Wilson loop. Reversal gives the inverse holonomy."""
    if len(face) != 3 or len(set(face)) != 3:
        raise ValueError("face must contain three distinct vertices")
    i, j, k = face
    return (directed_link(edges, i, j) *
            directed_link(edges, j, k) *
            directed_link(edges, k, i))


def wilson_action(face: tuple[int, int, int],
                  edges: Mapping[tuple[int, int], SU2Link]) -> Fraction:
    """Gauge-invariant nonnegative plaquette action: 2-Re(tr U)."""
    # 2 - Re Tr(U) >= 0, with exact rational arithmetic.
    return Fraction(2) - triangle_holonomy(face, edges).trace()


def gauge_transform(edges: Mapping[tuple[int, int], SU2Link],
                    vertex_gauges: Mapping[int, SU2Link]
                    ) -> dict[tuple[int, int], SU2Link]:
    """U_ij -> g_i U_ij g_j^{-1}, preserving Wilson loop traces."""
    identity = SU2Link.identity()
    return {
        (i, j): vertex_gauges.get(i, identity) * link *
                vertex_gauges.get(j, identity).inverse()
        for (i, j), link in edges.items()
    }
