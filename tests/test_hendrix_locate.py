"""Hendrix Galois locator: marked inputs found from the algebra, never from answer tables."""

import random

import pytest

from chronus.hendrix import (
    GF257,
    DiscreteLogOracle,
    PeriodOracle,
    PrimeField,
    QuadraticResidueOracle,
    XorPeriodOracle,
)
from chronus.hendrix import galois as galois_module
from chronus.hendrix import oracles as oracles_module
from chronus.hendrix.locate import (
    NotAlgebraicallyLocatable,
    NotInSubgroup,
    PolynomialRootOracle,
    PowerEquationOracle,
    SquareRootOracle,
    discrete_log,
    factorize,
    is_probable_prime,
    locate,
    multiplicative_order,
    polynomial_roots,
    sqrt_mod,
)

pytestmark = pytest.mark.real

MERSENNE_127 = (1 << 127) - 1
NTT_PRIME = 3 * (1 << 30) + 1          # 3221225473, group order 3 * 2**30
F65537 = PrimeField(65537)


@pytest.fixture
def no_answer_tables(monkeypatch):  # mock-ok: guard only; makes answer tables raise so locate must solve, nothing is substituted
    """Make every answer-reading path raise: locate must solve, not look up."""
    def refuse(*_args, **_kwargs):
        raise AssertionError("locate read an answer table or answer method")
    monkeypatch.setattr(galois_module.PrimeField, "discrete_log", refuse)  # mock-ok: guard only; makes answer tables raise so locate must solve, nothing is substituted
    monkeypatch.setattr(oracles_module.DiscreteLogOracle, "marked", refuse)  # mock-ok: guard only; makes answer tables raise so locate must solve, nothing is substituted
    monkeypatch.setattr(oracles_module.PeriodOracle, "period", refuse)  # mock-ok: guard only; makes answer tables raise so locate must solve, nothing is substituted
    monkeypatch.setattr(oracles_module.XorPeriodOracle, "period", refuse)  # mock-ok: guard only; makes answer tables raise so locate must solve, nothing is substituted


def _product_poly(roots, p, extra=(1,)):
    """Coefficients (lowest first) of extra(x) * prod (x - r)."""
    poly = list(extra)
    for r in roots:
        nxt = [0] * (len(poly) + 1)
        for i, c in enumerate(poly):
            nxt[i] = (nxt[i] - r * c) % p
            nxt[i + 1] = (nxt[i + 1] + c) % p
        poly = nxt
    return poly


# --- integer substrate ------------------------------------------------------

def test_primality_and_factorisation_are_exact():
    assert is_probable_prime(257) and is_probable_prime(65537) and is_probable_prime(MERSENNE_127)
    assert not is_probable_prime(257 * 65537)
    assert factorize(256) == {2: 8}
    assert factorize(NTT_PRIME - 1) == {2: 30, 3: 1}
    n = 2 ** 126 - 1
    f = factorize(n)
    prod = 1
    for q, e in f.items():
        assert is_probable_prime(q)
        prod *= q ** e
    assert prod == n


def test_composite_cofactor_is_refused_not_guessed():
    big = 1000000007 * 998244353
    with pytest.raises(ValueError, match="composite"):
        factorize(big, trial_bound=1000)


# --- discrete logarithm -----------------------------------------------------

def test_discrete_log_matches_tables_for_every_element_of_small_fields(no_answer_tables):
    for p in (2, 3, 5, 7, 11, 13, 17, 97, 257):
        field = PrimeField(p)
        for k in range(p - 1):
            y = field.antilog(k)
            assert discrete_log(p, field.generator, y) == k


def test_locate_discrete_log_oracle_every_target_gf257(no_answer_tables):
    for k in range(256):
        y = pow(3, k, 257)
        result = locate(DiscreteLogOracle(GF257, y))
        assert result.marked == (k,)
        assert result.complete and result.verified
        assert result.method == "pohlig_hellman"
        assert result.oracle_queries == 1          # verification only, versus 256 for a scan


def test_fermat_prime_65537_logs_without_tables(no_answer_tables):
    rng = random.Random(65537)
    for _ in range(200):
        k = rng.randrange(65536)
        y = pow(3, k, 65537)
        assert locate(DiscreteLogOracle(F65537, y)).marked == (k,)


def test_discrete_log_beyond_the_table_limit():
    p = NTT_PRIME
    g = next(c for c in range(2, 100) if multiplicative_order(p, c) == p - 1)
    rng = random.Random(7)
    for _ in range(50):
        x = rng.randrange(p - 1)
        result = locate(PowerEquationOracle(p, g, pow(g, x, p)))
        assert result.marked == (x,) and result.verified and result.complete


def test_discrete_log_in_the_mersenne_127_field():
    p = MERSENNE_127
    g = 43  # primitive root of 2**127 - 1, confirmed below
    assert multiplicative_order(p, g) == p - 1
    x = 0x1D5A_2F3C_9B8E_7710_4C6A_55E1_3F2B_0D99 % (p - 1)
    result = locate(PowerEquationOracle(p, g, pow(g, x, p)))
    assert result.marked == (x,)
    assert result.verified


def test_non_power_target_is_reported_empty_and_complete():
    p = 257
    g = 9                     # order 128: only the squares are its powers
    y = 3                     # a non-residue, not a power of 9
    result = locate(PowerEquationOracle(p, g, y))
    assert result.marked == () and result.complete


def test_undecided_discrete_log_is_raised_not_reported_as_empty(monkeypatch):  # mock-ok: real discrete_log with a lower factor bound, to force the refusal path
    """A refusal (factor above the bound) must not become a proven-empty answer."""
    import chronus.hendrix.locate as locate_module

    real = locate_module.discrete_log

    def bounded(p, g, y, **kwargs):
        return real(p, g, y, max_prime_factor=2)   # NTT order 3 * 2**30: factor 3 is above 2

    monkeypatch.setattr(locate_module, "discrete_log", bounded)  # mock-ok: real discrete_log with a lower factor bound, to force the refusal path
    p = NTT_PRIME
    g = next(c for c in range(2, 100) if multiplicative_order(p, c) == p - 1)
    with pytest.raises(ValueError, match="above") as caught:
        locate(PowerEquationOracle(p, g, pow(g, 12345, p)))
    assert not isinstance(caught.value, NotInSubgroup)
    with pytest.raises(NotInSubgroup):
        discrete_log(257, 9, 3)


# --- order / period finding -------------------------------------------------

def test_period_oracle_matches_order_for_every_base(no_answer_tables):
    for p in (7, 13, 97, 257):
        field = PrimeField(p)
        for a in range(1, p):
            expected = field.order(a)
            result = locate(PeriodOracle(field, a))
            assert result.marked == (expected,)
            assert result.verified


def test_multiplicative_order_large_field():
    p = MERSENNE_127
    assert multiplicative_order(p, 2) == 127          # 2**127 = 1 mod 2**127 - 1
    assert multiplicative_order(p, p - 1) == 2


# --- polynomial roots -------------------------------------------------------

def test_polynomial_roots_exhaustive_check_small_field():
    rng = random.Random(257)
    p = 257
    for _ in range(300):
        degree = rng.randrange(1, 7)
        coeffs = [rng.randrange(p) for _ in range(degree)] + [rng.randrange(1, p)]
        expected = tuple(x for x in range(p) if sum(c * pow(x, i, p) for i, c in enumerate(coeffs)) % p == 0)
        assert polynomial_roots(coeffs, p) == expected


def test_polynomial_roots_in_a_2_127_field_with_an_irreducible_factor():
    p = MERSENNE_127
    rng = random.Random(127)
    roots = sorted({rng.randrange(p) for _ in range(5)})
    nonresidue = next(a for a in range(2, 100) if pow(a, (p - 1) // 2, p) == p - 1)
    coeffs = _product_poly(roots, p, extra=((-nonresidue) % p, 0, 1))   # (x**2 - n) has no root
    oracle = PolynomialRootOracle(p, coeffs)
    result = locate(oracle)
    assert result.marked == tuple(roots)
    assert result.complete and result.verified
    assert result.oracle_queries == len(roots)                          # a scan would need p ~ 1.7e38


def test_rootless_polynomial_returns_empty():
    assert polynomial_roots([1, 0, 1], 7) == ()                         # x**2 + 1, -1 non-residue mod 7


def test_zero_polynomial_is_refused():
    with pytest.raises(ValueError):
        polynomial_roots([0, 0], 7)


# --- square roots -----------------------------------------------------------

def test_sqrt_mod_exhaustive_small_and_large():
    for p in (3, 5, 13, 17, 257, 65537):
        roots_of = {}
        for x in range(p):                       # one exhaustive pass builds the reference
            roots_of.setdefault(x * x % p, set()).add(x)
        for a in range(p):
            assert sqrt_mod(p, a) == tuple(sorted(roots_of.get(a, ())))
    p = MERSENNE_127
    r = 0x3F00_1234_5678_9ABC_DEF0_1122_3344_5566
    a = r * r % p
    result = locate(SquareRootOracle(p, a))
    assert set(result.marked) == {r, p - r} and result.verified


# --- GF(2)-linear hidden period (Simon) -------------------------------------

@pytest.mark.parametrize("bits", [1, 2, 8, 20, 64, 256])
def test_xor_period_recovered_in_n_plus_two_queries(bits, no_answer_tables):
    rng = random.Random(bits)
    for _ in range(10):
        s = rng.randrange(1, 1 << bits)
        result = locate(XorPeriodOracle(bits, s))
        assert result.marked == (s,)
        assert result.oracle_queries == bits + 2


# --- boundary ---------------------------------------------------------------

def test_unstructured_oracles_are_not_scanned_under_another_name():
    with pytest.raises(NotAlgebraicallyLocatable):
        locate(QuadraticResidueOracle(GF257))

    class HashOracle:
        domain_size = 1 << 32

        def __call__(self, x):
            return 0

    with pytest.raises(NotAlgebraicallyLocatable):
        locate(HashOracle())
