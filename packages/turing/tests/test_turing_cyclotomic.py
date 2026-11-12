import sys
from fractions import Fraction
from math import gcd
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[1] / "src")
if sys.path[:1] != [_SRC]:
    sys.path.insert(0, _SRC)

from turing.algebra import (  # noqa: E402
    CyclotomicElement,
    CyclotomicField,
    abs2_of_progression,
    abs2_of_root_sum,
    cyclotomic_polynomial,
    divisors,
    euler_phi,
    mobius,
    pairwise_difference_counts,
)

FIELD_ORDERS = (1, 2, 3, 4, 5, 6, 7, 8, 9, 12, 15, 16, 20)


def _samples(field):
    """Deterministic sample elements (fixed formulas, no randomness)."""
    d = field.degree
    return [
        field.zero,
        field.one,
        field.zeta(1),
        field.zeta(field.n - 1) + Fraction(2, 3),
        field.element([Fraction((3 * k * k + 1) % 7 - 3, k % 4 + 1) for k in range(d)]),
        field.element([Fraction((5 * k + 2) % 9 - 4, k % 3 + 2) for k in range(d)]),
        field.element([Fraction(1, k + 1) if k % 2 == 0 else Fraction(0) for k in range(d)]),
    ]


def _poly_mul(a, b):
    out = [0] * (len(a) + len(b) - 1)
    for i, u in enumerate(a):
        for j, v in enumerate(b):
            out[i + j] += u * v
    return out


def test_degree_of_phi_n_is_euler_phi_for_n_up_to_30():
    for n in range(1, 31):
        phi_n = cyclotomic_polynomial(n)
        assert len(phi_n) - 1 == euler_phi(n)
        assert phi_n[-1] == 1
        assert CyclotomicField(n).degree == euler_phi(n)


def test_known_cyclotomic_polynomials_and_product_formula():
    assert cyclotomic_polynomial(1) == (-1, 1)
    assert cyclotomic_polynomial(2) == (1, 1)
    assert cyclotomic_polynomial(12) == (1, 0, -1, 0, 1)
    assert cyclotomic_polynomial(256) == (1,) + (0,) * 127 + (1,)
    for n in range(1, 31):
        product = [1]
        for d in divisors(n):
            product = _poly_mul(product, list(cyclotomic_polynomial(d)))
        assert product == [-1] + [0] * (n - 1) + [1]


def test_field_axioms_on_deterministic_samples():
    for n in FIELD_ORDERS:
        field = CyclotomicField(n)
        samples = _samples(field)
        for a in samples:
            assert a + field.zero == a
            assert a * field.one == a
            assert a + (-a) == 0
            assert a - a == field.zero
            for b in samples:
                assert a + b == b + a
                assert a * b == b * a
                for c in samples[2:5]:
                    assert (a + b) + c == a + (b + c)
                    assert (a * b) * c == a * (b * c)
                    assert a * (b + c) == a * b + a * c


def test_multiplicative_inverses_and_division():
    for n in FIELD_ORDERS:
        field = CyclotomicField(n)
        for a in _samples(field):
            if a.is_zero():
                try:
                    a.inverse()
                except ZeroDivisionError:
                    pass
                else:
                    raise AssertionError("zero must not be invertible")
                continue
            assert a * a.inverse() == 1
            assert a / a == field.one
            assert (field.zeta(1) / a) * a == field.zeta(1)
            assert a ** -2 == (a * a).inverse()
            assert 3 / a == a.inverse() * 3


def test_conjugation_and_galois_maps_are_automorphisms():
    for n in FIELD_ORDERS:
        field = CyclotomicField(n)
        samples = _samples(field)
        units = [j for j in range(1, n + 1) if gcd(j, n) == 1]
        for a in samples:
            assert a.conjugate().conjugate() == a
            assert a.galois(1) == a
            for b in samples[3:]:
                assert (a + b).conjugate() == a.conjugate() + b.conjugate()
                assert (a * b).conjugate() == a.conjugate() * b.conjugate()
                for j in units[:4]:
                    assert (a * b).galois(j) == a.galois(j) * b.galois(j)
                    assert (a + b).galois(j) == a.galois(j) + b.galois(j)
            assert a.abs2().is_real()
            assert a.conjugate() == a.galois(n - 1 if n > 1 else 1)


def test_roots_of_unity():
    for n in range(1, 31):
        field = CyclotomicField(n)
        zeta = field.zeta(1)
        assert zeta ** n == 1
        for k in range(1, n):
            assert zeta ** k != 1
        total = field.zero
        for k in range(n):
            total = total + field.zeta(k)
            assert field.zeta(k).abs2() == 1
            assert field.zeta(k).conjugate() == field.zeta(-k)
        assert total == (1 if n == 1 else 0)
        assert zeta.trace() == mobius(n)


def test_exact_zero_test_and_rationals():
    field = CyclotomicField(12)
    a = field.element([Fraction(1, 2), 0, 0, 0])
    assert a.is_rational() and a.to_rational() == Fraction(1, 2)
    assert not field.zeta(1).is_rational()
    try:
        field.zeta(1).to_rational()
    except ValueError:
        pass
    else:
        raise AssertionError("zeta_12 is not rational")
    assert (field.zeta(3) * field.zeta(3)).to_rational() == -1
    assert field.zero.is_zero() and not field.one.is_zero()
    assert not bool(field.zero) and bool(field.zeta(5))
    assert field.from_exponents({0: 1, 4: 1, 8: 1}).is_zero()


def test_sqrt_two_lies_in_q_zeta_8():
    field = CyclotomicField(8)
    zeta = field.zeta(1)
    root_two = zeta - zeta ** 3
    assert root_two * root_two == 2
    assert root_two.is_real()
    assert (1 / root_two) * 2 == root_two


def test_lifting_and_cross_field_equality():
    q4 = CyclotomicField(4)
    q8 = CyclotomicField(8)
    q12 = CyclotomicField(12)
    assert q8.lift(q4.zeta(1)) == q8.zeta(2)
    assert q4.zeta(1) == q8.zeta(2)
    assert hash(q4.zeta(1)) == hash(q8.zeta(2))
    assert CyclotomicField(3).zeta(1) == q12.zeta(4)
    mixed = q4.zeta(1) + CyclotomicField(3).zeta(1)
    assert mixed.field.n == 12
    assert mixed == q12.zeta(3) + q12.zeta(4)
    assert hash(q8.from_rational(Fraction(3, 4))) == hash(Fraction(3, 4))
    assert q8.from_rational(Fraction(3, 4)) == Fraction(3, 4)
    try:
        q8.lift(CyclotomicField(3).zeta(1))
    except ValueError:
        pass
    else:
        raise AssertionError("Q(zeta_3) is not embedded in Q(zeta_8) by the lift map")


def test_pairwise_difference_helper_matches_multiplication():
    cases = {
        5: [0, 1, 1, 3, 4, 4, 4],
        8: [0, 3, 3, 5, 7, 2, 2, 9],
        12: [1, 5, 7, 11, 0, 6, 6],
        16: [0, 3, 3, 5, 11, 14, 2],
        30: [0, 7, 13, 13, 29, 15, 22, 3],
    }
    for n, exponents in cases.items():
        field = CyclotomicField(n)
        counts = {}
        for e in exponents:
            counts[e] = counts.get(e, 0) + 1
        total = field.from_exponents(counts)
        assert abs2_of_root_sum(field, exponents) == total * total.conjugate()
        assert abs2_of_root_sum(field, exponents) == total.abs2()
        differences = pairwise_difference_counts(exponents, n)
        assert sum(differences.values()) == len(exponents) ** 2
        for step in (1, 2, 3, n - 1):
            for length in (0, 1, 4, 7):
                progression = [j * step for j in range(length)]
                assert abs2_of_progression(field, step, length) == abs2_of_root_sum(field, progression)


def test_traces_are_rational_and_field_independent():
    q8 = CyclotomicField(8)
    q16 = CyclotomicField(16)
    a = q8.element([1, Fraction(1, 2), 3, -2])
    assert a.normalized_trace() == q16.lift(a).normalized_trace()
    assert q8.one.trace() == 4
    assert q8.zeta(1).trace() == 0


def test_invalid_inputs_fail_clearly():
    for bad in (0, -3, True):
        try:
            CyclotomicField(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"CyclotomicField({bad!r}) must fail")
    field = CyclotomicField(5)
    for bad_coefficients in (["1", 0, 0, 0], [True, 0, 0, 0]):
        try:
            field.element(bad_coefficients)
        except TypeError:
            pass
        else:
            raise AssertionError("non-rational coefficients must be rejected")
    try:
        CyclotomicElement(field, [1, 2])
    except ValueError:
        pass
    else:
        raise AssertionError("coefficient count must equal the degree")
    try:
        field.zeta(1).galois(5)
    except ValueError:
        pass
    else:
        raise AssertionError("sigma_5 is not an automorphism of Q(zeta_5)")
