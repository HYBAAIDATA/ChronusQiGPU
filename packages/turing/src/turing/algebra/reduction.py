"""Exact residue checksums: ring homomorphisms from cyclotomic integers to F_p.

For a prime p and an integer r with Phi_n(r) = 0 (mod p), the assignment
zeta_n -> r extends to a ring homomorphism from Z[zeta_n] onto F_p = Z/pZ,
and further to every element of Q(zeta_n) whose coefficient denominators are
prime to p. The map is many-to-one: a residue is an exact checksum of an
amplitude, never a replacement for it. Amplitudes always live in Q(zeta_n).

The standard instance (:func:`f257_residue_map`) uses n = 256, p = 257, r = 3.
Phi_256(x) = x^128 + 1, and 3 has multiplicative order 256 modulo 257, so
3^128 = -1 (mod 257). The odd powers of 3 are 128 distinct roots of x^128 + 1
modulo 257, so the prime 257 splits completely in Z[zeta_256]. Elements of
Q(zeta_m) with m dividing 256 are lifted first, so zeta_m -> 3^(256/m); for
example zeta_32 -> 3^8 = 136 (order 32) and zeta_16 -> 3^16 = 249 = -8
(order 16). The integer 2 also has order 16 modulo 257 (2^8 = -1), so 2 is
another root of Phi_16 = x^8 + 1 modulo 257.
"""

from __future__ import annotations

from fractions import Fraction
from math import gcd
from typing import Union

from .cyclotomic import CyclotomicElement, CyclotomicField, cyclotomic_polynomial, is_prime

__all__ = [
    "CyclotomicResidueMap",
    "f257_residue_map",
    "inverse_mod",
    "multiplicative_order",
]


def _check_int(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an int, got {type(value).__name__}")
    return value


def inverse_mod(value: int, modulus: int) -> int:
    """Inverse of ``value`` modulo ``modulus`` by the extended Euclidean algorithm."""
    _check_int(value, "value")
    _check_int(modulus, "modulus")
    if modulus < 2:
        raise ValueError("modulus must be at least 2")
    r0, r1 = modulus, value % modulus
    s0, s1 = 0, 1
    while r1:
        q = r0 // r1
        r0, r1 = r1, r0 - q * r1
        s0, s1 = s1, s0 - q * s1
    if r0 != 1:
        raise ValueError(f"{value} is not invertible modulo {modulus}")
    return s0 % modulus


def multiplicative_order(g: int, modulus: int) -> int:
    """Smallest k >= 1 with g^k = 1 (mod modulus), found by repeated exact multiplication."""
    _check_int(g, "g")
    _check_int(modulus, "modulus")
    if modulus < 2:
        raise ValueError("modulus must be at least 2")
    if gcd(g, modulus) != 1:
        raise ValueError(f"{g} is not a unit modulo {modulus}")
    base = g % modulus
    value = base
    k = 1
    while value != 1:
        value = value * base % modulus
        k += 1
    return k


class CyclotomicResidueMap:
    """The ring homomorphism Z[zeta_n] -> F_p with zeta_n -> root, as an exact checksum."""

    __slots__ = ("_field", "_prime", "_root", "_powers")

    def __init__(self, n: int, prime: int, root: int) -> None:
        field = CyclotomicField(n)
        _check_int(prime, "prime")
        _check_int(root, "root")
        if not is_prime(prime):
            raise ValueError(f"{prime} is not prime")
        residue = root % prime
        value = 0
        for coefficient in reversed(cyclotomic_polynomial(n)):
            value = (value * residue + coefficient) % prime
        if value:
            raise ValueError(f"Phi_{n}({root}) = {value} (mod {prime}), not 0; zeta_{n} -> {root} "
                             f"is not a ring homomorphism to F_{prime}")
        powers = []
        current = 1
        for _ in range(field.degree):
            powers.append(current)
            current = current * residue % prime
        self._field = field
        self._prime = prime
        self._root = residue
        self._powers = tuple(powers)

    @property
    def field(self) -> CyclotomicField:
        return self._field

    @property
    def prime(self) -> int:
        return self._prime

    @property
    def root(self) -> int:
        """Image of zeta_n in F_p."""
        return self._root

    def image_of_zeta(self, m: int) -> int:
        """Image of zeta_m for m dividing n, namely root^(n/m) mod p."""
        _check_int(m, "m")
        if m < 1 or self._field.n % m:
            raise ValueError(f"zeta_{m} lies in Q(zeta_{self._field.n}) under this map only if {m} divides "
                             f"{self._field.n}")
        exponent = self._field.n // m
        value = 1
        for _ in range(exponent):
            value = value * self._root % self._prime
        return value

    def conjugate_map(self) -> "CyclotomicResidueMap":
        """The map zeta_n -> root^(-1); reduce(conj(a)) equals conjugate_map().reduce(a)."""
        return CyclotomicResidueMap(self._field.n, self._prime, inverse_mod(self._root, self._prime))

    def reduce(self, element: Union[CyclotomicElement, int, Fraction]) -> int:
        """Residue in F_p of an element of Q(zeta_m), m | n, with denominators prime to p."""
        p = self._prime
        if isinstance(element, (int, Fraction)) and not isinstance(element, bool):
            value = Fraction(element)
            if value.denominator % p == 0:
                raise ValueError(f"denominator of {value} is divisible by {p}; the residue is undefined")
            return value.numerator * inverse_mod(value.denominator, p) % p
        if not isinstance(element, CyclotomicElement):
            raise TypeError("element must be a CyclotomicElement or a rational")
        lifted = self._field.lift(element)
        total = 0
        for coefficient, power in zip(lifted.coefficients, self._powers):
            if coefficient:
                denominator = coefficient.denominator
                if denominator % p == 0:
                    raise ValueError(f"coefficient {coefficient} has a denominator divisible by {p}; "
                                     f"the residue is undefined")
                total += coefficient.numerator * power * inverse_mod(denominator, p)
        return total % p


_F257_MAP: list = []


def f257_residue_map() -> CyclotomicResidueMap:
    """The checksum Z[zeta_256] -> F_257 with zeta_256 -> 3 (Phi_256(3) = 0 mod 257)."""
    if not _F257_MAP:
        _F257_MAP.append(CyclotomicResidueMap(256, 257, 3))
    return _F257_MAP[0]
