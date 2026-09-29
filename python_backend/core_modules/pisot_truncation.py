"""Exact bounded diagonal-SVD Pisot truncation; unsupported general SVD fails closed."""

from dataclasses import dataclass
from fractions import Fraction
from typing import Sequence
from .math_folding import below_pisot_threshold


class UnsupportedExactSVD(NotImplementedError):
    pass


class BondExceeded(ValueError):
    pass


@dataclass(frozen=True)
class TensorWithBound:
    diagonal: tuple[Fraction, ...]
    chi: int
    discarded_weight: Fraction
    trace_preserved: bool


def truncate_diagonal_tensor(
    matrix: Sequence[Sequence[int | Fraction]],
    *,
    threshold_index: int,
    max_bond: int,
    require_trace_preservation: bool = True,
) -> TensorWithBound:
    size = len(matrix)
    if size == 0 or any(len(row) != size for row in matrix):
        raise ValueError("square matrix required")
    exact = tuple(tuple(Fraction(v) for v in row) for row in matrix)
    if any(exact[i][j] for i in range(size) for j in range(size) if i != j):
        raise UnsupportedExactSVD("general exact SVD is not implemented; diagonal domain only")
    sigmas = tuple(abs(exact[i][i]) for i in range(size))
    retained = tuple(s for s in sigmas if not below_pisot_threshold(s, threshold_index))
    if len(retained) > max_bond:
        raise BondExceeded("required bond dimension exceeds max_bond")
    discarded = tuple(s for s in sigmas if below_pisot_threshold(s, threshold_index))
    trace_preserved = sum(retained, Fraction(0)) == sum(sigmas, Fraction(0))
    if require_trace_preservation and not trace_preserved:
        raise ValueError("non-zero truncation cannot claim exact trace preservation")
    return TensorWithBound(
        retained, len(retained), sum((s * s for s in discarded), Fraction(0)), trace_preserved
    )
