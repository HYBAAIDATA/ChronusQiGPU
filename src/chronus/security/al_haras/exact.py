"""Exact rational helpers shared by the AL HARAS engines.

Every security decision in this package is computed with integers or
``fractions.Fraction``. Floating-point values only appear at the API boundary:
inputs are converted to exact rationals on arrival, and ``display_number``
produces a JSON-friendly approximation for presentation next to the exact
string form.
"""

from fractions import Fraction
from math import isqrt
from typing import Any, Iterable, List, Sequence

Vector = List[Fraction]
Matrix = List[List[Fraction]]


def to_fraction(value: Any) -> Fraction:
    """Convert an API value to an exact rational.

    ``int``/``Fraction`` are taken as is; strings may be integers, decimals or
    ``"p/q"``; a binary float is read through its shortest round-trip decimal
    representation, i.e. the literal the client sent.
    """
    if isinstance(value, bool):
        raise TypeError("booleans are not numeric state values")
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, str):
        return Fraction(value.strip())
    if isinstance(value, float):
        if value != value or (value != 0 and value * 2 == value):
            raise ValueError("NaN and infinities are not valid state values")
        return Fraction(repr(value))
    raise TypeError(f"unsupported numeric type: {type(value).__name__}")


def to_vector(values: Iterable[Any]) -> Vector:
    return [to_fraction(v) for v in values]


def identity(dim: int) -> Matrix:
    return [[Fraction(int(i == j)) for j in range(dim)] for i in range(dim)]


def transpose(m: Matrix) -> Matrix:
    return [list(col) for col in zip(*m)] if m else []


def mat_mul(a: Matrix, b: Matrix) -> Matrix:
    bt = transpose(b)
    return [[sum((x * y for x, y in zip(row, col)), Fraction(0)) for col in bt] for row in a]


def mat_vec(m: Matrix, v: Sequence[Fraction]) -> Vector:
    return [sum((x * y for x, y in zip(row, v)), Fraction(0)) for row in m]


def vec_sub(a: Sequence[Fraction], b: Sequence[Fraction]) -> Vector:
    return [x - y for x, y in zip(a, b)]


def vec_add(a: Sequence[Fraction], b: Sequence[Fraction]) -> Vector:
    return [x + y for x, y in zip(a, b)]


def norm_sq(v: Sequence[Fraction]) -> Fraction:
    return sum((x * x for x in v), Fraction(0))


def is_orthogonal(m: Matrix) -> bool:
    """Exact check that ``m^T m = I``."""
    return mat_mul(transpose(m), m) == identity(len(m))


def householder(u: Sequence[Fraction]) -> Matrix:
    """Exact rational Householder reflection ``I - 2 u u^T / (u^T u)``.

    The result is orthogonal and symmetric for every non-zero rational ``u``,
    so it is an exact element of the orthogonal group (a Stiefel frame).
    """
    uu = norm_sq(u)
    if uu == 0:
        raise ValueError("Householder vector must be non-zero")
    dim = len(u)
    return [
        [Fraction(int(i == j)) - 2 * u[i] * u[j] / uu for j in range(dim)]
        for i in range(dim)
    ]


def rank_and_nullspace(rows: Matrix, ncols: int):
    """Exact Gaussian elimination over Q.

    Returns ``(rank, basis)`` where ``basis`` is a list of column vectors that
    span the nullspace of the matrix given by ``rows``.
    """
    m = [list(r) for r in rows]
    pivots: List[int] = []
    r = 0
    for c in range(ncols):
        pivot = next((i for i in range(r, len(m)) if m[i][c] != 0), None)
        if pivot is None:
            continue
        m[r], m[pivot] = m[pivot], m[r]
        inv = 1 / m[r][c]
        m[r] = [x * inv for x in m[r]]
        for i in range(len(m)):
            if i != r and m[i][c] != 0:
                f = m[i][c]
                m[i] = [x - f * y for x, y in zip(m[i], m[r])]
        pivots.append(c)
        r += 1
        if r == len(m):
            break
    free = [c for c in range(ncols) if c not in pivots]
    basis: List[Vector] = []
    for f in free:
        v = [Fraction(0)] * ncols
        v[f] = Fraction(1)
        for i, pc in enumerate(pivots):
            v[pc] = -m[i][f]
        basis.append(v)
    return len(pivots), basis


def solve_linear(rows: Matrix, rhs: Sequence[Fraction], ncols: int):
    """Exact solve of ``rows x = rhs``; returns a solution or ``None``."""
    aug = [list(r) + [b] for r, b in zip(rows, rhs)]
    pivots: List[int] = []
    r = 0
    for c in range(ncols):
        pivot = next((i for i in range(r, len(aug)) if aug[i][c] != 0), None)
        if pivot is None:
            continue
        aug[r], aug[pivot] = aug[pivot], aug[r]
        inv = 1 / aug[r][c]
        aug[r] = [x * inv for x in aug[r]]
        for i in range(len(aug)):
            if i != r and aug[i][c] != 0:
                f = aug[i][c]
                aug[i] = [x - f * y for x, y in zip(aug[i], aug[r])]
        pivots.append(c)
        r += 1
    for i in range(r, len(aug)):
        if aug[i][ncols] != 0:
            return None
    x = [Fraction(0)] * ncols
    for i, pc in enumerate(pivots):
        x[pc] = aug[i][ncols]
    return x


def decimal_string(value: Fraction, places: int = 6) -> str:
    """Round-half-up decimal rendering computed with integers only."""
    value = Fraction(value)
    sign = "-" if value < 0 else ""
    scaled = abs(value) * (10 ** places)
    q, rem = divmod(scaled.numerator, scaled.denominator)
    if 2 * rem >= scaled.denominator:
        q += 1
    whole, frac = divmod(q, 10 ** places)
    if places == 0:
        return f"{sign}{whole}"
    return f"{sign}{whole}.{frac:0{places}d}"


def sqrt_decimal_string(value: Fraction, places: int = 6) -> str:
    """Decimal rendering of ``sqrt(value)`` truncated to ``places`` digits."""
    value = Fraction(value)
    if value < 0:
        raise ValueError("square root of a negative value")
    scale = 10 ** places
    root = isqrt(value.numerator * scale * scale // value.denominator)
    whole, frac = divmod(root, scale)
    return f"{whole}.{frac:0{places}d}" if places else f"{whole}"


def sqrt_upper_bound(value: Fraction, places: int = 9) -> Fraction:
    """A rational upper bound of ``sqrt(value)`` within ``10**-places``."""
    value = Fraction(value)
    scale = 10 ** places
    root = isqrt(value.numerator * scale * scale // value.denominator) + 1
    return Fraction(root, scale)


def display_number(value: Fraction) -> Any:
    """JSON presentation of an exact rational (int when integral)."""
    value = Fraction(value)
    if value.denominator == 1:
        return value.numerator
    return value.numerator / value.denominator


def fraction_str(value: Fraction) -> str:
    value = Fraction(value)
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"
