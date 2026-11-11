"""Exact linear algebra over any field: reduced row echelon form, rank and CR.

The CR factorisation writes a matrix A (m x n, rank r) as A = C @ R, where C
(m x r) is the set of pivot columns of A and R (r x n) is the set of nonzero
rows of the reduced row echelon form of A. Both factors have full rank r, the
reduced row echelon form is unique, and every step is exact field arithmetic
through the :class:`~turing.tensor.field.Field` protocol, so the factorisation
is exact and deterministic. It plays the role that the singular value
decomposition plays in floating-point tensor networks: the SVD needs square
roots, which leave the field, so it can never be exact; CR needs only field
operations and reveals the exact rank.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from .dense import ExactTensor, _matrix_product
from .field import Field

__all__ = [
    "CRFactorization",
    "cr_factorization",
    "matmul",
    "rank",
    "rref",
]


def _rref_rows(field: Field, rows: list[list[Any]], columns: int) -> tuple[list[list[Any]], tuple[int, ...]]:
    """Reduce ``rows`` in place to reduced row echelon form; return (nonzero rows, pivot columns).

    The pivot of each column is the first remaining row with a nonzero entry
    (any choice gives the same, unique, reduced row echelon form). Zero
    entries are skipped, and a pivot row whose leading entry is already one
    is not rescaled.
    """
    is_zero = field.is_zero
    eq = field.eq
    sub = field.sub
    mul = field.mul
    div = field.div
    zero = field.zero
    one = field.one
    height = len(rows)
    pivots: list[int] = []
    top = 0
    for column in range(columns):
        if top == height:
            break
        found = None
        for i in range(top, height):
            if not is_zero(rows[i][column]):
                found = i
                break
        if found is None:
            continue
        if found != top:
            rows[top], rows[found] = rows[found], rows[top]
        pivot_row = rows[top]
        lead = pivot_row[column]
        if not eq(lead, one):
            inverse = div(one, lead)
            for k in range(column + 1, columns):
                value = pivot_row[k]
                if not is_zero(value):
                    pivot_row[k] = mul(inverse, value)
            pivot_row[column] = one
        support = [k for k in range(column + 1, columns) if not is_zero(pivot_row[k])]
        for i in range(height):
            if i == top:
                continue
            row = rows[i]
            factor = row[column]
            if is_zero(factor):
                continue
            for k in support:
                row[k] = sub(row[k], mul(factor, pivot_row[k]))
            row[column] = zero
        pivots.append(column)
        top += 1
    return rows[:top], tuple(pivots)


def _cr_rows(field: Field, rows: Sequence[Sequence[Any]],
             columns: int) -> tuple[list[list[Any]], list[list[Any]], tuple[int, ...]]:
    """CR factorisation of a row list: (C rows m x r, R rows r x n, pivot columns)."""
    reduced, pivots = _rref_rows(field, [list(row) for row in rows], columns)
    c_rows = [[row[p] for p in pivots] for row in rows]
    return c_rows, reduced, pivots


def _matrix_rows(matrix: object) -> tuple[Field, int, int, list[list[Any]]]:
    if not isinstance(matrix, ExactTensor):
        raise TypeError("expected an ExactTensor matrix")
    if matrix.order != 2:
        raise ValueError(f"expected a matrix (order-2 tensor), got shape {matrix.shape!r}")
    height, width = matrix.shape
    entries = matrix.entries
    return matrix.field, height, width, [list(entries[i * width:(i + 1) * width]) for i in range(height)]


def _from_rows(field: Field, rows: Sequence[Sequence[Any]], height: int, width: int) -> ExactTensor:
    flat = tuple(value for row in rows for value in row)
    return ExactTensor._raw(field, (height, width), flat)


def rref(matrix: ExactTensor) -> tuple[ExactTensor, tuple[int, ...]]:
    """Reduced row echelon form (same shape, zero rows last) and the pivot columns."""
    field, height, width, rows = _matrix_rows(matrix)
    reduced, pivots = _rref_rows(field, rows, width)
    full = list(reduced) + [[field.zero] * width for _ in range(height - len(reduced))]
    return _from_rows(field, full, height, width), pivots


def rank(matrix: ExactTensor) -> int:
    """Exact rank: the number of pivots of the reduced row echelon form."""
    field, _, width, rows = _matrix_rows(matrix)
    return len(_rref_rows(field, rows, width)[1])


@dataclass(frozen=True)
class CRFactorization:
    """A = C @ R with C the pivot columns of A and R the nonzero rows of rref(A)."""

    C: ExactTensor
    R: ExactTensor
    pivots: tuple[int, ...]

    @property
    def rank(self) -> int:
        return len(self.pivots)

    def product(self) -> ExactTensor:
        """C @ R, which equals the factorised matrix exactly."""
        return self.C.matmul(self.R)


def cr_factorization(matrix: ExactTensor) -> CRFactorization:
    """Exact CR factorisation of a matrix over its field (works for rank 0 and empty shapes)."""
    field, height, width, rows = _matrix_rows(matrix)
    c_rows, r_rows, pivots = _cr_rows(field, rows, width)
    r = len(pivots)
    return CRFactorization(_from_rows(field, c_rows, height, r), _from_rows(field, r_rows, r, width), pivots)


def matmul(left: ExactTensor, right: ExactTensor) -> ExactTensor:
    """Exact matrix product of two order-2 tensors over the same field."""
    if not isinstance(left, ExactTensor) or not isinstance(right, ExactTensor):
        raise TypeError("matmul needs two ExactTensor matrices")
    return left.matmul(right)


def _matmul_rows(field: Field, left: Sequence[Sequence[Any]], right: Sequence[Sequence[Any]],
                 inner: int, columns: int) -> list[list[Any]]:
    """Row-list matrix product used by the matrix-product classes (zero entries skipped)."""
    flat_left = [value for row in left for value in row]
    flat_right = [value for row in right for value in row]
    rows = len(left)
    flat = _matrix_product(field, flat_left, flat_right, rows, inner, columns)
    return [flat[i * columns:(i + 1) * columns] for i in range(rows)]
