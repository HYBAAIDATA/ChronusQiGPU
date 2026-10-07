"""Exact linear algebra over a field: Q (Fraction), Q(zeta_8) (Q8 or F4).

Every routine is Gaussian elimination with exact zero tests, so ranks,
factorizations, inverses and PSD decisions are decided, never thresholded.

The rank factorization M = C F takes C = the pivot columns of M and F = the
non-zero rows of the reduced row-echelon form. RREF is unique, so F is a
canonical gauge: two equal matrices always factor identically. This is the
exact replacement for SVD truncation: it removes only redundant bond
dimensions and never discards weight. SVD itself needs square roots outside
these fields and is a float-plane operation.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any, List, Sequence, Tuple

Matrix = List[List[Any]]


class SingularMatrix(ArithmeticError):
    """An exact inverse or solve met a singular matrix."""


def is_zero(value: Any) -> bool:
    probe = getattr(value, "is_zero", None)
    if probe is not None:
        return bool(probe())
    return value == 0


def zero_like(value: Any) -> Any:
    return value - value


def one_like(value: Any) -> Any:
    if isinstance(value, Fraction) or isinstance(value, int):
        return Fraction(1)
    z = zero_like(value)
    return type(value).coerce(1) if hasattr(type(value), "coerce") else z + 1


def conj(value: Any) -> Any:
    fn = getattr(value, "conjugate", None)
    return fn() if fn is not None else value


def shape(matrix: Sequence[Sequence[Any]]) -> Tuple[int, int]:
    rows = len(matrix)
    cols = len(matrix[0]) if rows else 0
    if any(len(row) != cols for row in matrix):
        raise ValueError("ragged matrix")
    return rows, cols


def copy(matrix: Sequence[Sequence[Any]]) -> Matrix:
    return [list(row) for row in matrix]


def matmul(left: Sequence[Sequence[Any]], right: Sequence[Sequence[Any]]) -> Matrix:
    n, m = shape(left)
    m2, p = shape(right)
    if m != m2:
        raise ValueError(f"matmul shape mismatch {n}x{m} @ {m2}x{p}")
    if m == 0:
        raise ValueError("matmul with an empty inner dimension")
    cols = [[right[k][j] for k in range(m)] for j in range(p)]
    out: Matrix = []
    for i in range(n):
        row = left[i]
        nz = [(k, row[k]) for k in range(m) if not is_zero(row[k])]
        line = []
        for j in range(p):
            col = cols[j]
            acc = zero_like(row[0])
            for k, v in nz:
                if not is_zero(col[k]):
                    acc = acc + v * col[k]
            line.append(acc)
        out.append(line)
    return out


def adjoint(matrix: Sequence[Sequence[Any]]) -> Matrix:
    rows, cols = shape(matrix)
    return [[conj(matrix[i][j]) for i in range(rows)] for j in range(cols)]


def transpose(matrix: Sequence[Sequence[Any]]) -> Matrix:
    rows, cols = shape(matrix)
    return [[matrix[i][j] for i in range(rows)] for j in range(cols)]


def identity(n: int, like: Any) -> Matrix:
    z, o = zero_like(like), one_like(like)
    return [[o if i == j else z for j in range(n)] for i in range(n)]


def equal(left: Sequence[Sequence[Any]], right: Sequence[Sequence[Any]]) -> bool:
    if shape(left) != shape(right):
        return False
    return all(a == b for ra, rb in zip(left, right) for a, b in zip(ra, rb))


def rref(matrix: Sequence[Sequence[Any]]) -> Tuple[Matrix, List[int]]:
    """Reduced row-echelon form and pivot columns, exactly."""
    m = copy(matrix)
    rows, cols = shape(m)
    pivots: List[int] = []
    r = 0
    for c in range(cols):
        if r == rows:
            break
        pivot_row = next((i for i in range(r, rows) if not is_zero(m[i][c])), None)
        if pivot_row is None:
            continue
        m[r], m[pivot_row] = m[pivot_row], m[r]
        inv = one_like(m[r][c]) / m[r][c]
        m[r] = [v * inv if not is_zero(v) else v for v in m[r]]
        for i in range(rows):
            if i != r and not is_zero(m[i][c]):
                factor = m[i][c]
                m[i] = [a - factor * b if not is_zero(b) else a for a, b in zip(m[i], m[r])]
        pivots.append(c)
        r += 1
    return m, pivots


def rank(matrix: Sequence[Sequence[Any]]) -> int:
    return len(rref(matrix)[1])


def cr_factor(matrix: Sequence[Sequence[Any]]) -> Tuple[Matrix, Matrix, List[int]]:
    """Exact rank factorization M = C F with C full column rank, F full row rank."""
    rows, cols = shape(matrix)
    reduced, pivots = rref(matrix)
    if not pivots:
        z = matrix[0][0]
        zero = zero_like(z)
        return [[zero] for _ in range(rows)], [[zero for _ in range(cols)]], []
    c = [[matrix[i][p] for p in pivots] for i in range(rows)]
    f = [list(reduced[k]) for k in range(len(pivots))]
    return c, f, pivots


def solve(matrix: Sequence[Sequence[Any]], rhs: Sequence[Any]) -> List[Any]:
    """Solve A x = b exactly for square non-singular A."""
    n, m = shape(matrix)
    if n != m or len(rhs) != n:
        raise ValueError("solve needs a square system")
    augmented = [list(matrix[i]) + [rhs[i]] for i in range(n)]
    reduced, pivots = rref(augmented)
    if pivots != list(range(n)):
        raise SingularMatrix("matrix is singular")
    return [reduced[i][n] for i in range(n)]


def inverse(matrix: Sequence[Sequence[Any]]) -> Matrix:
    n, m = shape(matrix)
    if n != m:
        raise ValueError("inverse needs a square matrix")
    eye = identity(n, matrix[0][0])
    reduced, pivots = rref([list(matrix[i]) + eye[i] for i in range(n)])
    if pivots[:n] != list(range(n)):
        raise SingularMatrix("matrix is singular")
    return [row[n:] for row in reduced]


def det(matrix: Sequence[Sequence[Any]]) -> Any:
    n, m = shape(matrix)
    if n != m:
        raise ValueError("determinant needs a square matrix")
    a = copy(matrix)
    result = one_like(a[0][0])
    for c in range(n):
        p = next((i for i in range(c, n) if not is_zero(a[i][c])), None)
        if p is None:
            return zero_like(a[0][0])
        if p != c:
            a[c], a[p] = a[p], a[c]
            result = -result
        result = result * a[c][c]
        inv = one_like(a[c][c]) / a[c][c]
        for i in range(c + 1, n):
            if not is_zero(a[i][c]):
                f = a[i][c] * inv
                a[i] = [x - f * y for x, y in zip(a[i], a[c])]
    return result


def is_hermitian(matrix: Sequence[Sequence[Any]]) -> bool:
    return equal(matrix, adjoint(matrix))


def is_unitary(matrix: Sequence[Sequence[Any]]) -> bool:
    n, m = shape(matrix)
    return n == m and equal(matmul(adjoint(matrix), matrix), identity(n, matrix[0][0]))


def _sign(value: Any) -> int:
    fn = getattr(value, "sign", None)
    if fn is not None:
        return int(fn())
    return (value > 0) - (value < 0)


def is_psd(matrix: Sequence[Sequence[Any]]) -> bool:
    """Exact positive-semidefiniteness of a real symmetric matrix.

    Symmetric elimination: a negative pivot refutes PSD; a zero pivot
    requires its whole row to vanish. Decided in the ordered field.
    """
    a = copy(matrix)
    n, m = shape(a)
    if n != m or not equal(a, transpose(a)):
        return False
    for k in range(n):
        s = _sign(a[k][k])
        if s < 0:
            return False
        if s == 0:
            if any(not is_zero(a[k][j]) for j in range(k + 1, n)):
                return False
            continue
        inv = one_like(a[k][k]) / a[k][k]
        for i in range(k + 1, n):
            if is_zero(a[i][k]):
                continue
            f = a[i][k] * inv
            for j in range(k, n):
                a[i][j] = a[i][j] - f * a[k][j]
    return True


def kron(left: Sequence[Sequence[Any]], right: Sequence[Sequence[Any]]) -> Matrix:
    n, m = shape(left)
    p, q = shape(right)
    return [
        [left[i][j] * right[k][l] for j in range(m) for l in range(q)]
        for i in range(n)
        for k in range(p)
    ]


def trace(matrix: Sequence[Sequence[Any]]) -> Any:
    n, m = shape(matrix)
    if n != m:
        raise ValueError("trace needs a square matrix")
    acc = zero_like(matrix[0][0])
    for i in range(n):
        acc = acc + matrix[i][i]
    return acc


__all__ = [
    "SingularMatrix",
    "adjoint",
    "conj",
    "copy",
    "cr_factor",
    "det",
    "equal",
    "identity",
    "inverse",
    "is_hermitian",
    "is_psd",
    "is_unitary",
    "is_zero",
    "kron",
    "matmul",
    "one_like",
    "rank",
    "rref",
    "shape",
    "solve",
    "trace",
    "transpose",
    "zero_like",
]
