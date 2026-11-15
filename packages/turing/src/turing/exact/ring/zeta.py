"""
Turing Exact Quantum Library — Parameterized Cyclotomic Integer Ring Z[zeta_p]
"""

from __future__ import annotations
from typing import List, Tuple, Union, TYPE_CHECKING
from turing.exact.errors import RingError, NonUnitError, DimensionMismatchError
from turing.exact.ring.utils import is_prime, gcd, convolution, legendre_symbol

if TYPE_CHECKING:
    from turing.exact.ring.rational import RationalZetaP


class ZetaP:
    """
    Exact element of Z[zeta_p] represented in the integral canonical basis:
    1, zeta_p, zeta_p^2, ..., zeta_p^(p-2).
    Minimal polynomial: Phi_p(x) = 1 + x + ... + x^(p-1) = 0.
    """
    __slots__ = ('p', 'degree', 'coeffs')

    def __init__(self, p: int, coeffs: Union[List[int], Tuple[int, ...]]):
        if not is_prime(p):
            raise ValueError(f"p={p} must be prime")
        if len(coeffs) != p - 1:
            raise DimensionMismatchError(f"Expected {p - 1} coefficients for p={p}, got {len(coeffs)}")
        self.p = p
        self.degree = p - 1
        self.coeffs = tuple(int(c) for c in coeffs)

    @staticmethod
    def reduce(coeffs: List[int], p: int) -> List[int]:
        """Reduces polynomial coefficients modulo Phi_p(x) = 1 + x + ... + x^(p-1)."""
        deg = p - 1
        work = list(coeffs)
        while len(work) > deg:
            k = len(work) - 1
            c = work.pop()
            if c != 0:
                for i in range(deg):
                    work[k - deg + i] -= c
        if len(work) < deg:
            work.extend([0] * (deg - len(work)))
        return work

    @classmethod
    def zero(cls, p: int) -> 'ZetaP':
        return cls(p, (0,) * (p - 1))

    @classmethod
    def one(cls, p: int) -> 'ZetaP':
        return cls(p, (1,) + (0,) * (p - 2))

    @classmethod
    def zeta(cls, p: int) -> 'ZetaP':
        c = [0] * (p - 1)
        c[1] = 1
        return cls(p, c)

    @classmethod
    def from_int(cls, n: int, p: int) -> 'ZetaP':
        return cls(p, (n,) + (0,) * (p - 2))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ZetaP):
            return False
        return self.p == other.p and self.coeffs == other.coeffs

    def __add__(self, other: 'ZetaP') -> 'ZetaP':
        if not isinstance(other, ZetaP) or self.p != other.p:
            raise RingError(f"Ring prime mismatch: {self.p} != {getattr(other, 'p', None)}")
        return ZetaP(self.p, tuple(a + b for a, b in zip(self.coeffs, other.coeffs)))

    def __sub__(self, other: 'ZetaP') -> 'ZetaP':
        if not isinstance(other, ZetaP) or self.p != other.p:
            raise RingError(f"Ring prime mismatch: {self.p} != {getattr(other, 'p', None)}")
        return ZetaP(self.p, tuple(a - b for a, b in zip(self.coeffs, other.coeffs)))

    def __neg__(self) -> 'ZetaP':
        return ZetaP(self.p, tuple(-c for c in self.coeffs))

    def __mul__(self, other: Union['ZetaP', 'RationalZetaP', int]) -> Union['ZetaP', 'RationalZetaP']:
        if isinstance(other, int):
            return ZetaP(self.p, tuple(c * other for c in self.coeffs))
        from turing.exact.ring.rational import RationalZetaP
        if isinstance(other, RationalZetaP):
            return other * self
        if not isinstance(other, ZetaP) or self.p != other.p:
            raise RingError(f"Ring prime mismatch: {self.p} != {getattr(other, 'p', None)}")
        conv = convolution(self.coeffs, other.coeffs)
        return ZetaP(self.p, ZetaP.reduce(conv, self.p))

    def __rmul__(self, other: int) -> 'ZetaP':
        return self * other

    def pow(self, n: int) -> 'ZetaP':
        if n < 0:
            raise ValueError("Non-negative power required for ring exponentiation")
        res = ZetaP.one(self.p)
        base = self
        while n > 0:
            if n % 2 == 1:
                res = res * base
            base = base * base
            n //= 2
        return res

    def __pow__(self, n: int) -> 'ZetaP':
        return self.pow(n)

    @classmethod
    def zeta_power(cls, k: int, p: int) -> 'ZetaP':
        k = k % p
        if k == 0:
            return cls.one(p)
        if k < p - 1:
            c = [0] * (p - 1)
            c[k] = 1
            return cls(p, c)
        return cls(p, [-1] * (p - 1))

    def galois_conjugate(self, k: int) -> 'ZetaP':
        if gcd(k, self.p) != 1:
            raise ValueError(f"k={k} must be coprime to p={self.p}")
        res = ZetaP.zero(self.p)
        for i, coeff in enumerate(self.coeffs):
            if coeff != 0:
                res = res + (ZetaP.zeta_power(i * k, self.p) * coeff)
        return res

    def conjugate(self) -> 'ZetaP':
        return self.galois_conjugate(self.p - 1)

    def norm(self) -> int:
        prod = ZetaP.one(self.p)
        for k in range(1, self.p):
            prod = prod * self.galois_conjugate(k)
        if not all(c == 0 for c in prod.coeffs[1:]):
            raise RingError("Product of Galois conjugates is not in Z; ring arithmetic error")
        return prod.coeffs[0]

    def is_unit(self) -> bool:
        return self.norm() in (1, -1)

    def inverse(self) -> 'ZetaP':
        if not self.is_unit():
            raise NonUnitError(f"{self} is not a unit in Z[zeta_{self.p}]; inverse lives in Q(zeta_{self.p})")
        return ZetaP.one(self.p).exact_div(self)

    def exact_div(self, other: 'ZetaP') -> 'ZetaP':
        """
        Exact quotient a / b over an integral domain:
        a / b = a * (prod_{k!=1} sigma_k(b)) / N(b).
        """
        if other == ZetaP.zero(self.p):
            raise ZeroDivisionError("Exact division by zero in ring")
        N = other.norm()
        cofactor = ZetaP.one(self.p)
        for k in range(2, self.p):
            cofactor = cofactor * other.galois_conjugate(k)
        num = self * cofactor
        if not all(c % N == 0 for c in num.coeffs):
            raise RingError("Exact algebraic division failed: remainder nonzero")
        return ZetaP(self.p, tuple(c // N for c in num.coeffs))

    def field_inverse(self) -> 'RationalZetaP':
        """
        Exact inversion in the cyclotomic field Q(zeta_p).
        Lifts the ring unit obstruction to the quotient field.
        """
        if self == ZetaP.zero(self.p):
            raise ZeroDivisionError("Cannot invert zero in Q(zeta_p)")
        from turing.exact.ring.rational import RationalZetaP
        N = self.norm()
        cofactor = ZetaP.one(self.p)
        for k in range(2, self.p):
            cofactor = cofactor * self.galois_conjugate(k)
        return RationalZetaP(cofactor, N)

    @classmethod
    def gauss_sum(cls, p: int) -> 'ZetaP':
        """Calculates quadratic Gauss sum g = sum_{k=1}^{p-1} (k/p) * zeta_p^k."""
        res = cls.zero(p)
        for k in range(1, p):
            sym = legendre_symbol(k, p)
            if sym != 0:
                res = res + (cls.zeta_power(k, p) * sym)
        return res

    def verify_gauss_sum(self) -> bool:
        """Verifies that g^2 = (-1)^{(p-1)/2} * p."""
        g = ZetaP.gauss_sum(self.p)
        g_sq = g * g
        expected = self.p if (self.p % 4 == 1) else -self.p
        return g_sq == ZetaP.from_int(expected, self.p)

    def __repr__(self) -> str:
        return f"ZetaP(p={self.p}, coeffs={self.coeffs})"
