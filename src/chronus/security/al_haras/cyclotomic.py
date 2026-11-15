"""Exact arithmetic in the cyclotomic ring Z[zeta_5] = Z[x]/(x^4 + x^3 + x^2 + x + 1).

Elements are stored with integer coefficients in the basis (1, zeta, zeta^2,
zeta^3). All operations are exact; there is no floating-point arithmetic.
"""

from typing import Iterable, List, Tuple


class CyclotomicZ5:
    """Element c0 + c1*zeta + c2*zeta^2 + c3*zeta^3 of Z[zeta_5]."""

    __slots__ = ("c0", "c1", "c2", "c3")

    def __init__(self, c0: int = 0, c1: int = 0, c2: int = 0, c3: int = 0) -> None:
        self.c0 = int(c0)
        self.c1 = int(c1)
        self.c2 = int(c2)
        self.c3 = int(c3)

    @classmethod
    def from_coeffs(cls, coeffs: Iterable[int]) -> "CyclotomicZ5":
        values = list(coeffs)
        if len(values) != 4:
            raise ValueError("Z[zeta_5] elements need exactly four coefficients")
        return cls(*values)

    @classmethod
    def zeta_power(cls, k: int) -> "CyclotomicZ5":
        """zeta_5^k reduced to the integral basis."""
        k %= 5
        if k == 4:
            return cls(-1, -1, -1, -1)
        coeffs = [0, 0, 0, 0]
        coeffs[k] = 1
        return cls(*coeffs)

    def coeffs(self) -> Tuple[int, int, int, int]:
        return (self.c0, self.c1, self.c2, self.c3)

    def __add__(self, other: "CyclotomicZ5") -> "CyclotomicZ5":
        return CyclotomicZ5(self.c0 + other.c0, self.c1 + other.c1, self.c2 + other.c2, self.c3 + other.c3)

    def __sub__(self, other: "CyclotomicZ5") -> "CyclotomicZ5":
        return CyclotomicZ5(self.c0 - other.c0, self.c1 - other.c1, self.c2 - other.c2, self.c3 - other.c3)

    def __neg__(self) -> "CyclotomicZ5":
        return CyclotomicZ5(-self.c0, -self.c1, -self.c2, -self.c3)

    def __mul__(self, other: "CyclotomicZ5") -> "CyclotomicZ5":
        s = [self.c0, self.c1, self.c2, self.c3]
        o = [other.c0, other.c1, other.c2, other.c3]
        p: List[int] = [0] * 7
        for i in range(4):
            for j in range(4):
                p[i + j] += s[i] * o[j]
        # x^4 = -x^3 - x^2 - x - 1
        for deg in range(6, 3, -1):
            lead = p[deg]
            if lead:
                p[deg - 1] -= lead
                p[deg - 2] -= lead
                p[deg - 3] -= lead
                p[deg - 4] -= lead
                p[deg] = 0
        return CyclotomicZ5(p[0], p[1], p[2], p[3])

    def __pow__(self, exponent: int) -> "CyclotomicZ5":
        if exponent < 0:
            raise ValueError("negative powers are not defined for general ring elements")
        result = CyclotomicZ5(1)
        base = self
        while exponent:
            if exponent & 1:
                result = result * base
            base = base * base
            exponent >>= 1
        return result

    def is_zero(self) -> bool:
        return self.c0 == 0 and self.c1 == 0 and self.c2 == 0 and self.c3 == 0

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CyclotomicZ5):
            return False
        return self.coeffs() == other.coeffs()

    def __hash__(self) -> int:
        return hash(self.coeffs())

    def __repr__(self) -> str:
        return f"CyclotomicZ5({self.c0}, {self.c1}, {self.c2}, {self.c3})"


ZERO = CyclotomicZ5(0)
ONE = CyclotomicZ5(1)
ZETA = CyclotomicZ5(0, 1)
# Golden ratio inside Z[zeta_5]: phi = -(zeta^2 + zeta^3) and phi^-1 = phi - 1.
PHI = CyclotomicZ5(0, 0, -1, -1)
PHI_INVERSE = CyclotomicZ5(-1, 0, -1, -1)

Matrix2 = List[List[CyclotomicZ5]]


def mat2_mul(a: Matrix2, b: Matrix2) -> Matrix2:
    return [
        [a[0][0] * b[0][0] + a[0][1] * b[1][0], a[0][0] * b[0][1] + a[0][1] * b[1][1]],
        [a[1][0] * b[0][0] + a[1][1] * b[1][0], a[1][0] * b[0][1] + a[1][1] * b[1][1]],
    ]


def mat2_identity() -> Matrix2:
    return [[ONE, ZERO], [ZERO, ONE]]


def mat2_coeffs(m: Matrix2) -> List[List[List[int]]]:
    return [[list(m[r][c].coeffs()) for c in range(2)] for r in range(2)]
