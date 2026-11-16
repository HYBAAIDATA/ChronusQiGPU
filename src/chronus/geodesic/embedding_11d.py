"""Exact 11-coordinate feature embedding for the H4 dual geometry.

This is a *nonlinear, injective* map of the 600 dual 120-cell vertices into
Q(sqrt(5))^11. Its first four coordinates retain the canonical 4D geometry;
the seven additional quadratic coordinates supply an explicit higher-dimensional
search representation with exact inverse projection. This construction is NOT
an 11-dimensional irreducible H4 representation, a distance-preserving
isometry, or a claim that the source four-polytope is an 11D manifold.
An isometric embedding of four-dimensional Euclidean space can have at most
four-dimensional affine image. Those distinct requirements cannot be combined.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from chronus.geodesic.dual_120cell import Point4, build_dual_120_cell


@dataclass(frozen=True)
class Q5:
    """An exact real quadratic-field element a + b sqrt(5)."""
    a: Fraction
    b: Fraction = Fraction(0)

    def __post_init__(self) -> None:
        object.__setattr__(self, "a", Fraction(self.a))
        object.__setattr__(self, "b", Fraction(self.b))

    @classmethod
    def of(cls, x: "Q5 | Fraction | int") -> "Q5":
        return x if isinstance(x, Q5) else cls(Fraction(x))

    def __add__(self, other: "Q5 | Fraction | int") -> "Q5":
        y = Q5.of(other)
        return Q5(self.a + y.a, self.b + y.b)

    __radd__ = __add__

    def __neg__(self) -> "Q5":
        return Q5(-self.a, -self.b)

    def __sub__(self, other: "Q5 | Fraction | int") -> "Q5":
        return self + (-Q5.of(other))

    def __rsub__(self, other: "Q5 | Fraction | int") -> "Q5":
        return Q5.of(other) - self

    def __mul__(self, other: "Q5 | Fraction | int") -> "Q5":
        y = Q5.of(other)
        return Q5(self.a * y.a + 5 * self.b * y.b,
                  self.a * y.b + self.b * y.a)

    __rmul__ = __mul__

    def __truediv__(self, other: "Q5 | Fraction | int") -> "Q5":
        y = Q5.of(other)
        norm = y.a * y.a - 5 * y.b * y.b
        if norm == 0:
            raise ZeroDivisionError("zero divisor in Q(sqrt(5))")
        return Q5((self.a * y.a - 5 * self.b * y.b) / norm,
                  (self.b * y.a - self.a * y.b) / norm)

    def sign(self) -> int:
        """Exact ordering of the real embedding sqrt(5)>0."""
        a, b = self.a, self.b
        if b == 0:
            return (a > 0) - (a < 0)
        if a == 0:
            return (b > 0) - (b < 0)
        if (a > 0) == (b > 0):
            return 1 if a > 0 else -1
        cmp = a * a - 5 * b * b
        if cmp == 0:
            raise AssertionError("nonzero rational cannot equal sqrt(5) multiple")
        return ((cmp > 0) - (cmp < 0)) * (1 if a > 0 else -1)

    def is_zero(self) -> bool:
        return self.a == 0 and self.b == 0


ZERO = Q5(0)
PHI = Q5(Fraction(1, 2), Fraction(1, 2))
PHI_INV = PHI - 1


def dual_vertex_4d(index: int) -> tuple[Q5, Q5, Q5, Q5]:
    """Recover canonical exact centroid coordinates from the H4 dual index."""
    geometry = build_dual_120_cell()
    if type(index) is not int or not 0 <= index < len(geometry.vertices):
        raise ValueError("dual vertex index must be in [0,600)")
    return tuple(Q5(Fraction(a, 16), Fraction(b, 16))
                 for a, b in geometry.vertices[index])  # type: ignore[return-value]


def embed_11d(point: tuple[Q5, Q5, Q5, Q5]) -> tuple[Q5, ...]:
    """Injective 4D -> 11D polynomial feature embedding, without rounding.

    Coordinates 0..3 are a left-invertible copy of the input. The remaining
    coordinates form a golden-scaled quadratic feature representation.
    """
    if len(point) != 4 or any(not isinstance(x, Q5) for x in point):
        raise TypeError("point must contain four exact Q5 coordinates")
    a, b, c, d = point
    return (
        a, b, c, d,
        PHI_INV * a * b, PHI_INV * a * c, PHI_INV * a * d,
        PHI_INV * b * c, PHI_INV * b * d, PHI_INV * c * d,
        PHI_INV * (a * a - b * b),
    )


def project_4d(point: tuple[Q5, ...]) -> tuple[Q5, Q5, Q5, Q5]:
    """Exact left inverse on the 11D embedding image."""
    if len(point) != 11:
        raise ValueError("expected 11 coordinates")
    return tuple(point[:4])  # type: ignore[return-value]


def embed_dual_vertex(index: int) -> tuple[Q5, ...]:
    return embed_11d(dual_vertex_4d(index))


def exact_affine_rank(points: list[tuple[Q5, ...]]) -> int:
    """Exact Gaussian elimination over Q(sqrt(5)), no tolerance/float."""
    if not points:
        return 0
    width = len(points[0])
    origin = points[0]
    pivots: list[tuple[int, list[Q5]]] = []
    for p in points[1:]:
        if len(p) != width:
            raise ValueError("inconsistent coordinate width")
        row = [p[i] - origin[i] for i in range(width)]
        for index, basis in pivots:
            coeff = row[index]
            if not coeff.is_zero():
                row = [row[i] - coeff * basis[i] for i in range(width)]
        pivot = next((i for i, value in enumerate(row) if not value.is_zero()), None)
        if pivot is None:
            continue
        factor = row[pivot]
        pivots.append((pivot, [value / factor for value in row]))
        pivots.sort(key=lambda p: p[0])
        if len(pivots) == width:
            break
    return len(pivots)


def embedding_certificate() -> dict[str, object]:
    """Independently assert injectivity, exact inversion and affine rank."""
    vertices = [embed_dual_vertex(i) for i in range(600)]
    distinct = len(set(vertices))
    all_roundtrip = all(project_4d(v) == dual_vertex_4d(i)
                        for i, v in enumerate(vertices))
    affine_rank = exact_affine_rank(vertices)
    if distinct != 600 or not all_roundtrip:
        raise AssertionError("11D embedding is not reversible on dual vertices")
    return {
        "input_vertices": 600,
        "output_coordinates": 11,
        "distinct_images": distinct,
        "left_inverse_verified": all_roundtrip,
        "affine_span_dimension": affine_rank,
        "field": "Q(sqrt(5))",
        "preserves_4d_coordinates": True,
        "preserves_11d_pairwise_distances": False,
        "H4_irreducible_representation_proven": False,
    }
