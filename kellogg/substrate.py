"""Kellogg substrate — (Z[phi], R): the golden transfer matrix and its identities.

R = [[1, 1], [1, 0]] is the Fibonacci transfer matrix. Its eigenvalues are
phi and psi = 1 - phi, so every substrate identity is a statement about R:

    L_n = trace(R^n) = phi^n + psi^n              Lucas, a contraction
    F_{n-1} F_{n+1} - F_n^2 = det(R)^n = (-1)^n    Fibonacci Cassini
    L_{n-1} L_{n+1} - L_n^2 = 5 (-1)^(n+1)         Lucas Cassini
    psi^n = L_n - phi^n,  |psi^n| -> 0             Pisot

R acts on T^2 = R^2 / Z^2 as the golden cat map, a hyperbolic toral
automorphism with det R = -1; on the discrete torus (Z/qZ)^2 it is an exact
integer permutation. The scalar rule x -> phi*x mod 1 is not a map on R/Z
(x and x + 1 land phi apart), so the substrate is R acting on T^2.

The field Q(phi) = Q(sqrt 5) carries the beta-expansion for beta = phi and
the exact comparisons the expansion needs. Every routine here is exact
integer or rational arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Dict, List, Sequence, Tuple

from .scales import Zphi, fibonacci, lucas, phi_power

IntMatrix = Tuple[Tuple[int, ...], ...]

TRANSFER: IntMatrix = ((1, 1), (1, 0))

FAMILY_COEFFS: Dict[str, Tuple[int, ...]] = {
    "golden": (1, -1, -1),
    "silver": (1, -2, -1),
    "plastic": (1, 0, -1, -1),
    "supergolden": (1, -1, 0, -1),
    "tribonacci": (1, -1, -1, -1),
}


def int_mat_mul(left: Sequence[Sequence[int]], right: Sequence[Sequence[int]]) -> IntMatrix:
    n, m, p = len(left), len(right), len(right[0])
    if any(len(row) != m for row in left):
        raise ValueError("inner dimensions do not match")
    return tuple(
        tuple(sum(left[i][k] * right[k][j] for k in range(m)) for j in range(p))
        for i in range(n)
    )


def int_mat_pow(matrix: Sequence[Sequence[int]], n: int) -> IntMatrix:
    """Exact M^n by binary exponentiation, n >= 0."""
    if n < 0:
        raise ValueError("integer matrix powers require n >= 0")
    size = len(matrix)
    result: IntMatrix = tuple(tuple(int(i == j) for j in range(size)) for i in range(size))
    base: IntMatrix = tuple(tuple(int(v) for v in row) for row in matrix)
    while n:
        if n & 1:
            result = int_mat_mul(result, base)
        base = int_mat_mul(base, base)
        n >>= 1
    return result


def trace(matrix: Sequence[Sequence[int]]) -> int:
    return sum(matrix[i][i] for i in range(len(matrix)))


def det2(matrix: Sequence[Sequence[int]]) -> int:
    return matrix[0][0] * matrix[1][1] - matrix[0][1] * matrix[1][0]


def lucas_wind(n: int) -> int:
    """L_n as the contraction trace(R^n)."""
    return trace(int_mat_pow(TRANSFER, n))


def lucas_cassini(n: int) -> int:
    """L_{n-1} L_{n+1} - L_n^2, which equals 5 (-1)^(n+1)."""
    if n < 1:
        raise ValueError("lucas_cassini is defined for n >= 1")
    return lucas(n - 1) * lucas(n + 1) - lucas(n) ** 2


def cassini_step(n: int) -> dict:
    """Both Cassini identities at index n, read off R^n.

    R^n = [[F_{n+1}, F_n], [F_n, F_{n-1}]], so det(R^n) is the Fibonacci
    Cassini value and det(R)^n = (-1)^n. The Lucas form carries the
    opposite sign and a factor 5.
    """
    if n < 1:
        raise ValueError("cassini_step is defined for n >= 1")
    power = int_mat_pow(TRANSFER, n)
    fib = fibonacci(n - 1) * fibonacci(n + 1) - fibonacci(n) ** 2
    luc = lucas_cassini(n)
    sign = -1 if n % 2 else 1
    return {
        "n": n,
        "R_n": [list(row) for row in power],
        "det_R_n": det2(power),
        "fibonacci_cassini": fib,
        "lucas_cassini": luc,
        "fibonacci_holds": fib == sign and det2(power) == fib,
        "lucas_holds": luc == -5 * sign,
    }


def cat_map(point: Tuple[int, int], modulus: int) -> Tuple[int, int]:
    """R acting on the discrete torus (Z/qZ)^2: (x, y) -> (x + y, x)."""
    if modulus < 1:
        raise ValueError("modulus must be positive")
    x, y = point
    return ((x + y) % modulus, x % modulus)


def cat_map_inverse(point: Tuple[int, int], modulus: int) -> Tuple[int, int]:
    """R^-1 = [[0, 1], [1, -1]]; det R = -1 makes R unimodular."""
    x, y = point
    return (y % modulus, (x - y) % modulus)


def cat_map_period(modulus: int) -> int:
    """Smallest n >= 1 with R^n = I modulo q (the Pisano period for q > 1)."""
    if modulus < 1:
        raise ValueError("modulus must be positive")
    if modulus == 1:
        return 1
    a, b, c, d = 1, 1, 1, 0
    n = 1
    while not (a % modulus == 1 and b % modulus == 0 and c % modulus == 0 and d % modulus == 1):
        a, b, c, d = (a + b) % modulus, a % modulus, (c + d) % modulus, c % modulus
        n += 1
        if n > 6 * modulus + 6:
            raise RuntimeError("Pisano period exceeded its 6q bound")
    return n


def pisot_residual(n: int) -> Zphi:
    """psi^n = L_n - phi^n as an exact Z[phi] element."""
    return Zphi(lucas(n), 0) - phi_power(n)


def pisot_contracts(n: int) -> bool:
    """Exact check that |psi^(n+1)| < |psi^n|: (psi^n)^2 - (psi^(n+1))^2 > 0."""
    current = pisot_residual(n)
    following = pisot_residual(n + 1)
    return (current * current - following * following).sign() > 0


def ring_norm(value: Zphi) -> int:
    """N(a + b phi) = a^2 + ab - b^2."""
    return value.norm()


def ring_sign(value: Zphi) -> int:
    """Exact sign: (2a + b)^2 against 5 b^2 with sign bookkeeping."""
    return value.sign()


def family_companion(name: str) -> IntMatrix:
    """Integer companion matrix of a Pisot family recurrence.

    Superdiagonal ones; the last row holds the recurrence coefficients.
    """
    coeffs = FAMILY_COEFFS[name]
    d = len(coeffs) - 1
    rows = [[0] * d for _ in range(d)]
    for i in range(d - 1):
        rows[i][i + 1] = 1
    for j in range(d):
        rows[d - 1][j] = -coeffs[d - j]
    return tuple(tuple(row) for row in rows)


def family_matrix_power(name: str, n: int) -> IntMatrix:
    return int_mat_pow(family_companion(name), n)


@dataclass(frozen=True)
class QPhi:
    """Exact element a + b*phi of the field Q(phi) = Q(sqrt 5)."""

    a: Fraction
    b: Fraction

    def __init__(self, a: int | Fraction = 0, b: int | Fraction = 0) -> None:
        object.__setattr__(self, "a", Fraction(a))
        object.__setattr__(self, "b", Fraction(b))

    @classmethod
    def of(cls, value: "QPhi | Zphi | int | Fraction") -> "QPhi":
        if isinstance(value, QPhi):
            return value
        if isinstance(value, Zphi):
            return cls(value.a, value.b)
        return cls(value, 0)

    def __add__(self, other: object) -> "QPhi":
        o = QPhi.of(other)  # type: ignore[arg-type]
        return QPhi(self.a + o.a, self.b + o.b)

    __radd__ = __add__

    def __sub__(self, other: object) -> "QPhi":
        o = QPhi.of(other)  # type: ignore[arg-type]
        return QPhi(self.a - o.a, self.b - o.b)

    def __rsub__(self, other: object) -> "QPhi":
        return QPhi.of(other) - self  # type: ignore[arg-type]

    def __neg__(self) -> "QPhi":
        return QPhi(-self.a, -self.b)

    def __mul__(self, other: object) -> "QPhi":
        o = QPhi.of(other)  # type: ignore[arg-type]
        return QPhi(self.a * o.a + self.b * o.b, self.a * o.b + self.b * o.a + self.b * o.b)

    __rmul__ = __mul__

    def conjugate(self) -> "QPhi":
        return QPhi(self.a + self.b, -self.b)

    def norm(self) -> Fraction:
        return self.a * self.a + self.a * self.b - self.b * self.b

    def inverse(self) -> "QPhi":
        n = self.norm()
        if n == 0:
            raise ZeroDivisionError("Q(phi) division by zero")
        c = self.conjugate()
        return QPhi(c.a / n, c.b / n)

    def __truediv__(self, other: object) -> "QPhi":
        return self * QPhi.of(other).inverse()  # type: ignore[arg-type]

    def sign(self) -> int:
        """Exact sign of (2a + b) + b*sqrt(5), halved."""
        lhs = 2 * self.a + self.b
        if self.b == 0:
            return (lhs > 0) - (lhs < 0)
        if lhs == 0:
            return (self.b > 0) - (self.b < 0)
        s_l = (lhs > 0) - (lhs < 0)
        s_r = (self.b > 0) - (self.b < 0)
        if s_l == s_r:
            return s_l
        cmp_sq = (lhs * lhs > 5 * self.b * self.b) - (lhs * lhs < 5 * self.b * self.b)
        return s_l * cmp_sq

    def __lt__(self, other: object) -> bool:
        return (self - other).sign() < 0

    def __le__(self, other: object) -> bool:
        return (self - other).sign() <= 0

    def floor(self) -> int:
        """Exact floor, located by a float estimate and corrected exactly."""
        guess = int(float(self.a) + float(self.b) * 1.618033988749895) - 2
        while not QPhi(guess + 1) <= self:
            guess -= 1
        while QPhi(guess + 1) <= self:
            guess += 1
        return guess


PHI_FIELD = QPhi(0, 1)


def phi_beta_expansion(x: Fraction | int, digits: int) -> Tuple[List[int], QPhi]:
    """Greedy beta-expansion of x in [0, 1) for beta = phi.

    Returns (d_1, ..., d_k) and the exact remainder r_k with
    x = sum d_i phi^-i + phi^-k r_k. Digits are 0 or 1 and no two adjacent
    digits are both 1 (Parry admissibility for beta = phi).
    """
    value = QPhi(Fraction(x))
    if value.sign() < 0 or not value < QPhi(1):
        raise ValueError("beta-expansion is defined on [0, 1)")
    out: List[int] = []
    r = value
    for _ in range(int(digits)):
        r = r * PHI_FIELD
        d = r.floor()
        out.append(d)
        r = r - QPhi(d)
    return out, r


def beta_expansion_value(digits: Sequence[int], remainder: QPhi) -> QPhi:
    """Rebuild x from its digits and remainder, exactly."""
    inv_phi = PHI_FIELD.inverse()
    total = QPhi(0)
    scale = QPhi(1)
    for d in digits:
        scale = scale * inv_phi
        total = total + scale * QPhi(d)
    return total + scale * remainder


def parry_admissible(digits: Sequence[int]) -> bool:
    return all(d in (0, 1) for d in digits) and all(
        not (digits[i] == 1 and digits[i + 1] == 1) for i in range(len(digits) - 1)
    )


def korobov_point(i: int, k: int) -> Tuple[Fraction, Fraction]:
    """Point i of the Fibonacci lattice with F_k points: (i/F_k, {i F_(k-1)/F_k})."""
    n = fibonacci(k)
    if n < 1 or not 0 <= i < n:
        raise ValueError("index outside the Fibonacci lattice")
    return (Fraction(i, n), Fraction((i * fibonacci(k - 1)) % n, n))


def star_discrepancy_2d(points: Sequence[Tuple[Fraction, Fraction]]) -> Fraction:
    """Exact star discrepancy of a finite point set in [0, 1)^2.

    D* = sup over anchored boxes of |A(box)/N - vol(box)|. The supremum of
    vol - A/N is taken over open boxes with corners in the coordinate grid
    plus 1; the supremum of A/N - vol over closed boxes at point coordinates.
    """
    n = len(points)
    if n == 0:
        raise ValueError("discrepancy needs at least one point")
    xs = sorted({p[0] for p in points} | {Fraction(1)})
    ys = sorted({p[1] for p in points} | {Fraction(1)})
    best = Fraction(0)
    for a in xs:
        open_y = sorted(p[1] for p in points if p[0] < a)
        closed_y = sorted(p[1] for p in points if p[0] <= a)
        oi = ci = 0
        for b in ys:
            while oi < len(open_y) and open_y[oi] < b:
                oi += 1
            while ci < len(closed_y) and closed_y[ci] <= b:
                ci += 1
            vol = a * b
            best = max(best, vol - Fraction(oi, n))
            if a < 1 and b < 1:
                best = max(best, Fraction(ci, n) - vol)
    return best


__all__ = [
    "FAMILY_COEFFS",
    "PHI_FIELD",
    "QPhi",
    "TRANSFER",
    "beta_expansion_value",
    "cassini_step",
    "cat_map",
    "cat_map_inverse",
    "cat_map_period",
    "det2",
    "family_companion",
    "family_matrix_power",
    "int_mat_mul",
    "int_mat_pow",
    "korobov_point",
    "lucas_cassini",
    "lucas_wind",
    "parry_admissible",
    "phi_beta_expansion",
    "pisot_contracts",
    "pisot_residual",
    "ring_norm",
    "ring_sign",
    "star_discrepancy_2d",
    "trace",
]
