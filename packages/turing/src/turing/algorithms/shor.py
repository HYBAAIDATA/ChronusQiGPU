"""Shor order finding and factoring with exact outcome distributions.

For N, a with gcd(a, N) = 1 and a register of size Q = 2^t >= N^2, the state
after modular exponentiation and the QFT has amplitude
(1/Q) sum_{x: f(x) = v} zeta_Q^(x y) on |y>|v>, with f(x) = a^x mod N computed
by explicit square-and-multiply. Folding the inputs by their f-value is
lossless, and
    P(y) = (1/Q^2) sum_v |S_{y,v}|^2,   S_{y,v} = sum_{x in class v} zeta_Q^(x y).
Expanding |S_{y,v}|^2 as a sum over ordered pairs of class members gives
P(y) = (1/Q^2) sum_d K(d) zeta_Q^(d y), where K(d) counts the pairs (x, x')
in a common class with x - x' = d (mod Q): the pairwise-difference helper,
applied once per class. The order of a is never used in this part.

Classical post-processing runs exact continued fractions on y/Q for every y
in the exact support and verifies each candidate order with modexp. The
success probability is a field element; it is real and nonnegative as a sum
of squared moduli, and its positivity follows from the exact zero test.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import gcd
from typing import Optional

from ..algebra.cyclotomic import CyclotomicElement, CyclotomicField, is_prime, pairwise_difference_counts

__all__ = [
    "FactorResult",
    "MAX_REGISTER_QUBITS",
    "OrderFindingResult",
    "continued_fraction",
    "convergents",
    "factor",
    "find_order",
    "modexp",
    "order_distribution",
    "register_qubits",
]

MAX_REGISTER_QUBITS = 12


def _check_int(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an int")
    return value


def modexp(base: int, exponent: int, modulus: int) -> int:
    """base^exponent mod modulus by explicit square-and-multiply on ints."""
    _check_int(base, "base")
    _check_int(exponent, "exponent")
    _check_int(modulus, "modulus")
    if modulus < 1:
        raise ValueError("modulus must be positive")
    if exponent < 0:
        raise ValueError("exponent must be non-negative")
    result = 1 % modulus
    square = base % modulus
    remaining = exponent
    while remaining:
        if remaining & 1:
            result = result * square % modulus
        square = square * square % modulus
        remaining >>= 1
    return result


def continued_fraction(value: Fraction) -> tuple[int, ...]:
    """Partial quotients of a rational number (exact integer Euclid)."""
    value = Fraction(value)
    p, q = value.numerator, value.denominator
    terms = []
    while q:
        quotient, remainder = divmod(p, q)
        terms.append(quotient)
        p, q = q, remainder
    return tuple(terms)


def convergents(value: Fraction) -> tuple[Fraction, ...]:
    """All convergents p_k / q_k of a rational number, in order."""
    h_prev, h = 0, 1
    k_prev, k = 1, 0
    result = []
    for a in continued_fraction(value):
        h_prev, h = h, a * h + h_prev
        k_prev, k = k, a * k + k_prev
        result.append(Fraction(h, k))
    return tuple(result)


def register_qubits(modulus: int) -> int:
    """Smallest t with 2^t >= N^2."""
    _check_int(modulus, "modulus")
    if modulus < 2:
        raise ValueError("modulus must be at least 2")
    target = modulus * modulus
    t = 0
    while (1 << t) < target:
        t += 1
    return t


def _check_order_inputs(modulus: int, base: int, t: Optional[int]) -> int:
    _check_int(modulus, "N")
    _check_int(base, "a")
    if modulus < 2:
        raise ValueError("N must be at least 2")
    if not 1 <= base < modulus:
        raise ValueError(f"a must lie in 1 .. {modulus - 1}")
    if gcd(base, modulus) != 1:
        raise ValueError(f"gcd({base}, {modulus}) = {gcd(base, modulus)}; order finding needs a unit modulo N")
    if t is None:
        t = register_qubits(modulus)
    _check_int(t, "t")
    if (1 << t) < modulus * modulus:
        raise ValueError(f"register of 2^{t} values is smaller than N^2 = {modulus * modulus}")
    if t > MAX_REGISTER_QUBITS:
        raise ValueError(f"t = {t} exceeds MAX_REGISTER_QUBITS = {MAX_REGISTER_QUBITS}: exact evaluation costs "
                         f"order Q^2 = 2^{2 * t} terms")
    return t


def order_distribution(modulus: int, base: int, t: Optional[int] = None) -> tuple[CyclotomicElement, ...]:
    """Exact P(y) for every y in [0, 2^t), as elements of Q(zeta_Q)."""
    t = _check_order_inputs(modulus, base, t)
    size = 1 << t
    field = CyclotomicField(size)
    classes: dict[int, list[int]] = {}
    for x in range(size):
        classes.setdefault(modexp(base, x, modulus), []).append(x)
    profile = [0] * size
    for members in classes.values():
        for d, count in pairwise_difference_counts(members, size).items():
            profile[d] += count
    nonzero = [(d, count) for d, count in enumerate(profile) if count]
    denominator = size * size
    probabilities = []
    for y in range(size):
        terms: dict[int, int] = {}
        for d, count in nonzero:
            e = d * y % size
            terms[e] = terms.get(e, 0) + count
        probabilities.append(field.from_exponents(terms, denominator=denominator))
    return tuple(probabilities)


def _candidate_order(y: int, size: int, modulus: int, base: int) -> Optional[int]:
    for convergent in convergents(Fraction(y, size)):
        q = convergent.denominator
        if q >= modulus:
            break
        if modexp(base, q, modulus) == 1:
            return q
    return None


@dataclass(frozen=True)
class OrderFindingResult:
    modulus: int
    base: int
    register_qubits: int
    probabilities: tuple[CyclotomicElement, ...]
    support: tuple[int, ...]
    candidates: tuple[tuple[int, Optional[int]], ...]
    order: Optional[int]
    success_probability: CyclotomicElement

    @property
    def register_size(self) -> int:
        return 1 << self.register_qubits

    @property
    def factors(self) -> Optional[tuple[int, int]]:
        """(gcd(a^(r/2) - 1, N), gcd(a^(r/2) + 1, N)) when r is even and a^(r/2) != -1 mod N."""
        r = self.order
        if r is None or r % 2:
            return None
        half = modexp(self.base, r // 2, self.modulus)
        if half == self.modulus - 1:
            return None
        return gcd(half - 1, self.modulus), gcd(half + 1, self.modulus)


def find_order(modulus: int, base: int, t: Optional[int] = None) -> OrderFindingResult:
    """Exact order finding: distribution, support, verified order and success probability."""
    t = _check_order_inputs(modulus, base, t)
    size = 1 << t
    probabilities = order_distribution(modulus, base, t)
    support = tuple(y for y, p in enumerate(probabilities) if not p.is_zero())
    candidates = tuple((y, _candidate_order(y, size, modulus, base)) for y in support)
    verified = [c for _, c in candidates if c is not None]
    order = min(verified) if verified else None
    success = CyclotomicField(size).zero
    if order is not None:
        for y, candidate in candidates:
            if candidate == order:
                success = success + probabilities[y]
    return OrderFindingResult(modulus=modulus, base=base, register_qubits=t, probabilities=probabilities,
                              support=support, candidates=candidates, order=order,
                              success_probability=success)


@dataclass(frozen=True)
class FactorResult:
    modulus: int
    factors: tuple[int, int]
    base: int
    method: str
    order_finding: Optional[OrderFindingResult]


def factor(modulus: int) -> FactorResult:
    """Split a composite N into two nontrivial factors, trying a = 2, 3, 4, ... in order.

    A base sharing a factor with N yields that factor by gcd (method 'gcd');
    otherwise the order is found exactly and gcd(a^(r/2) +- 1, N) is used
    (method 'order').
    """
    _check_int(modulus, "N")
    if modulus < 4 or is_prime(modulus):
        raise ValueError(f"N = {modulus} must be composite")
    for base in range(2, modulus):
        common = gcd(base, modulus)
        if common > 1:
            return FactorResult(modulus, tuple(sorted((common, modulus // common))), base, "gcd", None)
        result = find_order(modulus, base)
        split = result.factors
        if split is None:
            continue
        d = split[0] if 1 < split[0] < modulus else split[1]
        return FactorResult(modulus, tuple(sorted((d, modulus // d))), base, "order", result)
    raise ArithmeticError(f"no base split {modulus}")
