"""Deterministic linear algebra over GF(2) with Python ints as bit vectors.

Bit i of an int is coordinate i. Every routine is exact elimination with XOR;
there is no pivoting heuristic and no randomness.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Iterable, Iterator

__all__ = [
    "AffineSubspace",
    "echelon_basis",
    "nullspace",
    "parity",
    "rank",
    "reduced_echelon",
    "solve_affine",
]


def parity(value: int) -> int:
    return value.bit_count() & 1


def echelon_basis(vectors: Iterable[int]) -> dict[int, int]:
    """Insert vectors into an XOR basis keyed by leading bit (forward elimination)."""
    basis: dict[int, int] = {}
    for vector in vectors:
        if not isinstance(vector, int) or isinstance(vector, bool) or vector < 0:
            raise ValueError(f"GF(2) vectors must be non-negative ints, got {vector!r}")
        while vector:
            lead = vector.bit_length() - 1
            pivot = basis.get(lead)
            if pivot is None:
                basis[lead] = vector
                break
            vector ^= pivot
    return basis


def rank(vectors: Iterable[int]) -> int:
    """Rank over GF(2)."""
    return len(echelon_basis(vectors))


def reduced_echelon(vectors: Iterable[int]) -> dict[int, int]:
    """Reduced row echelon form: each row has its leading bit and no other pivot bit."""
    basis = echelon_basis(vectors)
    pivot_mask = 0
    for lead in basis:
        pivot_mask |= 1 << lead
    reduced: dict[int, int] = {}
    for lead in sorted(basis):
        row = basis[lead]
        others = pivot_mask & ~(1 << lead)
        hit = row & others
        while hit:
            row ^= reduced[hit.bit_length() - 1]
            hit = row & others
        reduced[lead] = row
    return reduced


def nullspace(vectors: Iterable[int], width: int) -> tuple[int, ...]:
    """Basis of {x in GF(2)^width : parity(v & x) = 0 for every v}."""
    space = solve_affine(((vector, 0) for vector in vectors), width)
    if space is None:
        raise ArithmeticError("homogeneous system cannot be inconsistent")
    return space.basis


def solve_affine(constraints: Iterable[tuple[int, int]], width: int) -> "AffineSubspace | None":
    """Solutions x in GF(2)^width of parity(c & x) = s for every (c, s); None if inconsistent."""
    if not isinstance(width, int) or isinstance(width, bool) or width < 0:
        raise ValueError(f"width must be a non-negative int, got {width!r}")
    limit = 1 << width
    augmented = []
    for vector, value in constraints:
        if not isinstance(vector, int) or isinstance(vector, bool) or not 0 <= vector < limit:
            raise ValueError(f"constraint vector must lie in GF(2)^{width}")
        if value not in (0, 1) or isinstance(value, bool):
            raise ValueError("constraint value must be 0 or 1")
        augmented.append((vector << 1) | value)
    reduced = reduced_echelon(augmented)
    if 0 in reduced:
        return None
    offset = 0
    pivot_columns = 0
    for lead, row in reduced.items():
        column = lead - 1
        pivot_columns |= 1 << column
        if row & 1:
            offset |= 1 << column
    free = [c for c in range(width) if not (pivot_columns >> c) & 1]
    free_vectors = {c: 1 << c for c in free}
    free_mask = 0
    for c in free:
        free_mask |= 1 << c
    for lead, row in reduced.items():
        column = lead - 1
        hits = (row >> 1) & free_mask
        while hits:
            c = hits.bit_length() - 1
            free_vectors[c] |= 1 << column
            hits ^= 1 << c
    basis = tuple(free_vectors[c] for c in free)
    return AffineSubspace(width=width, offset=offset, basis=basis)


@dataclass(frozen=True)
class AffineSubspace:
    """The set offset + span(basis) in GF(2)^width (basis linearly independent)."""

    width: int
    offset: int
    basis: tuple[int, ...]
    _pivots: dict = field(default=None, init=False, repr=False, compare=False)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        pivots = echelon_basis(self.basis)
        if len(pivots) != len(self.basis):
            raise ValueError("affine subspace basis vectors must be linearly independent")
        object.__setattr__(self, "_pivots", pivots)
        object.__setattr__(self, "offset", self._reduce(self.offset))

    def _reduce(self, vector: int) -> int:
        pivots = self._pivots
        while vector:
            lead = vector.bit_length() - 1
            pivot = pivots.get(lead)
            if pivot is None:
                return vector
            vector ^= pivot
        return 0

    @property
    def dimension(self) -> int:
        return len(self.basis)

    @property
    def size(self) -> int:
        return 1 << len(self.basis)

    @property
    def uniform_probability(self) -> Fraction:
        """Probability of each element under the uniform distribution on this set."""
        return Fraction(1, 1 << len(self.basis))

    def contains(self, vector: int) -> bool:
        if not isinstance(vector, int) or isinstance(vector, bool) or not 0 <= vector < 1 << self.width:
            return False
        return self._reduce(vector ^ self.offset) == 0

    def elements(self, limit: int = 1 << 20) -> Iterator[int]:
        """Enumerate the set (refuses sets larger than ``limit``)."""
        if self.size > limit:
            raise ValueError(f"affine subspace has 2**{self.dimension} elements; refusing to enumerate")
        for mask in range(self.size):
            vector = self.offset
            for i, b in enumerate(self.basis):
                if (mask >> i) & 1:
                    vector ^= b
            yield vector

    def orthogonal_complement(self) -> tuple[int, ...]:
        """Basis of {s : parity(s & b) = 0 for every basis vector b} (GF(2) elimination)."""
        return nullspace(self.basis, self.width)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AffineSubspace):
            return NotImplemented
        if self.width != other.width or self.dimension != other.dimension:
            return False
        if not self.contains(other.offset):
            return False
        return all(self._reduce(b) == 0 for b in other.basis)

    def __hash__(self) -> int:
        return hash((self.width, self.dimension))
