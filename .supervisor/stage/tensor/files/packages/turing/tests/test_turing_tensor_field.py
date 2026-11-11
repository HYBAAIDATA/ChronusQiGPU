import sys
from fractions import Fraction
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[1] / "src")
if sys.path[:1] != [_SRC]:
    sys.path.insert(0, _SRC)

from turing.algebra import CyclotomicField  # noqa: E402
from turing.tensor import QQ, CyclotomicNumberField, Field, RationalField, cyclotomic  # noqa: E402

F8 = cyclotomic(8)
ONE, TWO = 1, 2


def _raises(exception, function, *args, **kwargs):
    try:
        function(*args, **kwargs)
    except exception as error:
        return error
    raise AssertionError(f"{function!r} did not raise {exception.__name__}")


def _samples(field, count, seed):
    """Deterministic field elements from an integer recurrence (no randomness)."""
    state = seed
    values = [field.zero, field.one, field.neg(field.one)]
    width = getattr(field, "algebra", None)
    while len(values) < count:
        coordinates = []
        for _ in range(width.degree if width is not None else 1):
            state = (state * 1103515245 + 12345) % (1 << 31)
            numerator = (state >> 8) % 11 - 5
            denominator = 1 + (state >> 16) % 4
            coordinates.append(Fraction(numerator, denominator))
        value = width.element(coordinates) if width is not None else coordinates[0]
        values.append(field.coerce(value))
    return values


def _check_axioms(field, samples):
    add, sub, mul, div, neg, eq = field.add, field.sub, field.mul, field.div, field.neg, field.eq
    zero, one = field.zero, field.one
    for a in samples:
        assert eq(add(a, zero), a)
        assert eq(mul(a, one), a)
        assert field.is_zero(add(a, neg(a)))
        assert field.is_zero(mul(a, zero))
        assert eq(field.conj(field.conj(a)), a)
        product = mul(a, field.conj(a))
        assert eq(field.conj(product), product)
        if not field.is_zero(a):
            assert eq(mul(div(one, a), a), one)
            assert not field.is_zero(product)
        else:
            assert field.is_zero(product)
        for b in samples:
            assert eq(add(a, b), add(b, a))
            assert eq(mul(a, b), mul(b, a))
            assert eq(sub(a, b), add(a, neg(b)))
            assert eq(field.conj(add(a, b)), add(field.conj(a), field.conj(b)))
            assert eq(field.conj(mul(a, b)), mul(field.conj(a), field.conj(b)))
            if not field.is_zero(b):
                assert eq(mul(div(a, b), b), a)
            assert eq(a, b) == field.is_zero(sub(a, b))
            for c in samples[:7]:
                assert eq(add(add(a, b), c), add(a, add(b, c)))
                assert eq(mul(mul(a, b), c), mul(a, mul(b, c)))
                assert eq(mul(a, add(b, c)), add(mul(a, b), mul(a, c)))


def test_field_axioms_for_the_rationals():
    _check_axioms(QQ, _samples(QQ, 14, 7))


def test_field_axioms_for_q_zeta_8():
    _check_axioms(F8, _samples(F8, 12, 11))


def test_from_int_is_a_ring_homomorphism():
    for field in (QQ, F8, cyclotomic(5)):
        assert field.eq(field.from_int(0), field.zero)
        assert field.eq(field.from_int(1), field.one)
        for m in (-7, -1, 0, 2, 9):
            for k in (-3, 0, 1, 4):
                assert field.eq(field.from_int(m + k), field.add(field.from_int(m), field.from_int(k)))
                assert field.eq(field.from_int(m * k), field.mul(field.from_int(m), field.from_int(k)))
                assert field.eq(field.conj(field.from_int(m)), field.from_int(m))


def test_protocol_membership_and_shared_instances():
    assert isinstance(QQ, Field)
    assert isinstance(F8, Field)
    assert QQ is RationalField()
    assert cyclotomic(8) is F8
    assert isinstance(F8, CyclotomicNumberField)
    assert F8.order == 8
    assert F8.algebra is CyclotomicField(8)
    assert cyclotomic(8) == cyclotomic(8) and cyclotomic(8) != cyclotomic(16)
    assert not isinstance(object(), Field)


def test_conjugation_inverts_roots_of_unity():
    zeta = F8.zeta(1)
    assert F8.eq(F8.conj(zeta), F8.zeta(7))
    assert F8.eq(F8.mul(zeta, F8.conj(zeta)), F8.one)
    i = F8.root_of_unity(4, 1)
    assert F8.eq(F8.mul(i, i), F8.from_int(-1))
    assert F8.eq(F8.conj(i), F8.neg(i))


def test_division_by_zero_and_refused_inputs():
    _raises(ZeroDivisionError, QQ.div, QQ.one, QQ.zero)
    _raises(ZeroDivisionError, F8.div, F8.one, F8.zero)
    runtime_float = ONE / TWO
    for field in (QQ, F8):
        _raises(TypeError, field.coerce, runtime_float)
        _raises(TypeError, field.coerce, True)
        _raises(TypeError, field.coerce, "1")
        _raises(TypeError, field.from_int, runtime_float)
        _raises(TypeError, field.from_int, Fraction(1, 2))
    _raises(ValueError, cyclotomic, 0)
    _raises(TypeError, cyclotomic, runtime_float)


def test_coercion_lifts_subfields_only():
    i_in_q4 = CyclotomicField(4).zeta(1)
    lifted = F8.coerce(i_in_q4)
    assert F8.eq(lifted, F8.zeta(2))
    _raises(ValueError, F8.coerce, CyclotomicField(3).zeta(1))
    assert QQ.coerce(Fraction(3, 4)) == Fraction(3, 4)
    assert QQ.coerce(-5) == Fraction(-5)
    assert F8.eq(F8.coerce(Fraction(-2, 3)), F8.algebra.from_rational(Fraction(-2, 3)))


def test_roots_of_unity_by_order():
    assert F8.eq(F8.root_of_unity(8, 3), F8.zeta(3))
    assert F8.eq(F8.root_of_unity(2, 1), F8.from_int(-1))
    assert F8.eq(F8.root_of_unity(16, 2), F8.zeta(1))
    _raises(ValueError, F8.root_of_unity, 16, 1)
    _raises(ValueError, F8.root_of_unity, 3, 1)
    q3 = cyclotomic(3)
    sixth = q3.root_of_unity(6, 1)
    assert q3.eq(q3.mul(sixth, sixth), q3.zeta(1))
    power = q3.one
    for _ in range(6):
        power = q3.mul(power, sixth)
    assert q3.eq(power, q3.one)
    assert not q3.eq(q3.mul(sixth, q3.mul(sixth, sixth)), q3.one)


def test_positive_square_roots_are_exact_and_positive():
    root_two = F8.positive_sqrt(2)
    assert F8.eq(root_two, F8.add(F8.zeta(1), F8.zeta(7)))
    assert F8.eq(F8.mul(root_two, root_two), F8.from_int(2))
    assert F8.eq(F8.positive_sqrt(8), F8.mul(F8.from_int(2), root_two))
    assert F8.eq(F8.positive_sqrt(9), F8.from_int(3))
    assert F8.positive_sqrt(3) is None and F8.positive_sqrt(6) is None
    q5 = cyclotomic(5)
    root_five = q5.positive_sqrt(5)
    # sqrt(5) = 1 + 2 (zeta_5 + zeta_5^4), since zeta_5 + zeta_5^4 = 2 cos(72 degrees) = (sqrt(5) - 1) / 2.
    assert q5.eq(root_five, q5.add(q5.one, q5.mul(q5.from_int(2), q5.add(q5.zeta(1), q5.zeta(4)))))
    q12 = cyclotomic(12)
    root_three = q12.positive_sqrt(3)
    assert q12.eq(root_three, q12.add(q12.zeta(1), q12.zeta(11)))
    assert q12.eq(q12.mul(root_three, root_three), q12.from_int(3))
    assert cyclotomic(3).positive_sqrt(3) is None
    q24 = cyclotomic(24)
    root_six = q24.positive_sqrt(6)
    assert q24.eq(q24.mul(root_six, root_six), q24.from_int(6))
    assert q24.eq(root_six, q24.mul(q24.positive_sqrt(2), q24.positive_sqrt(3)))
    q7 = cyclotomic(28)
    root_seven = q7.positive_sqrt(7)
    assert q7.eq(q7.mul(root_seven, root_seven), q7.from_int(7))
    assert QQ.positive_sqrt(49) == Fraction(7) and QQ.positive_sqrt(2) is None
    _raises(ValueError, QQ.positive_sqrt, 0)
