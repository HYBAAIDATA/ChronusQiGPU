"""
Fibonacci Q-matrix and its powers.

The Q-matrix Q = [[1,1],[1,0]] satisfies:
    Q^n = [[F(n+1), F(n)], [F(n), F(n-1)]]

Key properties:
    det(Q^n) = (-1)^n          (Cassini's identity)
    tr(Q^n) = L(n)             (Lucas trace identity)
    Q^m · Q^n = Q^(m+n)        (semigroup property)
"""

from .sequences import fib_pair, lucas


def matrix_power(n: int) -> list[list[int]]:
    """Compute Q^n = [[F(n+1), F(n)], [F(n), F(n-1)]] as Python ints.

    Q = [[1,1],[1,0]], Q^0 = I = [[1,0],[0,1]].
    """
    if n == 0:
        return [[1, 0], [0, 1]]
    fn, fn1 = fib_pair(n)
    fn_1 = fn1 - fn  # F(n-1) = F(n+1) - F(n)
    return [[fn1, fn], [fn, fn_1]]


def matrix_det(m: list[list[int]]) -> int:
    """Determinant of a 2×2 matrix."""
    return m[0][0] * m[1][1] - m[0][1] * m[1][0]


def matrix_trace(m: list[list[int]]) -> int:
    """Trace of a 2×2 matrix."""
    return m[0][0] + m[1][1]


def matrix_mult(a: list[list[int]], b: list[list[int]]) -> list[list[int]]:
    """Multiply two 2×2 matrices."""
    return [
        [a[0][0] * b[0][0] + a[0][1] * b[1][0],
         a[0][0] * b[0][1] + a[0][1] * b[1][1]],
        [a[1][0] * b[0][0] + a[1][1] * b[1][0],
         a[1][0] * b[0][1] + a[1][1] * b[1][1]],
    ]


def matrix_equal(a: list[list[int]], b: list[list[int]]) -> bool:
    """Check equality of two 2×2 matrices."""
    return a[0] == b[0] and a[1] == b[1]
