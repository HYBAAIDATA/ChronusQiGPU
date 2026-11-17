"""Hendrix Galois locator: find unknown marked inputs by solving the oracle's algebra.

The structured-search catalogue (``chronus.hendrix.structured``) records that
the legacy one-shot routines take the marked set as an input. This module is
the step past that: given an oracle whose condition is *algebraic* over a
finite field, it computes the marked inputs from the algebra itself, without
reading a precomputed answer table and without scanning the domain. Every
returned input is then confirmed by querying the oracle.

What is located, and at what cost (p is the field characteristic, d a degree,
n a bit length; "field ops" are modular multiplications of log2(p)-bit ints):

==============================  ===========================================  =====================================
Oracle condition                Method                                       Cost
==============================  ===========================================  =====================================
g**x = y (discrete log)         Pohlig-Hellman + baby-step/giant-step        O(sum e_i (log p + sqrt q_i)) field ops
                                per prime power q_i**e_i of the order        (k steps for a Fermat prime 2**k + 1)
a**x periodic (order finding)   strip prime factors of p - 1                 O(log p * #factors) field ops
f(x) = 0, deg f = d             gcd(f, x**p - x) + Cantor-Zassenhaus split   polynomial in d and log p (expected)
x**2 = a                        Tonelli-Shanks                               O(log**2 p) field ops
GF(2)-linear f, f(x)=f(x^s)     learn f on the basis (n + 1 queries),        n + 1 queries + O(n**3) bit ops
(Simon promise)                 kernel by Gaussian elimination
==============================  ===========================================  =====================================

None of these cost scales with the domain size p or 2**n, which is what makes
the fields usable far beyond the 2**20 table limit of ``PrimeField``: a
degree-5 polynomial over p = 2**127 - 1 has its roots located exactly, where a
scan would need about 1.7e38 queries.

Boundaries (the mathematics, stated rather than hidden):

* An oracle with no exposed algebraic structure (for example SHA-256d target
  membership) cannot be located this way. ``locate`` raises
  ``NotAlgebraicallyLocatable`` instead of scanning under another name.
* Pohlig-Hellman needs the factorisation of the group order and is fast only
  when its prime factors are small. That is a property of the field chosen,
  reported in the result, never assumed. When the order cannot be factorised
  or has a prime factor above the bound, ``discrete_log`` refuses with
  ValueError and ``locate`` propagates it: "could not decide" is never
  reported as "nothing is marked" (only ``NotInSubgroup`` means that).
* Cantor-Zassenhaus splitting chooses shifts deterministically and checks
  every root; the output is exact, the running time is an expected bound.
* The GF(2)-linear locator relies on the oracle's declared linearity (Simon's
  promise as constructed by ``XorPeriodOracle``); it confirms the recovered
  period against the oracle, it does not certify linearity of an arbitrary
  function.

All arithmetic is exact integer arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isqrt
from typing import Sequence

__all__ = [
    "LocateResult",
    "NotAlgebraicallyLocatable",
    "NotInSubgroup",
    "PolynomialRootOracle",
    "PowerEquationOracle",
    "SquareRootOracle",
    "discrete_log",
    "factorize",
    "is_probable_prime",
    "locate",
    "multiplicative_order",
    "polynomial_roots",
    "sqrt_mod",
    "xor_period_from_linear_oracle",
]


class NotAlgebraicallyLocatable(TypeError):
    """The oracle exposes no algebraic structure this module can solve."""


class NotInSubgroup(ValueError):
    """y is provably not a power of g: the discrete logarithm does not exist.

    Distinct from the other ValueErrors of ``discrete_log`` (order not
    factorisable, prime factor above the bound), which mean "not decided".
    """


@dataclass(frozen=True)
class LocateResult:
    """Outcome of ``locate``.

    ``marked`` holds the located inputs. ``complete`` is True when the method
    proves that no other input is marked (for example: all roots of the
    polynomial, or the unique discrete log of a primitive root). ``verified``
    is True when every located input was confirmed by querying the oracle.
    ``oracle_queries`` counts the queries made, including verification.
    """

    marked: tuple[int, ...]
    method: str
    complete: bool
    verified: bool
    oracle_queries: int
    details: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Integer helpers
# ---------------------------------------------------------------------------

_MR_BASES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41)
#: Below this bound the fixed Miller-Rabin bases above are a proof of primality.
MR_DETERMINISTIC_LIMIT = 3_317_044_064_679_887_385_961_981


def _require_int(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an int, not {type(value).__name__}")
    return value


def is_probable_prime(n: int) -> bool:
    """Miller-Rabin with 13 fixed bases.

    Deterministic (a proof) for n < MR_DETERMINISTIC_LIMIT; above it a strong
    probable-prime test whose fixed bases are not a proof.
    """
    _require_int(n, "n")
    if n < 2:
        return False
    for q in _MR_BASES:
        if n % q == 0:
            return n == q
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2
        s += 1
    for a in _MR_BASES:
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = x * x % n
            if x == n - 1:
                break
        else:
            return False
    return True


def factorize(n: int, trial_bound: int = 1 << 20) -> dict[int, int]:
    """Prime factorisation of n >= 1 by trial division up to ``trial_bound``.

    A remaining cofactor must pass ``is_probable_prime``; otherwise the
    factorisation is refused with ValueError rather than guessed.
    """
    _require_int(n, "n")
    if n < 1:
        raise ValueError("n must be positive")
    factors: dict[int, int] = {}
    for q in (2, 3):
        while n % q == 0:
            factors[q] = factors.get(q, 0) + 1
            n //= q
    q = 5
    while q * q <= n and q <= trial_bound:
        for r in (q, q + 2):
            while n % r == 0:
                factors[r] = factors.get(r, 0) + 1
                n //= r
        q += 6
    if n > 1:
        if not is_probable_prime(n):
            raise ValueError(
                f"cofactor {n} is composite with no factor <= {trial_bound}; "
                "factorisation of the group order is required and is not available"
            )
        factors[n] = factors.get(n, 0) + 1
    return factors


def _check_prime_field(p: int) -> int:
    _require_int(p, "p")
    if not is_probable_prime(p):
        raise ValueError(f"p = {p} is not prime")
    return p


def multiplicative_order(p: int, a: int, order_factors: dict[int, int] | None = None) -> int:
    """Order of a in F_p*, from the factorisation of p - 1 (no table, any p)."""
    _check_prime_field(p)
    a = _require_int(a, "a") % p
    if a == 0:
        raise ValueError("0 has no multiplicative order")
    factors = order_factors if order_factors is not None else factorize(p - 1)
    order = p - 1
    for q in factors:
        while order % q == 0 and pow(a, order // q, p) == 1:
            order //= q
    return order


def _bsgs(base: int, target: int, p: int, bound: int) -> int:
    """x in [0, bound) with base**x = target mod p, or NotInSubgroup."""
    m = isqrt(bound - 1) + 1
    table: dict[int, int] = {}
    value = 1
    for j in range(m):
        table.setdefault(value, j)
        value = value * base % p
    factor = pow(base, -m, p)
    gamma = target
    for i in range(m):
        j = table.get(gamma)
        if j is not None:
            return i * m + j
        gamma = gamma * factor % p
    raise NotInSubgroup("no logarithm in the subgroup")


def discrete_log(p: int, g: int, y: int, *, max_prime_factor: int = 1 << 40) -> int:
    """The least x >= 0 with g**x = y in F_p, by Pohlig-Hellman.

    The group order ord(g) is factorised; each prime power q**e costs
    e * (one exponentiation + a baby-step/giant-step of size sqrt(q)).
    Raises ``NotInSubgroup`` when y is not a power of g, and plain ValueError
    when the order cannot be factorised or a prime factor exceeds
    ``max_prime_factor`` (undecided, not a negative answer). The answer is
    checked: pow(g, x, p) == y.
    """
    _check_prime_field(p)
    g, y = _require_int(g, "g") % p, _require_int(y, "y") % p
    if g == 0 or y == 0:
        raise ValueError("g and y must be nonzero")
    order = multiplicative_order(p, g)
    factors = factorize(order)
    too_big = [q for q in factors if q > max_prime_factor]
    if too_big:
        raise ValueError(f"group order has prime factors {too_big} above {max_prime_factor}")
    residues, moduli = [], []
    for q, e in factors.items():
        qe = q**e
        g_i = pow(g, order // qe, p)          # generator of the order-q**e subgroup
        y_i = pow(y, order // qe, p)
        gamma = pow(g_i, q ** (e - 1), p)     # element of order q
        x_i = 0
        for k in range(e):
            h = pow(pow(g_i, -x_i, p) * y_i % p, q ** (e - 1 - k), p)
            d_k = _bsgs(gamma, h, p, q)
            x_i += d_k * q**k
        residues.append(x_i)
        moduli.append(qe)
    x = 0
    for r, m in zip(residues, moduli):          # Chinese remainder theorem
        rest = order // m
        x = (x + r * rest * pow(rest, -1, m)) % order
    if pow(g, x, p) != y:
        raise NotInSubgroup("y is not in the subgroup generated by g")
    return x


def sqrt_mod(p: int, a: int) -> tuple[int, ...]:
    """All x in F_p with x**2 = a, by Tonelli-Shanks; () if a is a non-residue."""
    _check_prime_field(p)
    a = _require_int(a, "a") % p
    if a == 0:
        return (0,)
    if p == 2:
        return (a,)
    if pow(a, (p - 1) // 2, p) != 1:
        return ()
    q, s = p - 1, 0
    while q % 2 == 0:
        q //= 2
        s += 1
    z = 2
    while pow(z, (p - 1) // 2, p) != p - 1:
        z += 1
    m, c, t, r = s, pow(z, q, p), pow(a, q, p), pow(a, (q + 1) // 2, p)
    while t != 1:
        i, t2 = 0, t
        while t2 != 1:
            t2 = t2 * t2 % p
            i += 1
        b = pow(c, 1 << (m - i - 1), p)
        m, c, t, r = i, b * b % p, t * b * b % p, r * b % p
    if r * r % p != a:
        raise ArithmeticError("Tonelli-Shanks produced a non-root")
    return tuple(sorted({r, p - r}))


# ---------------------------------------------------------------------------
# Polynomials over F_p (coefficient lists, lowest degree first)
# ---------------------------------------------------------------------------

def _trim(f: list[int]) -> list[int]:
    while f and f[-1] == 0:
        f.pop()
    return f


def _poly_mod(f: list[int], g: list[int], p: int) -> list[int]:
    f = f[:]
    inv = pow(g[-1], -1, p)
    dg = len(g) - 1
    while len(f) - 1 >= dg and f:
        coef = f[-1] * inv % p
        shift = len(f) - 1 - dg
        for i, gc in enumerate(g):
            f[shift + i] = (f[shift + i] - coef * gc) % p
        _trim(f)
    return f


def _poly_mulmod(f: list[int], g: list[int], m: list[int], p: int) -> list[int]:
    if not f or not g:
        return []
    out = [0] * (len(f) + len(g) - 1)
    for i, a in enumerate(f):
        if a:
            for j, b in enumerate(g):
                out[i + j] = (out[i + j] + a * b) % p
    return _poly_mod(_trim(out), m, p)


def _poly_powmod(base: list[int], e: int, m: list[int], p: int) -> list[int]:
    result = [1]
    base = _poly_mod(base, m, p)
    while e:
        if e & 1:
            result = _poly_mulmod(result, base, m, p)
        base = _poly_mulmod(base, base, m, p)
        e >>= 1
    return result


def _poly_gcd(f: list[int], g: list[int], p: int) -> list[int]:
    f, g = _trim(f[:]), _trim(g[:])
    while g:
        f, g = g, _poly_mod(f, g, p)
    if not f:
        return []
    inv = pow(f[-1], -1, p)
    return [c * inv % p for c in f]


def _poly_sub(f: list[int], g: list[int], p: int) -> list[int]:
    n = max(len(f), len(g))
    return _trim([((f[i] if i < len(f) else 0) - (g[i] if i < len(g) else 0)) % p for i in range(n)])


def _poly_divexact(f: list[int], g: list[int], p: int) -> list[int]:
    f = f[:]
    inv = pow(g[-1], -1, p)
    dg = len(g) - 1
    q = [0] * (len(f) - dg)
    while f and len(f) - 1 >= dg:
        coef = f[-1] * inv % p
        shift = len(f) - 1 - dg
        q[shift] = coef
        for i, gc in enumerate(g):
            f[shift + i] = (f[shift + i] - coef * gc) % p
        _trim(f)
    if f:
        raise ArithmeticError("polynomial division was not exact")
    return q


def _poly_eval(f: Sequence[int], x: int, p: int) -> int:
    acc = 0
    for c in reversed(f):
        acc = (acc * x + c) % p
    return acc


def polynomial_roots(coefficients: Sequence[int], p: int) -> tuple[int, ...]:
    """All distinct roots in F_p of sum c_i x**i (coefficients lowest first).

    gcd(f, x**p - x) isolates the product of (x - r) over the roots r in F_p,
    computed with x**p reduced modulo f by repeated squaring, so the work is
    polynomial in deg f and log p. That product is split by Cantor-Zassenhaus
    with deterministic shifts a = 0, 1, 2, ...: gcd(h, (x + a)**((p-1)/2) - 1).
    Every returned root is checked by evaluation.
    """
    _check_prime_field(p)
    f = _trim([_require_int(c, "coefficient") % p for c in coefficients])
    if not f:
        raise ValueError("the zero polynomial vanishes everywhere; the marked set is the whole field")
    if len(f) == 1:
        return ()
    if p == 2:
        return tuple(x for x in (0, 1) if _poly_eval(f, x, p) == 0)
    xp = _poly_powmod([0, 1], p, f, p)
    split = _poly_gcd(f, _poly_sub(xp, [0, 1], p), p)
    roots: list[int] = []
    stack = [split] if len(split) > 1 else []
    half = (p - 1) // 2
    while stack:
        h = stack.pop()
        if len(h) == 2:
            roots.append((-h[0]) * pow(h[1], -1, p) % p)
            continue
        for a in range(p):
            w = _poly_sub(_poly_powmod([a % p, 1], half, h, p), [1], p)
            d = _poly_gcd(h, w, p)
            if 1 < len(d) < len(h):
                stack.extend([d, _poly_divexact(h, d, p)])
                break
        else:  # pragma: no cover - impossible for a product of distinct linear factors
            raise ArithmeticError("Cantor-Zassenhaus failed to split")
    roots = sorted(set(roots))
    if any(_poly_eval(f, r, p) != 0 for r in roots):
        raise ArithmeticError("a located root does not satisfy the polynomial")
    if len(roots) != len(split) - 1:
        raise ArithmeticError("root count disagrees with deg gcd(f, x**p - x)")
    return tuple(roots)


# ---------------------------------------------------------------------------
# GF(2)-linear period recovery (Simon's promise)
# ---------------------------------------------------------------------------

def _gf2_kernel(columns: list[int], n: int) -> list[int]:
    """Basis of {x : sum_i x_i * columns[i] = 0} over GF(2); columns are bit masks."""
    pivots: dict[int, tuple[int, int]] = {}   # leading bit -> (column, combination of inputs)
    kernel = []
    for i, col in enumerate(columns):
        combo = 1 << i
        while col:
            top = col.bit_length() - 1
            if top not in pivots:
                break
            pcol, pcombo = pivots[top]
            col ^= pcol
            combo ^= pcombo
        if col == 0:
            kernel.append(combo)
        else:
            pivots[col.bit_length() - 1] = (col, combo)
    return kernel


def xor_period_from_linear_oracle(oracle, n: int) -> tuple[int, int]:
    """Recover s with f(x) = f(x XOR s) from a GF(2)-linear oracle in n + 1 queries.

    Linearity means f is determined by f(e_i) on the n basis vectors (and
    f(0) for an affine offset). The kernel of that matrix is the period set;
    under Simon's promise it is {0, s}. Returns (s, queries). The period is
    confirmed against the oracle on the basis vectors and at s.
    """
    _require_int(n, "n")
    f0 = oracle(0)
    columns = [oracle(1 << i) ^ f0 for i in range(n)]
    queries = n + 1
    kernel = _gf2_kernel(columns, n)
    if len(kernel) != 1:
        raise ArithmeticError(
            f"kernel has dimension {len(kernel)}; Simon's promise (exactly one nonzero period) does not hold"
        )
    s = kernel[0]
    if oracle(s) != f0:
        raise ArithmeticError("recovered period fails f(s) = f(0)")
    queries += 1
    return s, queries


# ---------------------------------------------------------------------------
# Table-free oracles for fields of any size
# ---------------------------------------------------------------------------

class _BigFieldOracle:
    __slots__ = ("_p", "_domain_size")

    def __init__(self, p: int, domain_size: int) -> None:
        self._p = _check_prime_field(p)
        self._domain_size = domain_size

    @property
    def p(self) -> int:
        return self._p

    @property
    def domain_size(self) -> int:
        return self._domain_size

    def _check(self, x: object) -> int:
        x = _require_int(x, "oracle input")
        if not 0 <= x < self._domain_size:
            raise ValueError(f"oracle input {x} is outside [0, {self._domain_size})")
        return x


class PolynomialRootOracle(_BigFieldOracle):
    """Boolean oracle on F_p: f(x) = 1 iff sum c_i x**i = 0 (any prime p)."""

    __slots__ = ("_coefficients",)

    def __init__(self, p: int, coefficients: Sequence[int]) -> None:
        super().__init__(p, p)
        coeffs = _trim([_require_int(c, "coefficient") % p for c in coefficients])
        if len(coeffs) < 2:
            raise ValueError("polynomial must have degree >= 1")
        self._coefficients = tuple(coeffs)

    @property
    def coefficients(self) -> tuple[int, ...]:
        return self._coefficients

    def __call__(self, x: int) -> int:
        return 1 if _poly_eval(self._coefficients, self._check(x), self._p) == 0 else 0


class PowerEquationOracle(_BigFieldOracle):
    """Boolean oracle on exponents: f(x) = 1 iff g**x = y in F_p (any prime p).

    The domain is [0, ord(g)); exactly one input is marked when y is a power
    of g. No EXP/LOG tables are built.
    """

    __slots__ = ("_g", "_y", "_order")

    def __init__(self, p: int, g: int, y: int) -> None:
        _check_prime_field(p)
        g, y = _require_int(g, "g") % p, _require_int(y, "y") % p
        if g == 0 or y == 0:
            raise ValueError("g and y must be nonzero")
        order = multiplicative_order(p, g)
        super().__init__(p, order)
        self._g, self._y, self._order = g, y, order

    @property
    def g(self) -> int:
        return self._g

    @property
    def target(self) -> int:
        return self._y

    def __call__(self, x: int) -> int:
        return 1 if pow(self._g, self._check(x), self._p) == self._y else 0


class SquareRootOracle(_BigFieldOracle):
    """Boolean oracle on F_p: f(x) = 1 iff x**2 = a (any prime p)."""

    __slots__ = ("_a",)

    def __init__(self, p: int, a: int) -> None:
        super().__init__(p, p)
        self._a = _require_int(a, "a") % p

    @property
    def target(self) -> int:
        return self._a

    def __call__(self, x: int) -> int:
        x = self._check(x)
        return 1 if x * x % self._p == self._a else 0


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def _confirm(oracle, xs: Sequence[int]) -> bool:
    return all(oracle(x) == 1 for x in xs)


def locate(oracle) -> LocateResult:
    """Locate the marked inputs (or hidden period) of a structured oracle.

    Supported: Hendrix ``DiscreteLogOracle``, ``PeriodOracle`` and
    ``XorPeriodOracle``, and this module's ``PowerEquationOracle``,
    ``PolynomialRootOracle`` and ``SquareRootOracle``. The Hendrix oracles'
    ``marked()``/``period()`` answer methods and the EXP/LOG tables are not
    used: only the public algebraic description (p, g, y, a, n) and oracle
    queries. Anything else raises ``NotAlgebraicallyLocatable``.
    """
    from chronus.hendrix.oracles import DiscreteLogOracle, PeriodOracle, XorPeriodOracle

    if isinstance(oracle, (DiscreteLogOracle, PowerEquationOracle)):
        if isinstance(oracle, DiscreteLogOracle):
            p, g, y = oracle.field.p, oracle.field.generator, oracle.target
        else:
            p, g, y = oracle.p, oracle.g, oracle.target
        try:
            x = discrete_log(p, g, y)
        except NotInSubgroup:
            # Proven: y is not a power of g, so nothing in the domain is marked.
            # Any other ValueError (order not factorisable, factor too large)
            # propagates: an undecided case is never reported as an empty answer.
            return LocateResult((), "pohlig_hellman", True, True, 0,
                                {"reason": "y is not a power of g"})
        order_factors = factorize(oracle.domain_size)
        return LocateResult(
            (x,), "pohlig_hellman", True, _confirm(oracle, (x,)), 1,
            {"group_order": oracle.domain_size, "order_factors": order_factors},
        )
    if isinstance(oracle, PeriodOracle):
        p, a = oracle.field.p, oracle.base
        r = multiplicative_order(p, a)
        # f(x) = a**x: confirm f(r) = 1 (f(r) is f(0) since r | p - 1) and that no
        # proper divisor r/q is also a period, by querying the oracle itself.
        probes = [r % oracle.domain_size] + [r // q for q in factorize(r)] if r > 1 else [0]
        values = [oracle(x) for x in probes]
        ok = values[0] == 1 and all(v != 1 for v in values[1:])
        return LocateResult((r,), "order_from_group_factorisation", True, ok, len(probes),
                            {"period": r})
    if isinstance(oracle, XorPeriodOracle):
        s, queries = xor_period_from_linear_oracle(oracle, oracle.bits)
        return LocateResult((s,), "gf2_linear_kernel", True, True, queries, {"bits": oracle.bits})
    if isinstance(oracle, PolynomialRootOracle):
        roots = polynomial_roots(oracle.coefficients, oracle.p)
        return LocateResult(roots, "gcd_x_p_minus_x_cantor_zassenhaus", True,
                            _confirm(oracle, roots), len(roots),
                            {"degree": len(oracle.coefficients) - 1})
    if isinstance(oracle, SquareRootOracle):
        roots = sqrt_mod(oracle.p, oracle.target)
        return LocateResult(roots, "tonelli_shanks", True, _confirm(oracle, roots), len(roots), {})
    raise NotAlgebraicallyLocatable(
        f"{type(oracle).__name__} exposes no algebraic structure to solve; "
        "an exhaustive scan is the only exact method and is not performed under this name"
    )
