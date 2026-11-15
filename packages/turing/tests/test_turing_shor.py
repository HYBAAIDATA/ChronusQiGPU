import sys
from fractions import Fraction
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[1] / "src")
if sys.path[:1] != [_SRC]:
    sys.path.insert(0, _SRC)

from turing.algebra import CyclotomicField, abs2_of_root_sum  # noqa: E402
from turing.algorithms import shor  # noqa: E402


def _total(elements):
    total = elements[0].field.zero
    for element in elements:
        total = total + element
    return total


def test_modexp_and_continued_fractions():
    for base in range(0, 12):
        for exponent in range(0, 20):
            expected = 1
            for _ in range(exponent):
                expected = expected * base % 35
            assert shor.modexp(base, exponent, 35) == expected % 35
    assert shor.continued_fraction(Fraction(64, 256)) == (0, 4)
    assert shor.continued_fraction(Fraction(415, 93)) == (4, 2, 6, 7)
    assert shor.convergents(Fraction(415, 93))[-1] == Fraction(415, 93)
    assert shor.register_qubits(15) == 8 and shor.register_qubits(21) == 9


def test_order_of_7_modulo_15():
    result = shor.find_order(15, 7)
    assert result.register_qubits == 8
    assert result.order == 4
    assert result.support == (0, 64, 128, 192)
    for y, probability in enumerate(result.probabilities):
        assert probability == (Fraction(1, 4) if y in (0, 64, 128, 192) else 0)
    assert _total(result.probabilities) == 1
    assert result.success_probability == Fraction(1, 2)
    assert set(result.factors) == {3, 5}


def test_order_of_2_modulo_21_from_the_exact_support():
    result = shor.find_order(21, 2)
    assert result.register_qubits == 9
    assert result.order == 6
    assert _total(result.probabilities) == 1
    assert all(p.is_real() for p in result.probabilities)
    success = result.success_probability
    assert not success.is_zero() and success.is_real()
    assert any(not p.is_rational() for p in result.probabilities)
    verified = {candidate for _, candidate in result.candidates if candidate is not None}
    assert min(verified) == 6 and all(c % 6 == 0 for c in verified)
    assert set(result.factors) == {3, 7}


def test_folding_matches_per_class_sums_and_direct_multiplication():
    modulus, base, t = 15, 7, 8
    size = 1 << t
    field = CyclotomicField(size)
    classes = {}
    for x in range(size):
        classes.setdefault(shor.modexp(base, x, modulus), []).append(x)
    probabilities = shor.order_distribution(modulus, base, t)
    for y in (0, 1, 37, 64, 100, 192):
        by_helper = field.zero
        by_product = field.zero
        for members in classes.values():
            exponents = [x * y for x in members]
            by_helper = by_helper + abs2_of_root_sum(field, exponents)
            counts = {}
            for e in exponents:
                counts[e % size] = counts.get(e % size, 0) + 1
            amplitude = field.from_exponents(counts)
            by_product = by_product + amplitude * amplitude.conjugate()
        assert probabilities[y] == by_helper / (size * size) == by_product / (size * size)


def test_unfolded_small_instance_matches():
    modulus, base, t = 5, 2, 5
    size = 1 << t
    field = CyclotomicField(size)
    probabilities = shor.order_distribution(modulus, base, t)
    for y in range(size):
        total = field.zero
        for v in range(modulus):
            amplitude = field.zero
            for x in range(size):
                if shor.modexp(base, x, modulus) == v:
                    amplitude = amplitude + field.zeta(x * y)
            total = total + amplitude.abs2()
        assert probabilities[y] == total / (size * size)
    assert shor.find_order(modulus, base, t).order == 4


def test_factor_15_and_21():
    fifteen = shor.factor(15)
    assert fifteen.factors == (3, 5) and fifteen.method == "order" and fifteen.base == 2
    twenty_one = shor.factor(21)
    assert twenty_one.factors == (3, 7) and twenty_one.method == "order"
    assert twenty_one.order_finding.order == 6
    nine = shor.factor(9)
    assert nine.factors == (3, 3) and nine.method == "gcd"


def test_invalid_inputs_are_rejected():
    for args in ((15, 5), (15, 0), (15, 7, 7)):
        try:
            shor.find_order(*args)
        except ValueError:
            pass
        else:
            raise AssertionError(f"find_order{args} must fail")
    for modulus in (13, 2, 3):
        try:
            shor.factor(modulus)
        except ValueError:
            pass
        else:
            raise AssertionError(f"factor({modulus}) must fail")
    try:
        shor.find_order(91, 2)
    except ValueError as error:
        assert "MAX_REGISTER_QUBITS" in str(error)
    else:
        raise AssertionError("N = 91 needs t = 14 > MAX_REGISTER_QUBITS")
