"""
Turing Exact Quantum Library — Ring Number-Theoretic Primitives & Linear Algebra
"""

from __future__ import annotations
from typing import List, Tuple, Union, TYPE_CHECKING
from turing.exact.errors import DimensionMismatchError, RingError

if TYPE_CHECKING:
    from turing.exact.ring.zeta import ZetaP


def is_prime(n: int) -> bool:
    """Deterministic primality test for ring parameter verification."""
    if n < 2:
        return False
    if n in (2, 3):
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    d = 5
    while d * d <= n:
        if n % d == 0 or n % (d + 2) == 0:
            return False
        d += 6
    return True


def gcd(a: int, b: int) -> int:
    """Euclidean algorithm for greatest common divisor."""
    while b != 0:
        a, b = b, a % b
    return abs(a)


def legendre_symbol(k: int, p: int) -> int:
    """Computes the Legendre symbol (k / p) via Euler's criterion."""
    k_mod = k % p
    if k_mod == 0:
        return 0
    res = pow(k_mod, (p - 1) // 2, p)
    return 1 if res == 1 else -1


def cyclotomic_polynomial_prime(p: int) -> List[int]:
    """Returns the coefficients of the cyclotomic polynomial Phi_p(x) = 1 + x + ... + x^(p-1)."""
    if not is_prime(p):
        raise ValueError(f"p={p} must be prime")
    return [1] * p


def convolution(a: Union[Tuple[int, ...], List[int]], b: Union[Tuple[int, ...], List[int]]) -> List[int]:
    """Computes polynomial discrete convolution without floating-point arithmetic."""
    if not a or not b:
        return []
    res = [0] * (len(a) + len(b) - 1)
    for i, ai in enumerate(a):
        for j, bj in enumerate(b):
            res[i + j] += ai * bj
    return res


def bareiss_det(entries: List[List['ZetaP']]) -> 'ZetaP':
    """
    Fraction-free Gaussian elimination over an integral domain.
    Computes det(A) exactly using only ring additions, multiplications,
    and exact ring divisions.
    """
    from turing.exact.ring.zeta import ZetaP

    n = len(entries)
    if n == 0:
        raise DimensionMismatchError("Matrix has dimension zero")
    if any(len(row) != n for row in entries):
        raise DimensionMismatchError("Determinant requires a square matrix")

    p = entries[0][0].p
    for row in entries:
        for val in row:
            if val.p != p:
                raise RingError(f"Matrix entry ring prime mismatch: {val.p} != {p}")

    if n == 1:
        return entries[0][0]

    M = [[entries[i][j] for j in range(n)] for i in range(n)]
    sign = 1
    prev_pivot = ZetaP.one(p)

    for k in range(n - 1):
        if M[k][k] == ZetaP.zero(p):
            swap_row = -1
            for i in range(k + 1, n):
                if M[i][k] != ZetaP.zero(p):
                    swap_row = i
                    break
            if swap_row == -1:
                return ZetaP.zero(p)
            M[k], M[swap_row] = M[swap_row], M[k]
            sign = -sign

        for i in range(k + 1, n):
            for j in range(k + 1, n):
                num = (M[i][j] * M[k][k]) - (M[i][k] * M[k][j])
                M[i][j] = num.exact_div(prev_pivot)
        prev_pivot = M[k][k]

    det = M[n - 1][n - 1]
    return det if sign == 1 else -det
