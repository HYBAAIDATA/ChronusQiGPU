"""Exact prime-field arithmetic by discrete-logarithm table lookup.

``PrimeField(p)`` tabulates the cyclic group F_p* once:

* ``EXP[k] = g**k mod p`` for ``0 <= k < p - 1``;
* ``LOG[y] = k`` with ``g**k = y (mod p)``, for ``1 <= y < p``;

where ``g`` is the smallest primitive root of ``p``. The primitive root is
found by testing each candidate's order against the prime factorisation of
``p - 1``; the table build then checks that the powers of ``g`` visit every
nonzero residue exactly once and return to 1. The cyclic structure is
therefore verified in code, never assumed.

Cost model
----------
* Construction: O(sqrt(p)) trial divisions (primality of ``p`` and the
  factorisation of ``p - 1``), a primitive-root scan upwards from 1 (one
  modular power per prime factor of ``p - 1`` per candidate), then O(p) time
  and O(p) memory for the two tables.
* Each query afterwards (``mul``, ``div``, ``inverse``, ``pow``,
  ``discrete_log``, ``antilog``, ``zech_log``) is at most three table reads
  plus one reduction of an exponent modulo ``p - 1``. The work does not depend
  on which field elements are involved. ``pow`` additionally multiplies the
  stored logarithm by the caller's exponent, an integer product whose cost
  grows with the number of digits of that exponent.

Scope
-----
Fields with ``p > MAX_FIELD_ORDER`` (2**20) are refused with ``ValueError``
before any primality test or table work. Tables of size ``p - 1`` must be
built and held in memory, which is only possible for small fields.
Tabulating a small field is not a general discrete-logarithm method and says
nothing about the field sizes used in cryptography.

All arithmetic is exact integer arithmetic.
"""

from __future__ import annotations

from array import array
from math import gcd, isqrt

__all__ = ["GF257", "MAX_FIELD_ORDER", "PrimeField"]

#: Inclusive upper bound on the characteristic p accepted by PrimeField.
MAX_FIELD_ORDER = 1 << 20


def _require_int(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an int, not {type(value).__name__}")
    return value


def _is_prime(n: int) -> bool:
    """Deterministic trial division; callers bound n by MAX_FIELD_ORDER first."""
    if n < 2:
        return False
    if n % 2 == 0:
        return n == 2
    return all(n % divisor for divisor in range(3, isqrt(n) + 1, 2))


def _distinct_prime_factors(n: int) -> tuple[int, ...]:
    """Distinct prime factors of n >= 1 in increasing order, by trial division."""
    factors = []
    divisor = 2
    while divisor * divisor <= n:
        if n % divisor == 0:
            factors.append(divisor)
            while n % divisor == 0:
                n //= divisor
        divisor += 1 if divisor == 2 else 2
    if n > 1:
        factors.append(n)
    return tuple(factors)


def _smallest_primitive_root(p: int, group_order: int, factors: tuple[int, ...]) -> int:
    """Smallest g with g**(group_order // q) != 1 (mod p) for every prime q | p - 1."""
    for candidate in range(1, p):
        if all(pow(candidate, group_order // q, p) != 1 for q in factors):
            return candidate
    raise ArithmeticError(f"no primitive root modulo {p}")


def _build_tables(p: int, generator: int, group_order: int) -> tuple[array, array]:
    """EXP and LOG tables, checking that the generator has order exactly p - 1."""
    # 'H' holds 0..65535 and 'L' at least 0..2**32 - 1 on every platform.
    typecode = "H" if p <= 1 << 16 else "L"
    exp_table = array(typecode, [0]) * group_order
    log_table = array(typecode, [0]) * p
    visited = bytearray(p)
    value = 1
    for k in range(group_order):
        if visited[value]:
            raise ArithmeticError(f"{generator} has order {k} < {group_order} modulo {p}")
        visited[value] = 1
        exp_table[k] = value
        log_table[value] = k
        value = value * generator % p
    if value != 1:
        raise ArithmeticError(f"{generator}**{group_order} is not 1 modulo {p}")
    return exp_table, log_table


class PrimeField:
    """The prime field F_p, ``p <= MAX_FIELD_ORDER``, with exact EXP/LOG tables.

    Operands are ints interpreted modulo ``p`` (bools and non-ints raise
    ``TypeError``); results are canonical representatives in ``[0, p)``.
    Exponents are reduced modulo the group order ``p - 1``. Instances are
    immutable and compare equal exactly when their characteristics are equal.

    ``max_order`` may tighten the size guard for a caller; it cannot raise it
    above ``MAX_FIELD_ORDER``.
    """

    __slots__ = ("_p", "_group_order", "_factors", "_generator", "_exp", "_log")

    def __init__(self, p: int, *, max_order: int = MAX_FIELD_ORDER) -> None:
        _require_int(p, "p")
        _require_int(max_order, "max_order")
        if not 2 <= max_order <= MAX_FIELD_ORDER:
            raise ValueError(
                f"max_order must lie in [2, {MAX_FIELD_ORDER}]: table lookup is "
                "limited to small fields"
            )
        if p > max_order:
            raise ValueError(
                f"p = {p} exceeds max_order = {max_order}: EXP/LOG tables of size "
                "p - 1 are only built for small fields, and tabulating a field is "
                "not a general discrete-logarithm method"
            )
        if not _is_prime(p):
            raise ValueError(f"p = {p} is not prime")
        group_order = p - 1
        factors = _distinct_prime_factors(group_order)
        generator = _smallest_primitive_root(p, group_order, factors)
        self._exp, self._log = _build_tables(p, generator, group_order)
        self._p = p
        self._group_order = group_order
        self._factors = factors
        self._generator = generator

    @property
    def p(self) -> int:
        """The characteristic p (also the number of field elements)."""
        return self._p

    @property
    def generator(self) -> int:
        """The smallest primitive root g modulo p; its order is exactly p - 1."""
        return self._generator

    @property
    def group_order(self) -> int:
        """Order p - 1 of the multiplicative group F_p*."""
        return self._group_order

    @property
    def group_order_factors(self) -> tuple[int, ...]:
        """Distinct primes dividing p - 1, in increasing order."""
        return self._factors

    def reduce(self, a: int) -> int:
        """Canonical representative of a in [0, p)."""
        return _require_int(a, "a") % self._p

    def mul(self, a: int, b: int) -> int:
        """a * b in F_p: EXP[(LOG[a] + LOG[b]) mod (p - 1)], or 0 if a factor is 0."""
        a, b = self.reduce(a), self.reduce(b)
        if a == 0 or b == 0:
            return 0
        return self._exp[(self._log[a] + self._log[b]) % self._group_order]

    def div(self, a: int, b: int) -> int:
        """a / b in F_p: EXP[(LOG[a] - LOG[b]) mod (p - 1)]; ZeroDivisionError if b = 0."""
        a, b = self.reduce(a), self.reduce(b)
        if b == 0:
            raise ZeroDivisionError("division by 0 in F_p")
        if a == 0:
            return 0
        return self._exp[(self._log[a] - self._log[b]) % self._group_order]

    def inverse(self, a: int) -> int:
        """a**-1 in F_p: EXP[-LOG[a] mod (p - 1)]; ZeroDivisionError if a = 0."""
        a = self.reduce(a)
        if a == 0:
            raise ZeroDivisionError("0 has no multiplicative inverse")
        return self._exp[-self._log[a] % self._group_order]

    def pow(self, a: int, e: int) -> int:
        """a**e in F_p for any int e: EXP[LOG[a] * e mod (p - 1)].

        For a = 0: 0**e = 0 for e > 0, 0**0 = 1 (as in ``pow(0, 0, p)``), and a
        negative e raises ZeroDivisionError.
        """
        a = self.reduce(a)
        _require_int(e, "e")
        if a == 0:
            if e > 0:
                return 0
            if e == 0:
                return 1
            raise ZeroDivisionError("0 has no negative powers")
        return self._exp[self._log[a] * e % self._group_order]

    def discrete_log(self, y: int) -> int:
        """The k in [0, p - 1) with g**k = y, read from LOG; ValueError if y = 0."""
        y = self.reduce(y)
        if y == 0:
            raise ValueError("0 has no discrete logarithm")
        return self._log[y]

    def antilog(self, k: int) -> int:
        """g**k in F_p, read from EXP after reducing k modulo p - 1."""
        return self._exp[_require_int(k, "k") % self._group_order]

    def zech_log(self, n: int) -> int | None:
        """Zech logarithm: the k in [0, p - 1) with g**k = 1 + g**n, or None.

        None is returned exactly when 1 + g**n = 0, i.e. g**n = -1, which happens
        for n = (p - 1) // 2 modulo p - 1. Addition then becomes exponent
        arithmetic: g**a + g**b = g**(a + zech_log(b - a)).
        """
        total = (1 + self.antilog(n)) % self._p
        if total == 0:
            return None
        return self._log[total]

    def order(self, a: int) -> int:
        """Multiplicative order of a != 0: (p - 1) // gcd(LOG[a], p - 1)."""
        a = self.reduce(a)
        if a == 0:
            raise ValueError("0 has no multiplicative order")
        return self._group_order // gcd(self._log[a], self._group_order)

    def is_quadratic_residue(self, a: int) -> bool:
        """True iff a is a nonzero square, i.e. LOG[a] is even; 0 gives False."""
        a = self.reduce(a)
        if a == 0:
            return False
        return self._log[a] % 2 == 0

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PrimeField):
            return NotImplemented
        return self._p == other._p

    def __hash__(self) -> int:
        return hash((PrimeField, self._p))

    def __repr__(self) -> str:
        return f"PrimeField(p={self._p}, generator={self._generator})"


#: F_257 (257 = 2**8 + 1): generator 3, multiplicative group order 256 = 2**8.
GF257 = PrimeField(257)
