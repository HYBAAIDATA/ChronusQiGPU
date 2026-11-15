"""Exact quantum Fourier transform over Z_Q with amplitudes in Q(zeta_Q).

A state is an integer D >= 1 together with a vector v of cyclotomic numbers;
the amplitude of |k> is v_k / sqrt(D). The QFT maps v_j -> sum_k zeta_Q^(jk) v_k
and D -> D * Q, so 1/sqrt(Q) is kept symbolic and nothing is rounded. The
pair (D, v) is kept canonical: D is squarefree, every square factor of D
having been moved into v.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import lcm
from typing import Iterable, Sequence

from ..algebra.cyclotomic import CyclotomicElement, CyclotomicField, factorize

__all__ = [
    "ScaledVector",
    "inverse_qft",
    "is_unitary",
    "qft",
    "qft_is_unitary",
    "qft_matrix",
]


def _squarefree_split(value: int) -> tuple[int, int]:
    """Return (s, d) with value = s^2 * d and d squarefree."""
    s, d = 1, 1
    for p, exponent in factorize(value).items():
        s *= p ** (exponent // 2)
        if exponent % 2:
            d *= p
    return s, d


@dataclass(frozen=True, eq=False)
class ScaledVector:
    """Exact vector with entries values[k] / sqrt(scale)."""

    scale: int
    values: tuple[CyclotomicElement, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.scale, int) or isinstance(self.scale, bool) or self.scale < 1:
            raise ValueError("scale must be a positive int")
        values = tuple(self.values)
        if not values:
            raise ValueError("a vector needs at least one entry")
        fields = set()
        for value in values:
            if not isinstance(value, CyclotomicElement):
                raise TypeError("entries must be CyclotomicElement values")
            fields.add(value.field.n)
        common = CyclotomicField(lcm(*fields))
        values = tuple(common.lift(v) for v in values)
        root, squarefree = _squarefree_split(self.scale)
        if root != 1:
            values = tuple(v / root for v in values)
        object.__setattr__(self, "scale", squarefree)
        object.__setattr__(self, "values", values)

    @classmethod
    def from_values(cls, values: Iterable[object], field: CyclotomicField, scale: int = 1) -> "ScaledVector":
        return cls(scale, tuple(field.lift(v) for v in values))  # type: ignore[arg-type]

    @property
    def field(self) -> CyclotomicField:
        return self.values[0].field

    @property
    def dimension(self) -> int:
        return len(self.values)

    def probability(self, k: int) -> CyclotomicElement:
        """|amplitude_k|^2 = |v_k|^2 / D, exactly."""
        return self.values[k].abs2() / self.scale

    def norm_squared(self) -> CyclotomicElement:
        total = self.field.zero
        for value in self.values:
            total = total + value.abs2()
        return total / self.scale

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ScaledVector):
            return NotImplemented
        return (self.scale == other.scale and len(self.values) == len(other.values)
                and all(a == b for a, b in zip(self.values, other.values)))

    def __hash__(self) -> int:
        return hash((self.scale, self.values))


def _times_zeta_power(value: CyclotomicElement, exponent: int) -> CyclotomicElement:
    field = value.field
    n = field.n
    return field.from_exponents({(k + exponent) % n: c for k, c in enumerate(value.coefficients) if c})


def _transform(state: ScaledVector, sign: int) -> ScaledVector:
    if not isinstance(state, ScaledVector):
        raise TypeError("state must be a ScaledVector")
    size = state.dimension
    field = CyclotomicField(lcm(state.field.n, size))
    values = [field.lift(v) for v in state.values]
    stride = field.n // size
    out = []
    for j in range(size):
        total = field.zero
        for k, value in enumerate(values):
            if value:
                total = total + _times_zeta_power(value, sign * stride * ((j * k) % size))
        out.append(total)
    return ScaledVector(state.scale * size, tuple(out))


def qft(state: ScaledVector) -> ScaledVector:
    """QFT over Z_Q (Q = dimension): v_j -> sum_k zeta_Q^(jk) v_k, D -> D * Q."""
    return _transform(state, 1)


def inverse_qft(state: ScaledVector) -> ScaledVector:
    """Inverse QFT: v_j -> sum_k zeta_Q^(-jk) v_k, D -> D * Q."""
    return _transform(state, -1)


def qft_matrix(size: int) -> tuple[int, tuple[tuple[CyclotomicElement, ...], ...]]:
    """Return (D, rows) with QFT_Q = rows / sqrt(D), D = Q, rows[j][k] = zeta_Q^(jk)."""
    if not isinstance(size, int) or isinstance(size, bool) or size < 1:
        raise ValueError("size must be a positive int")
    field = CyclotomicField(size)
    rows = tuple(tuple(field.zeta((j * k) % size) for k in range(size)) for j in range(size))
    return size, rows


def is_unitary(scale: int, rows: Sequence[Sequence[CyclotomicElement]]) -> bool:
    """Exact check that U = rows / sqrt(scale) satisfies U U^dagger = I."""
    size = len(rows)
    if any(len(row) != size for row in rows):
        return False
    for j in range(size):
        for l in range(size):
            total = rows[j][0].field.zero
            for k in range(size):
                total = total + rows[j][k] * rows[l][k].conjugate()
            if total != (scale if j == l else 0):
                return False
    return True


def qft_is_unitary(size: int, limit: int = 64) -> bool:
    """Exact unitarity check of QFT_Q (QFT * QFT^dagger = I) for Q <= limit."""
    if size > limit:
        raise ValueError(f"refusing the O(Q^3) exact unitarity check for Q = {size} > {limit}")
    scale, rows = qft_matrix(size)
    return is_unitary(scale, rows)
