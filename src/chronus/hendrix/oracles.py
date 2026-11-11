"""Deterministic oracle objects built on Hendrix lookup tables.

Oracle protocol
---------------
An oracle is any object with

* an ``int`` attribute ``domain_size`` (positive), and
* ``__call__(x: int) -> int`` defined for ``0 <= x < domain_size``.

A Boolean oracle returns 0 or 1. This is the protocol shared with the TURING
oracle work. It is matched by duck typing: this module does not import
``turing``, and ``is_oracle`` checks only the shape of an object.

Oracles in this module
----------------------
* ``DiscreteLogOracle(field, y)``: domain p - 1, f(x) = 1 iff g**x = y;
  exactly one marked input.
* ``QuadraticResidueOracle(field)``: domain p - 1 (exponents), f(k) = 1 iff
  g**k is a square, i.e. k is even; (p - 1) / 2 marked inputs.
* ``QuadraticResidueElementOracle(field)``: domain p (elements), f(x) = 1 iff
  x is a nonzero square; (p - 1) / 2 marked inputs, all in [1, p).
* ``PeriodOracle(field, a)``: domain p - 1, f(x) = a**x; least period
  ord(a) = (p - 1) / gcd(log_g a, p - 1).
* ``XorPeriodOracle(n, s)``: domain 2**n, a GF(2)-linear map with kernel
  {0, s}, so f(x) = f(x XOR s) and f is exactly 2-to-1 (Simon's promise).

Every oracle is exact and deterministic, and one query costs a fixed number
of PrimeField table reads (bit operations for ``XorPeriodOracle``).
``marked()`` and ``period()`` return the answer that a search or
period-finding routine should produce. They read it from the tables or from
the construction parameters, so they serve to cross-check such routines;
they are not search algorithms, and code that calls them instead of querying
the oracle has not searched for anything.
"""

from __future__ import annotations

from chronus.hendrix.galois import PrimeField

__all__ = [
    "DiscreteLogOracle",
    "MAX_PROMISE_CHECK_BITS",
    "PeriodOracle",
    "QuadraticResidueElementOracle",
    "QuadraticResidueOracle",
    "XorPeriodOracle",
    "is_oracle",
]

#: XorPeriodOracle.validate_promise enumerates all 2**n inputs; larger n is refused.
MAX_PROMISE_CHECK_BITS = 20


def is_oracle(obj: object) -> bool:
    """True iff obj has the protocol shape: positive int ``domain_size`` and callable.

    Classes are rejected (an instance is expected). The oracle is not
    evaluated, so whether a Boolean oracle really returns 0 or 1 is not checked.
    """
    if isinstance(obj, type):
        return False
    domain_size = getattr(obj, "domain_size", None)
    return (
        isinstance(domain_size, int)
        and not isinstance(domain_size, bool)
        and domain_size > 0
        and callable(obj)
    )


def _require_int(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an int, not {type(value).__name__}")
    return value


def _require_field(field: object) -> PrimeField:
    if not isinstance(field, PrimeField):
        raise TypeError(f"field must be a PrimeField, not {type(field).__name__}")
    return field


def _require_odd_field(field: object) -> PrimeField:
    field = _require_field(field)
    if field.p == 2:
        raise ValueError(
            "quadratic residuosity needs an odd prime: every element of F_2 is a square"
        )
    return field


class _Oracle:
    """Shared protocol plumbing: a read-only domain_size and query validation."""

    __slots__ = ("_domain_size",)

    def __init__(self, domain_size: int) -> None:
        self._domain_size = domain_size

    @property
    def domain_size(self) -> int:
        """Number of valid inputs; queries are ints x with 0 <= x < domain_size."""
        return self._domain_size

    def _check(self, x: object) -> int:
        if not isinstance(x, int) or isinstance(x, bool):
            raise TypeError(f"oracle input must be an int, not {type(x).__name__}")
        if not 0 <= x < self._domain_size:
            raise ValueError(f"oracle input {x} is outside [0, {self._domain_size})")
        return x


class DiscreteLogOracle(_Oracle):
    """Boolean oracle over exponents: f(x) = 1 iff g**x = y in F_p.

    The domain is [0, p - 1) and exactly one input, log_g(y), is marked. A query
    reads one EXP entry. ``marked()`` reads the LOG table, so it returns the
    answer directly; it exists to cross-check search routines.
    """

    __slots__ = ("_field", "_target")

    def __init__(self, field: PrimeField, y: int) -> None:
        field = _require_field(field)
        target = field.reduce(y)
        if target == 0:
            raise ValueError("y must be nonzero in F_p: 0 is not a power of the generator")
        super().__init__(field.group_order)
        self._field = field
        self._target = target

    @property
    def field(self) -> PrimeField:
        return self._field

    @property
    def target(self) -> int:
        """The element y in [1, p) whose discrete logarithm is marked."""
        return self._target

    @property
    def marked_count(self) -> int:
        """Number of marked inputs: always 1."""
        return 1

    def __call__(self, x: int) -> int:
        return 1 if self._field.antilog(self._check(x)) == self._target else 0

    def marked(self) -> frozenset[int]:
        """{log_g(y)}, from one LOG table read."""
        return frozenset((self._field.discrete_log(self._target),))

    def __repr__(self) -> str:
        return f"DiscreteLogOracle(p={self._field.p}, y={self._target})"


class QuadraticResidueOracle(_Oracle):
    """Boolean oracle over exponents: f(k) = 1 iff g**k is a square in F_p.

    A query reads EXP[k] and then the parity of its LOG entry; because
    LOG[EXP[k]] = k this is 1 exactly for even k, so (p - 1) / 2 of the p - 1
    inputs are marked. Requires an odd prime.
    """

    __slots__ = ("_field",)

    def __init__(self, field: PrimeField) -> None:
        field = _require_odd_field(field)
        super().__init__(field.group_order)
        self._field = field

    @property
    def field(self) -> PrimeField:
        return self._field

    @property
    def marked_count(self) -> int:
        """(p - 1) / 2."""
        return self._field.group_order // 2

    def __call__(self, x: int) -> int:
        element = self._field.antilog(self._check(x))
        return 1 if self._field.is_quadratic_residue(element) else 0

    def marked(self) -> frozenset[int]:
        """The even exponents 0, 2, ..., p - 3 (built in O(p))."""
        return frozenset(range(0, self._field.group_order, 2))

    def __repr__(self) -> str:
        return f"QuadraticResidueOracle(p={self._field.p})"


class QuadraticResidueElementOracle(_Oracle):
    """Boolean oracle over elements: f(x) = 1 iff x is a nonzero square in F_p.

    The domain is [0, p) so that the input is the field element itself. x = 0
    is in the domain and unmarked (Legendre symbol 0); the (p - 1) / 2 marked
    inputs all lie in [1, p). A query reads one LOG entry. Requires an odd
    prime.
    """

    __slots__ = ("_field",)

    def __init__(self, field: PrimeField) -> None:
        field = _require_odd_field(field)
        super().__init__(field.p)
        self._field = field

    @property
    def field(self) -> PrimeField:
        return self._field

    @property
    def marked_count(self) -> int:
        """(p - 1) / 2."""
        return self._field.group_order // 2

    def __call__(self, x: int) -> int:
        return 1 if self._field.is_quadratic_residue(self._check(x)) else 0

    def marked(self) -> frozenset[int]:
        """The even powers g**0, g**2, ..., g**(p - 3) (built in O(p))."""
        return frozenset(
            self._field.antilog(k) for k in range(0, self._field.group_order, 2)
        )

    def __repr__(self) -> str:
        return f"QuadraticResidueElementOracle(p={self._field.p})"


class PeriodOracle(_Oracle):
    """Order-finding oracle f(x) = a**x in F_p on the domain [0, p - 1).

    Because a**(p - 1) = 1, f is periodic modulo p - 1 with least period
    ord(a) = (p - 1) / gcd(log_g a, p - 1) and is injective on one period. A
    query reads one LOG and one EXP entry; outputs are elements of [1, p).
    ``period()`` evaluates the closed form from the LOG table; it exists to
    cross-check period-finding routines.
    """

    __slots__ = ("_field", "_base")

    def __init__(self, field: PrimeField, a: int) -> None:
        field = _require_field(field)
        base = field.reduce(a)
        if base == 0:
            raise ValueError("a must be nonzero in F_p")
        super().__init__(field.group_order)
        self._field = field
        self._base = base

    @property
    def field(self) -> PrimeField:
        return self._field

    @property
    def base(self) -> int:
        """The element a in [1, p)."""
        return self._base

    def __call__(self, x: int) -> int:
        return self._field.pow(self._base, self._check(x))

    def period(self) -> int:
        """Multiplicative order of a: (p - 1) // gcd(LOG[a], p - 1)."""
        return self._field.order(self._base)

    def validate_promise(self) -> bool:
        """Exhaustive check that f(x) = f(y) iff x = y modulo period().

        Evaluates the oracle on the whole domain (p - 1 queries): f must repeat
        with period() and be injective on [0, period()).
        """
        size = self._domain_size
        period = self.period()
        if not 0 < period <= size or size % period:
            return False
        values = [self(x) for x in range(size)]
        if any(values[x] != values[(x + period) % size] for x in range(size)):
            return False
        return len(set(values[:period])) == period

    def __repr__(self) -> str:
        return f"PeriodOracle(p={self._field.p}, a={self._base})"


class XorPeriodOracle(_Oracle):
    """Simon-type oracle on n-bit strings with a hidden period s != 0.

    f(x) = x XOR (bit_t(x) * s), where t is the index of the highest set bit of
    s. This map is GF(2)-linear with kernel {0, s}, so f(x) = f(y) iff y is x or
    x XOR s: f is exactly 2-to-1, and f(x) = min(x, x XOR s). It is
    deterministic; a query is a few bit operations. ``period()`` returns s, for
    cross-checking period-finding routines.
    """

    __slots__ = ("_bits", "_secret", "_pivot")

    def __init__(self, n: int, s: int) -> None:
        n = _require_int(n, "n")
        s = _require_int(s, "s")
        if n < 1:
            raise ValueError("n must be a positive number of bits")
        if not 0 < s < 1 << n:
            raise ValueError(f"s must satisfy 0 < s < 2**{n}")
        super().__init__(1 << n)
        self._bits = n
        self._secret = s
        self._pivot = s.bit_length() - 1

    @property
    def bits(self) -> int:
        """The input length n; the domain is [0, 2**n)."""
        return self._bits

    def __call__(self, x: int) -> int:
        x = self._check(x)
        return x ^ self._secret if (x >> self._pivot) & 1 else x

    def period(self) -> int:
        """The hidden period s."""
        return self._secret

    def validate_promise(self) -> bool:
        """Exhaustive check of Simon's promise over all 2**n inputs.

        True iff f(x) = f(x XOR s) for every x and every output has exactly two
        preimages. Refused with ValueError for n > MAX_PROMISE_CHECK_BITS.
        """
        if self._bits > MAX_PROMISE_CHECK_BITS:
            raise ValueError(
                f"exhaustive promise check is limited to n <= {MAX_PROMISE_CHECK_BITS} bits"
            )
        secret = self.period()
        if not 0 < secret < self._domain_size:
            return False
        preimages: dict[int, int] = {}
        for x in range(self._domain_size):
            value = self(x)
            if value != self(x ^ secret):
                return False
            preimages[value] = preimages.get(value, 0) + 1
        return all(count == 2 for count in preimages.values())

    def __repr__(self) -> str:
        return f"XorPeriodOracle(n={self._bits}, s={self._secret})"
