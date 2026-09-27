"""Kellogg scales — Layer 0 (Z[phi] ring) and Layer 1 (algebraic scales).

Every primitive in this module is exact integer/algebraic arithmetic.
``Zphi`` elements are ``a + b*phi`` with ``a, b`` integers and
``phi^2 = phi + 1``; Lucas, Fibonacci, Binet, Pisot drift, Zeckendorf
folds and the Cassini ledger are all computed without floating point.

The single declared float boundary is ``pisot_wind``: torus coordinates
on T^11 are observational positions, so the exact Pisot drift element is
projected once through ``to_float`` and the crossing is recorded in the
function's contract. Nothing downstream may promote the result back into
an exact field.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

PHI_NAME = "phi = (1 + sqrt(5)) / 2"


class NotRepresentable(ValueError):
    """Raised when a value cannot be represented exactly in the field."""


# ---------------------------------------------------------------------------
# Zphi — the ring Z[phi] = { a + b*phi : a, b in Z }
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Zphi:
    """Exact element ``a + b*phi`` of the ring Z[phi]."""

    a: int = 0
    b: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "a", int(self.a))
        object.__setattr__(self, "b", int(self.b))

    def __add__(self, other: "Zphi") -> "Zphi":
        return Zphi(self.a + other.a, self.b + other.b)

    def __sub__(self, other: "Zphi") -> "Zphi":
        return Zphi(self.a - other.a, self.b - other.b)

    def __neg__(self) -> "Zphi":
        return Zphi(-self.a, -self.b)

    def __mul__(self, other: "Zphi") -> "Zphi":
        # (a + b*phi)(c + d*phi) = ac + (ad + bc)*phi + bd*phi^2
        #                        = (ac + bd) + (ad + bc + bd)*phi
        return Zphi(
            self.a * other.a + self.b * other.b,
            self.a * other.b + self.b * other.a + self.b * other.b,
        )

    def __pow__(self, n: int) -> "Zphi":
        if n < 0:
            raise NotRepresentable("Z[phi] negative powers leave the ring")
        result = Zphi(1, 0)
        base = self
        while n:
            if n & 1:
                result = result * base
            base = base * base
            n >>= 1
        return result

    def conjugate(self) -> "Zphi":
        """Galois conjugate phi -> psi = 1 - phi maps a + b*phi -> (a+b) - b*phi."""
        return Zphi(self.a + self.b, -self.b)

    def norm(self) -> int:
        """N(a + b*phi) = a^2 + ab - b^2, an exact integer."""
        return self.a * self.a + self.a * self.b - self.b * self.b

    def sign(self) -> int:
        """Exact sign without floats.

        a + b*phi > 0  iff  (2a + b) + b*sqrt(5) > 0, decided by integer
        comparison of (2a + b)^2 against 5b^2 with sign bookkeeping.
        """
        lhs = 2 * self.a + self.b  # 2(a + b*phi) = (2a + b) + b*sqrt(5)
        if self.b == 0:
            return (lhs > 0) - (lhs < 0)
        if lhs == 0:
            return (self.b > 0) - (self.b < 0)  # value is b*sqrt(5)
        # Compare lhs against -b*sqrt(5): signs first, then squares.
        s_l = (lhs > 0) - (lhs < 0)
        s_r = (-self.b > 0) - (-self.b < 0)
        if s_l != s_r:
            return s_l
        cmp_sq = (lhs * lhs > 5 * self.b * self.b) - (
            lhs * lhs < 5 * self.b * self.b
        )
        return cmp_sq if s_l > 0 else -cmp_sq

    def to_float(self) -> float:
        """ONE-WAY boundary crossing: exact element -> IEEE-754."""
        return self.a + self.b * ((1.0 + 5.0**0.5) / 2.0)

    @classmethod
    def from_float(cls, x: float) -> "Zphi":
        """Fail-closed: only exact integers are representable."""
        if isinstance(x, float) and x.is_integer():
            return cls(int(x), 0)
        raise NotRepresentable(f"{x!r} is not representable in Z[phi]")


ZPHI_ZERO = Zphi(0, 0)
ZPHI_ONE = Zphi(1, 0)
PHI = Zphi(0, 1)


# ---------------------------------------------------------------------------
# Fibonacci / Lucas — fast doubling, exact integers
# ---------------------------------------------------------------------------


def _fib_lucas_pair(n: int) -> Tuple[int, int]:
    """Return (F_n, L_n) by fast doubling. n >= 0."""
    if n == 0:
        return (0, 2)
    f, l = _fib_lucas_pair(n >> 1)
    # F_{2k} = F_k * L_k ; L_{2k} = L_k^2 - 2*(-1)^k
    f2 = f * l
    l2 = l * l - 2 * (1 if ((n >> 1) % 2 == 0) else -1)
    if n & 1:
        # F_{2k+1} = (F_{2k} + L_{2k}) / 2 ; L_{2k+1} = (5 F_{2k} + L_{2k}) / 2
        return ((f2 + l2) // 2, (5 * f2 + l2) // 2)
    return (f2, l2)


def fibonacci(n: int) -> int:
    """F_0 = 0, F_1 = 1 — exact integer."""
    if n < 0:
        raise ValueError("fibonacci is defined for n >= 0")
    return _fib_lucas_pair(n)[0]


def lucas(n: int) -> int:
    """L_0 = 2, L_1 = 1, L_n = L_{n-1} + L_{n-2} — exact integer.

    Equivalent to L_n = phi^n + psi^n evaluated in Z[phi].
    """
    if n < 0:
        raise ValueError("lucas is defined for n >= 0")
    return _fib_lucas_pair(n)[1]


def phi_power(n: int) -> Zphi:
    """phi^n = F_{n-1} + F_n * phi as an exact Zphi element."""
    if n < 0:
        raise NotRepresentable("phi_power requires n >= 0 in Z[phi]")
    if n == 0:
        return ZPHI_ONE
    return Zphi(fibonacci(n - 1), fibonacci(n))


def binet_fold(n: int) -> Zphi:
    """Binet fold: F_n = (phi^n - psi^n) / sqrt(5) returned in Z[phi].

    phi^n - psi^n = sqrt(5) * F_n and sqrt(5) = 2*phi - 1, so the quotient
    is the plain integer F_n — verified in Z[phi], never approximated.
    """
    if n < 0:
        raise ValueError("binet_fold is defined for n >= 0")
    pn = phi_power(n)
    psi_n = pn.conjugate()
    num = pn - psi_n  # == sqrt(5) * F_n = (-F_n) + 2 F_n * phi
    f_n = fibonacci(n)
    if num != Zphi(-f_n, 2 * f_n):
        raise ArithmeticError("Binet fold violated: phi^n - psi^n != sqrt(5) * F_n")
    return Zphi(f_n, 0)


def pisot_drift(n: int) -> Zphi:
    """delta_n = phi^n - L_n — the exact Pisot drift element.

    At n = 15 this is the irrational rotation magnitude
    |phi^15 - L_15| ~ 7.33e-4 that makes the T^11 winding ergodic.
    Returned symbolically in Z[phi]; never truncated.
    """
    if n < 0:
        raise ValueError("pisot_drift is defined for n >= 0")
    return phi_power(n) - Zphi(lucas(n), 0)


# ---------------------------------------------------------------------------
# Zeckendorf fold
# ---------------------------------------------------------------------------


def zeckendorf(n: int) -> List[int]:
    """Zeckendorf representation: greedy non-consecutive Fibonacci indices.

    Returns the unique descending list of indices k >= 2 with
    n = sum F_{k_i} and consecutive indices differing by at least 2.
    """
    if n < 0:
        raise ValueError("zeckendorf is defined for n >= 0")
    if n == 0:
        return []
    indices: List[int] = []
    remainder = n
    # Largest k with F_k <= remainder; F_2 = 1 starts the usable sequence.
    k = 2
    while fibonacci(k + 1) <= remainder:
        k += 1
    while remainder > 0:
        indices.append(k)
        remainder -= fibonacci(k)
        # Next usable index is at most k - 2 (non-adjacency theorem).
        k -= 2
        while k >= 2 and fibonacci(k) > remainder:
            k -= 1
        if remainder > 0 and k < 2:
            raise ArithmeticError("Zeckendorf decomposition failed")
    return indices


def zeckendorf_11d(x: int) -> int:
    """Project a Zeckendorf representation onto an 11-bit token.

    Bit (k mod 11) is set iff F_k appears in the Zeckendorf fold of x.
    The projection is declared lossy — distinct integers may share a
    token; it is a lane index, not an encoding.
    """
    token = 0
    for k in zeckendorf(x):
        token |= 1 << (k % 11)
    return token


def zeckendorf_is_legal(indices: Sequence[int]) -> bool:
    """Non-adjacency check: no two Zeckendorf indices differ by less than 2."""
    ordered = sorted(indices)
    return all(ordered[i + 1] - ordered[i] >= 2 for i in range(len(ordered) - 1))


# ---------------------------------------------------------------------------
# Cassini ledger
# ---------------------------------------------------------------------------


def cassini(n: int) -> int:
    """Cassini value F_{n-1} F_{n+1} - F_n^2 — must equal (-1)^n exactly."""
    if n < 1:
        raise ValueError("cassini is defined for n >= 1")
    return fibonacci(n - 1) * fibonacci(n + 1) - fibonacci(n) * fibonacci(n)


def cassini_verify(n: int) -> bool:
    """Machine check of the Cassini identity at index n."""
    return cassini(n) == (1 if n % 2 == 0 else -1)


def cassini_store(k: int) -> List[Tuple[int, int, int, int]]:
    """The traversal integrity ledger: (F_{i-1}, F_i, F_{i+1}, (-1)^i).

    Any consumer replaying a Fibonacci-indexed stream can re-verify each
    quadruple; a violation proves the index stream is corrupt.
    """
    if k < 1:
        return []
    return [
        (fibonacci(i - 1), fibonacci(i), fibonacci(i + 1), 1 if i % 2 == 0 else -1)
        for i in range(1, k + 1)
    ]


# ---------------------------------------------------------------------------
# Pisot winding on the 11-torus — DECLARED FLOAT BOUNDARY
# ---------------------------------------------------------------------------

# phi^15 - L_15 is the drift used by the repo's historical winding step.
_DRIFT15 = pisot_drift(15)


def pisot_wind(state: Sequence[float], n: int) -> Tuple[float, ...]:
    """Irrational rotation of an 11-torus state by the Pisot drift.

    FLOAT_BOUNDARY: the exact element delta_15 = phi^15 - L_15 in Z[phi]
    is projected through ``to_float`` exactly once per call; the torus
    coordinates themselves are observational and remain in the float
    plane. Weyl equidistribution gives dense coverage — this is an honest
    floating-point rotation, not claimed to be exact.
    """
    if len(state) != 11:
        raise ValueError("pisot_wind operates on T^11: exactly 11 coordinates")
    delta = _DRIFT15.to_float()
    out = []
    for i, coordinate in enumerate(state):
        step = delta * lucas(n + i)
        out.append((float(coordinate) + step) % 1.0)
    return tuple(out)
