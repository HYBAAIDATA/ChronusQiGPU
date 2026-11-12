"""Exact arithmetic in the cyclotomic fields Q(zeta_n).

Q(zeta_n) is the subfield of the complex numbers generated over the rationals
by zeta_n = exp(2 pi i / n). An element is stored as its rational coordinates
in the power basis 1, z, z^2, ..., z^(phi(n) - 1), where z denotes zeta_n,
reduced modulo the n-th cyclotomic polynomial Phi_n. Coefficients are
``fractions.Fraction`` values and every reduction is integer polynomial
arithmetic, so every result is exact with zero rounding.
"""

from __future__ import annotations

from fractions import Fraction
from math import gcd, lcm
from typing import Iterable, Mapping, Union

Rational = Union[int, Fraction]

__all__ = [
    "CyclotomicElement",
    "CyclotomicField",
    "abs2_of_progression",
    "abs2_of_root_sum",
    "cyclotomic_polynomial",
    "divisors",
    "euler_phi",
    "factorize",
    "is_prime",
    "mobius",
    "pairwise_difference_counts",
    "progression_difference_counts",
]


def _check_positive_int(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{name} must be a positive integer, got {value!r}")
    return value


def _check_int(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an int, got {type(value).__name__}")
    return value


def _as_fraction(value: object, name: str = "coefficient") -> Fraction:
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return Fraction(value)
    raise TypeError(f"{name} must be an int or fractions.Fraction, got {type(value).__name__}")


# ---------------------------------------------------------------------------
# Elementary number theory (exact integers only)
# ---------------------------------------------------------------------------

def factorize(n: int) -> dict[int, int]:
    """Return the prime factorisation of ``n`` as ``{prime: exponent}`` (trial division)."""
    _check_positive_int(n, "n")
    factors: dict[int, int] = {}
    remaining = n
    p = 2
    while p * p <= remaining:
        while remaining % p == 0:
            factors[p] = factors.get(p, 0) + 1
            remaining //= p
        p = 3 if p == 2 else p + 2
    if remaining > 1:
        factors[remaining] = factors.get(remaining, 0) + 1
    return factors


def is_prime(n: int) -> bool:
    """Deterministic primality test by trial division."""
    _check_int(n, "n")
    if n < 2:
        return False
    return factorize(n) == {n: 1}


def euler_phi(n: int) -> int:
    """Euler's totient phi(n) = [Q(zeta_n) : Q]."""
    result = n
    for p in factorize(n):
        result = result // p * (p - 1)
    return result


def mobius(n: int) -> int:
    """The Mobius function mu(n)."""
    factors = factorize(n)
    if any(exponent > 1 for exponent in factors.values()):
        return 0
    return -1 if len(factors) % 2 else 1


def divisors(n: int) -> tuple[int, ...]:
    """All positive divisors of ``n`` in increasing order."""
    found = [1]
    for p, exponent in factorize(n).items():
        found = [d * p ** k for d in found for k in range(exponent + 1)]
    return tuple(sorted(found))


# ---------------------------------------------------------------------------
# Cyclotomic polynomials
# ---------------------------------------------------------------------------

_PHI_CACHE: dict[int, tuple[int, ...]] = {}


def _divide_exactly(numerator: list[int], divisor: tuple[int, ...]) -> list[int]:
    """Exact quotient of integer polynomials by a monic divisor (constant term first)."""
    degree = len(divisor) - 1
    if divisor[-1] != 1:
        raise ValueError("divisor must be monic")
    tail = [(j, c) for j, c in enumerate(divisor[:-1]) if c]
    work = list(numerator)
    quotient = [0] * (len(work) - degree)
    for k in range(len(work) - 1, degree - 1, -1):
        c = work[k]
        if c:
            base = k - degree
            quotient[base] = c
            for j, m in tail:
                work[base + j] -= c * m
    if any(work[:degree]):
        raise ArithmeticError("cyclotomic division left a nonzero remainder")
    return quotient


def cyclotomic_polynomial(n: int) -> tuple[int, ...]:
    """Integer coefficients of Phi_n, constant term first.

    Computed exactly by integer polynomial division:
    Phi_n = (x^n - 1) / prod_{d | n, d < n} Phi_d.
    """
    _check_positive_int(n, "n")
    cached = _PHI_CACHE.get(n)
    if cached is not None:
        return cached
    quotient = [-1] + [0] * (n - 1) + [1]
    for d in divisors(n)[:-1]:
        quotient = _divide_exactly(quotient, cyclotomic_polynomial(d))
    result = tuple(quotient)
    _PHI_CACHE[n] = result
    return result


# ---------------------------------------------------------------------------
# Pairwise-difference helpers for |sum of roots of unity|^2
# ---------------------------------------------------------------------------

def pairwise_difference_counts(exponents: Iterable[int], modulus: int) -> dict[int, int]:
    """Count ordered pairs (i, j) by the difference (e_i - e_j) mod ``modulus``.

    The multiset is first grouped by residue, so the cost is quadratic in the
    number of distinct residues, not in the number of exponents.
    """
    _check_positive_int(modulus, "modulus")
    multiplicity: dict[int, int] = {}
    for exponent in exponents:
        residue = _check_int(exponent, "exponent") % modulus
        multiplicity[residue] = multiplicity.get(residue, 0) + 1
    items = list(multiplicity.items())
    differences: dict[int, int] = {}
    for u, count_u in items:
        for v, count_v in items:
            d = (u - v) % modulus
            differences[d] = differences.get(d, 0) + count_u * count_v
    return differences


def progression_difference_counts(step: int, length: int, modulus: int) -> dict[int, int]:
    """Pairwise differences of the progression 0, step, ..., (length - 1) * step.

    The difference d * step (|d| < length) occurs exactly length - |d| times.
    """
    _check_int(step, "step")
    _check_int(length, "length")
    _check_positive_int(modulus, "modulus")
    if length < 0:
        raise ValueError("length must be non-negative")
    counts: dict[int, int] = {}
    if length:
        counts[0] = length
    for d in range(1, length):
        weight = length - d
        forward = (d * step) % modulus
        backward = (-d * step) % modulus
        counts[forward] = counts.get(forward, 0) + weight
        counts[backward] = counts.get(backward, 0) + weight
    return counts


def abs2_of_root_sum(field: "CyclotomicField", exponents: Iterable[int]) -> "CyclotomicElement":
    """Return |sum_i zeta_n^(e_i)|^2 = sum_{i,j} zeta_n^(e_i - e_j) exactly.

    Computed by counting pairwise differences; no polynomial multiplication.
    """
    if not isinstance(field, CyclotomicField):
        raise TypeError("field must be a CyclotomicField")
    return field.from_exponents(pairwise_difference_counts(exponents, field.n))


def abs2_of_progression(field: "CyclotomicField", step: int, length: int) -> "CyclotomicElement":
    """Return |sum_{j < length} zeta_n^(j * step)|^2 exactly (closed-form difference counts)."""
    if not isinstance(field, CyclotomicField):
        raise TypeError("field must be a CyclotomicField")
    return field.from_exponents(progression_difference_counts(step, length, field.n))


# ---------------------------------------------------------------------------
# Fields and elements
# ---------------------------------------------------------------------------

class CyclotomicField:
    """The cyclotomic field Q(zeta_n) with exact power-basis arithmetic.

    Instances are shared: ``CyclotomicField(8) is CyclotomicField(8)``.
    """

    __slots__ = ("_n", "_degree", "_modulus", "_tail", "_trace_weights", "_zero", "_one")
    _instances: dict = {}

    def __new__(cls, n: int) -> "CyclotomicField":
        _check_positive_int(n, "n")
        field = cls._instances.get(n)
        if field is None:
            field = object.__new__(cls)
            modulus = cyclotomic_polynomial(n)
            degree = len(modulus) - 1
            field._n = n
            field._degree = degree
            field._modulus = modulus
            field._tail = tuple((j, c) for j, c in enumerate(modulus[:-1]) if c)
            field._trace_weights = None
            field._zero = CyclotomicElement._raw(field, (Fraction(0),) * degree)
            field._one = CyclotomicElement._raw(field, (Fraction(1),) + (Fraction(0),) * (degree - 1))
            cls._instances[n] = field
        return field

    def __reduce__(self):
        return (CyclotomicField, (self._n,))

    def __repr__(self) -> str:
        return f"CyclotomicField({self._n})"

    def __str__(self) -> str:
        return f"Q(zeta_{self._n})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CyclotomicField):
            return self._n == other._n
        return NotImplemented

    def __hash__(self) -> int:
        return hash(("CyclotomicField", self._n))

    @property
    def n(self) -> int:
        """The order of the primitive root of unity zeta_n generating the field."""
        return self._n

    @property
    def degree(self) -> int:
        """[Q(zeta_n) : Q] = phi(n) = deg Phi_n."""
        return self._degree

    @property
    def modulus(self) -> tuple[int, ...]:
        """Coefficients of Phi_n, constant term first."""
        return self._modulus

    @property
    def zero(self) -> "CyclotomicElement":
        return self._zero

    @property
    def one(self) -> "CyclotomicElement":
        return self._one

    def zeta(self, k: int = 1) -> "CyclotomicElement":
        """Return zeta_n^k (any integer k; negative powers allowed)."""
        _check_int(k, "k")
        return self.from_exponents({k % self._n: 1})

    def basis(self) -> tuple["CyclotomicElement", ...]:
        """The power basis 1, z, ..., z^(phi(n) - 1)."""
        return tuple(self.zeta(k) for k in range(self._degree))

    def from_rational(self, value: Rational) -> "CyclotomicElement":
        q = _as_fraction(value, "value")
        return CyclotomicElement._raw(self, (q,) + (Fraction(0),) * (self._degree - 1))

    def element(self, coefficients: Iterable[Rational]) -> "CyclotomicElement":
        """Return sum_k c_k z^k for any finite coefficient list (reduced modulo Phi_n)."""
        values = [_as_fraction(c) for c in coefficients]
        if len(values) == self._degree:
            return CyclotomicElement._raw(self, tuple(values))
        return self.from_exponents({k: c for k, c in enumerate(values) if c})

    def from_exponents(self, terms: Mapping[int, Rational], denominator: int = 1) -> "CyclotomicElement":
        """Return (1 / denominator) * sum_e c_e zeta_n^e for integer exponents e."""
        _check_positive_int(denominator, "denominator")
        n = self._n
        common = 1
        for coefficient in terms.values():
            if type(coefficient) is not int:
                value = _as_fraction(coefficient)
                if value.denominator != 1:
                    common = lcm(common, value.denominator)
        poly = [0] * n
        for exponent, coefficient in terms.items():
            if type(exponent) is not int:
                _check_int(exponent, "exponent")
            if type(coefficient) is int:
                poly[exponent % n] += coefficient * common
            else:
                value = _as_fraction(coefficient)
                poly[exponent % n] += value.numerator * (common // value.denominator)
        return self._from_scaled_ints(self._reduce_ints(poly), common * denominator)

    def lift(self, element: "CyclotomicElement") -> "CyclotomicElement":
        """Embed an element of Q(zeta_m) into this field Q(zeta_n); requires m | n."""
        if isinstance(element, (int, Fraction)) and not isinstance(element, bool):
            return self.from_rational(element)
        if not isinstance(element, CyclotomicElement):
            raise TypeError("element must be a CyclotomicElement or a rational")
        source = element.field
        if source is self:
            return element
        if self._n % source.n:
            raise ValueError(f"Q(zeta_{source.n}) is not embedded in Q(zeta_{self._n}) by this map; "
                             f"{source.n} does not divide {self._n}")
        stride = self._n // source.n
        return self.from_exponents({k * stride: c for k, c in enumerate(element.coefficients) if c})

    def __call__(self, value: object) -> "CyclotomicElement":
        """Coerce a rational or an element of a subfield Q(zeta_m), m | n, into this field."""
        return self.lift(value)  # type: ignore[arg-type]

    # -- internal exact helpers ------------------------------------------------

    def _reduce_ints(self, poly: list[int]) -> list[int]:
        """Reduce an integer coefficient list modulo Phi_n (in place, top down)."""
        degree = self._degree
        tail = self._tail
        for k in range(len(poly) - 1, degree - 1, -1):
            c = poly[k]
            if c:
                base = k - degree
                for j, m in tail:
                    poly[base + j] -= c * m
        if len(poly) < degree:
            poly.extend([0] * (degree - len(poly)))
        return poly[:degree]

    def _from_scaled_ints(self, numerators: list[int], denominator: int) -> "CyclotomicElement":
        if denominator == 1:
            coeffs = tuple(Fraction(c) for c in numerators)
        else:
            coeffs = tuple(Fraction(c, denominator) for c in numerators)
        return CyclotomicElement._raw(self, coeffs)

    def _trace_weight_table(self) -> tuple[Fraction, ...]:
        weights = self._trace_weights
        if weights is None:
            n = self._n
            table = []
            for k in range(self._degree):
                m = n // gcd(n, k)
                table.append(Fraction(mobius(m), euler_phi(m)))
            weights = tuple(table)
            self._trace_weights = weights
        return weights


def _common_denominator(coefficients: tuple[Fraction, ...]) -> int:
    return lcm(*(c.denominator for c in coefficients))


def _trim(poly: list[Fraction]) -> list[Fraction]:
    while poly and not poly[-1]:
        poly.pop()
    return poly


def _poly_mul(a: list[Fraction], b: list[Fraction]) -> list[Fraction]:
    if not a or not b:
        return []
    out = [Fraction(0)] * (len(a) + len(b) - 1)
    for i, u in enumerate(a):
        if u:
            for j, v in enumerate(b):
                if v:
                    out[i + j] += u * v
    return _trim(out)


def _poly_sub(a: list[Fraction], b: list[Fraction]) -> list[Fraction]:
    size = max(len(a), len(b))
    out = [(a[k] if k < len(a) else Fraction(0)) - (b[k] if k < len(b) else Fraction(0))
           for k in range(size)]
    return _trim(out)


def _poly_divmod(numerator: list[Fraction], divisor: list[Fraction]) -> tuple[list[Fraction], list[Fraction]]:
    remainder = list(numerator)
    degree = len(divisor) - 1
    lead = divisor[-1]
    if len(remainder) <= degree:
        return [], _trim(remainder)
    quotient = [Fraction(0)] * (len(remainder) - degree)
    for k in range(len(remainder) - 1, degree - 1, -1):
        c = remainder[k]
        if c:
            factor = c / lead
            base = k - degree
            quotient[base] = factor
            for j, m in enumerate(divisor):
                if m:
                    remainder[base + j] -= factor * m
    return _trim(quotient), _trim(remainder[:degree])


class CyclotomicElement:
    """An exact element of Q(zeta_n), stored in the power basis modulo Phi_n."""

    __slots__ = ("_field", "_coeffs", "_hash")

    def __init__(self, field: CyclotomicField, coefficients: Iterable[Rational]) -> None:
        if not isinstance(field, CyclotomicField):
            raise TypeError("field must be a CyclotomicField")
        values = tuple(_as_fraction(c) for c in coefficients)
        if len(values) != field.degree:
            raise ValueError(f"expected {field.degree} power-basis coefficients for {field}, got {len(values)}")
        self._field = field
        self._coeffs = values
        self._hash = None

    @classmethod
    def _raw(cls, field: CyclotomicField, coefficients: tuple[Fraction, ...]) -> "CyclotomicElement":
        element = object.__new__(cls)
        element._field = field
        element._coeffs = coefficients
        element._hash = None
        return element

    # -- basic accessors -------------------------------------------------------

    @property
    def field(self) -> CyclotomicField:
        return self._field

    @property
    def coefficients(self) -> tuple[Fraction, ...]:
        """Exact rational coordinates in the power basis 1, z, ..., z^(phi(n) - 1)."""
        return self._coeffs

    def is_zero(self) -> bool:
        """Exact zero test: every rational coordinate is zero."""
        return not any(self._coeffs)

    def __bool__(self) -> bool:
        return not self.is_zero()

    def is_rational(self) -> bool:
        return not any(self._coeffs[1:])

    def to_rational(self) -> Fraction:
        if not self.is_rational():
            raise ValueError(f"{self!r} is not a rational number")
        return self._coeffs[0]

    # -- coercion --------------------------------------------------------------

    def _coerce_pair(self, other: object):
        if isinstance(other, CyclotomicElement):
            if other._field is self._field:
                return self, other
            common = CyclotomicField(lcm(self._field.n, other._field.n))
            return common.lift(self), common.lift(other)
        if isinstance(other, (int, Fraction)) and not isinstance(other, bool):
            return self, self._field.from_rational(other)
        return None

    # -- ring operations ---------------------------------------------------------

    def __add__(self, other: object) -> "CyclotomicElement":
        if isinstance(other, (int, Fraction)) and not isinstance(other, bool):
            coeffs = (self._coeffs[0] + other,) + self._coeffs[1:]
            return CyclotomicElement._raw(self._field, coeffs)
        pair = self._coerce_pair(other)
        if pair is None:
            return NotImplemented
        a, b = pair
        return CyclotomicElement._raw(a._field, tuple(x + y for x, y in zip(a._coeffs, b._coeffs)))

    __radd__ = __add__

    def __neg__(self) -> "CyclotomicElement":
        return CyclotomicElement._raw(self._field, tuple(-c for c in self._coeffs))

    def __pos__(self) -> "CyclotomicElement":
        return self

    def __sub__(self, other: object) -> "CyclotomicElement":
        if isinstance(other, (int, Fraction)) and not isinstance(other, bool):
            coeffs = (self._coeffs[0] - other,) + self._coeffs[1:]
            return CyclotomicElement._raw(self._field, coeffs)
        pair = self._coerce_pair(other)
        if pair is None:
            return NotImplemented
        a, b = pair
        return CyclotomicElement._raw(a._field, tuple(x - y for x, y in zip(a._coeffs, b._coeffs)))

    def __rsub__(self, other: object) -> "CyclotomicElement":
        result = self.__sub__(other)
        if result is NotImplemented:
            return NotImplemented
        return -result

    def _scale(self, factor: Fraction) -> "CyclotomicElement":
        return CyclotomicElement._raw(self._field, tuple(c * factor for c in self._coeffs))

    def _multiply_same_field(self, other: "CyclotomicElement") -> "CyclotomicElement":
        field = self._field
        a, b = self._coeffs, other._coeffs
        den_a = _common_denominator(a)
        den_b = _common_denominator(b)
        ints_a = [c.numerator * (den_a // c.denominator) for c in a]
        nonzero_b = [(j, c.numerator * (den_b // c.denominator)) for j, c in enumerate(b) if c]
        product = [0] * (len(a) + len(b) - 1)
        for i, u in enumerate(ints_a):
            if u:
                for j, v in nonzero_b:
                    product[i + j] += u * v
        return field._from_scaled_ints(field._reduce_ints(product), den_a * den_b)

    def __mul__(self, other: object) -> "CyclotomicElement":
        if isinstance(other, (int, Fraction)) and not isinstance(other, bool):
            return self._scale(Fraction(other))
        pair = self._coerce_pair(other)
        if pair is None:
            return NotImplemented
        a, b = pair
        return a._multiply_same_field(b)

    __rmul__ = __mul__

    def inverse(self) -> "CyclotomicElement":
        """Multiplicative inverse via the extended Euclidean algorithm on Q[x] modulo Phi_n."""
        if self.is_zero():
            raise ZeroDivisionError("zero has no multiplicative inverse")
        field = self._field
        if self.is_rational():
            return field.from_rational(1 / self._coeffs[0])
        r0 = [Fraction(c) for c in field.modulus]
        r1 = _trim(list(self._coeffs))
        s0: list[Fraction] = []
        s1 = [Fraction(1)]
        while len(r1) > 1:
            quotient, remainder = _poly_divmod(r0, r1)
            r0, r1 = r1, remainder
            s0, s1 = s1, _poly_sub(s0, _poly_mul(quotient, s1))
        if not r1:
            raise ArithmeticError("element is not invertible; Phi_n must be irreducible")
        constant = r1[0]
        return field.element([c / constant for c in s1])

    def __truediv__(self, other: object) -> "CyclotomicElement":
        if isinstance(other, (int, Fraction)) and not isinstance(other, bool):
            if other == 0:
                raise ZeroDivisionError("division by zero")
            return self._scale(1 / Fraction(other))
        pair = self._coerce_pair(other)
        if pair is None:
            return NotImplemented
        a, b = pair
        return a._multiply_same_field(b.inverse())

    def __rtruediv__(self, other: object) -> "CyclotomicElement":
        if isinstance(other, (int, Fraction)) and not isinstance(other, bool):
            return self.inverse()._scale(Fraction(other))
        return NotImplemented

    def __pow__(self, exponent: int) -> "CyclotomicElement":
        if not isinstance(exponent, int) or isinstance(exponent, bool):
            return NotImplemented
        if exponent < 0:
            return self.inverse() ** (-exponent)
        result = self._field.one
        base = self
        remaining = exponent
        while remaining:
            if remaining & 1:
                result = result * base
            remaining >>= 1
            if remaining:
                base = base * base
        return result

    # -- automorphisms -----------------------------------------------------------

    def galois(self, j: int) -> "CyclotomicElement":
        """Apply the Galois automorphism sigma_j : zeta_n -> zeta_n^j (gcd(j, n) = 1)."""
        _check_int(j, "j")
        n = self._field.n
        if gcd(j, n) != 1:
            raise ValueError(f"sigma_{j} is an automorphism of Q(zeta_{n}) only when gcd({j}, {n}) = 1")
        return self._field.from_exponents({(j * k) % n: c for k, c in enumerate(self._coeffs) if c})

    def conjugate(self) -> "CyclotomicElement":
        """Complex conjugation: zeta_n^k -> zeta_n^(-k)."""
        n = self._field.n
        return self._field.from_exponents({(-k) % n: c for k, c in enumerate(self._coeffs) if c})

    def abs2(self) -> "CyclotomicElement":
        """|a|^2 = a * conj(a), an element of the real subfield."""
        return self * self.conjugate()

    def is_real(self) -> bool:
        return self == self.conjugate()

    def trace(self) -> Fraction:
        """Tr_{Q(zeta_n)/Q}(a), an exact rational."""
        return self.normalized_trace() * self._field.degree

    def normalized_trace(self) -> Fraction:
        """Tr(a) / [K : Q]; independent of the cyclotomic field used to represent a."""
        weights = self._field._trace_weight_table()
        total = Fraction(0)
        for c, w in zip(self._coeffs, weights):
            if c:
                total += c * w
        return total

    # -- comparison and hashing -------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CyclotomicElement):
            if other._field is self._field:
                return self._coeffs == other._coeffs
            a, b = self._coerce_pair(other)
            return a._coeffs == b._coeffs
        if isinstance(other, (int, Fraction)):
            return self.is_rational() and self._coeffs[0] == other
        return NotImplemented

    def __hash__(self) -> int:
        value = self._hash
        if value is None:
            value = hash(self.normalized_trace())
            self._hash = value
        return value

    def __repr__(self) -> str:
        terms = []
        for k, c in enumerate(self._coeffs):
            if not c:
                continue
            if k == 0:
                terms.append(str(c))
            else:
                power = "z" if k == 1 else f"z^{k}"
                if c == 1:
                    terms.append(power)
                elif c == -1:
                    terms.append(f"-{power}")
                else:
                    terms.append(f"({c})*{power}")
        body = " + ".join(terms) if terms else "0"
        return f"{self._field}[{body}]"
