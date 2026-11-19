"""Hendrix PrimeField: exact EXP/LOG tables, round trips, Zech logarithms, size guard."""

from chronus.hendrix import GF257, MAX_FIELD_ORDER, PrimeField
import pytest

pytestmark = pytest.mark.real

SMALL_PRIMES = (2, 3, 5, 7, 11, 13, 17, 97, 257)


def _raised(exc_type, call):
    try:
        call()
    except exc_type as exc:
        return exc
    raise AssertionError(f"{exc_type.__name__} was not raised")


def _order_by_repeated_multiplication(a, p):
    value, order = a % p, 1
    while value != 1:
        value = value * a % p
        order += 1
    return order


def test_generator_is_the_smallest_element_of_full_order():
    for p in SMALL_PRIMES:
        field = PrimeField(p)
        orders = [_order_by_repeated_multiplication(a, p) for a in range(1, p)]
        assert field.generator == orders.index(p - 1) + 1, p
        assert field.group_order == p - 1


def test_gf257_is_generated_by_3_with_group_order_2_to_the_8():
    assert GF257.p == 257
    assert GF257.generator == 3
    assert GF257.group_order == 256 == 2 ** 8
    assert GF257.group_order_factors == (2,)
    assert PrimeField(257) == GF257


def test_f65537_is_generated_by_3_with_group_order_2_to_the_16():
    field = PrimeField(65537)
    assert field.generator == 3
    assert field.group_order == 2 ** 16
    assert field.group_order_factors == (2,)
    assert field.antilog(2 ** 15) == 65536
    assert field.discrete_log(65536) == 2 ** 15
    assert field.mul(65536, 65536) == 1


def test_tables_agree_with_builtin_pow_for_every_element():
    for p in SMALL_PRIMES:
        field = PrimeField(p)
        g = field.generator
        for k in range(p - 1):
            assert field.antilog(k) == pow(g, k, p)
        for y in range(1, p):
            k = field.discrete_log(y)
            assert 0 <= k < p - 1
            assert pow(g, k, p) == y


def test_log_antilog_and_inverse_round_trips_for_every_element():
    for p in SMALL_PRIMES:
        field = PrimeField(p)
        for k in range(p - 1):
            assert field.discrete_log(field.antilog(k)) == k
        for y in range(1, p):
            assert field.antilog(field.discrete_log(y)) == y
            assert field.mul(y, field.inverse(y)) == 1
            assert field.inverse(field.inverse(y)) == y
            assert field.div(1, y) == field.inverse(y)
        assert sorted(field.antilog(k) for k in range(p - 1)) == list(range(1, p))


def test_exponents_are_reduced_modulo_the_group_order():
    for k in (-1, -256, 256, 257, 10 ** 40 + 3):
        assert GF257.antilog(k) == pow(3, k % 256, 257)
        assert GF257.zech_log(k) == GF257.zech_log(k % 256)


def test_arithmetic_agrees_with_integer_reference_on_f257():
    p = 257
    for a in range(p):
        for b in range(p):
            assert GF257.mul(a, b) == a * b % p
            if b:
                assert GF257.div(a, b) == a * pow(b, -1, p) % p
    for a in range(1, p):
        assert GF257.inverse(a) == pow(a, -1, p)
        for e in (-300, -1, 0, 1, 2, 128, 255, 256, 257, 10 ** 30 + 7):
            assert GF257.pow(a, e) == pow(a, e, p)


def test_arithmetic_reduces_operands_on_small_primes():
    for p in SMALL_PRIMES[:-1]:
        field = PrimeField(p)
        for a in range(-p, 2 * p):
            for b in range(-p, 2 * p):
                assert field.mul(a, b) == a * b % p
                if b % p:
                    assert field.div(a, b) == a * pow(b, -1, p) % p
            for e in range(-3, 2 * p):
                if a % p or e >= 0:
                    assert field.pow(a, e) == pow(a, e, p)


def test_zero_is_handled_explicitly():
    assert GF257.mul(0, 5) == 0
    assert GF257.mul(5, 0) == 0
    assert GF257.div(0, 5) == 0
    assert GF257.pow(0, 0) == 1 == pow(0, 0, 257)
    assert GF257.pow(0, 7) == 0
    assert GF257.is_quadratic_residue(0) is False
    for call in (
        lambda: GF257.inverse(0),
        lambda: GF257.inverse(257),
        lambda: GF257.div(1, 0),
        lambda: GF257.pow(0, -1),
    ):
        _raised(ZeroDivisionError, call)
    for call in (lambda: GF257.discrete_log(0), lambda: GF257.order(0)):
        _raised(ValueError, call)


def test_zech_logarithm_satisfies_its_defining_identity():
    for p in SMALL_PRIMES:
        field = PrimeField(p)
        g = field.generator
        undefined = []
        for n in range(p - 1):
            z = field.zech_log(n)
            one_plus = (1 + pow(g, n, p)) % p
            if z is None:
                assert one_plus == 0
                undefined.append(n)
            else:
                assert 0 <= z < p - 1
                assert pow(g, z, p) == one_plus
        assert undefined == [(p - 1) // 2]


def test_zech_logarithm_turns_addition_into_exponent_arithmetic():
    g, p = GF257.generator, GF257.p
    for a in range(p - 1):
        for b in range(p - 1):
            total = (pow(g, a, p) + pow(g, b, p)) % p
            z = GF257.zech_log(b - a)
            if z is None:
                assert total == 0
            else:
                assert GF257.antilog(a + z) == total


def test_order_and_quadratic_residuosity_agree_with_brute_force():
    for p in SMALL_PRIMES:
        field = PrimeField(p)
        for a in range(1, p):
            assert field.order(a) == _order_by_repeated_multiplication(a, p)
            assert field.is_quadratic_residue(a) is (pow(a, (p - 1) // 2, p) == 1)
        assert sum(field.is_quadratic_residue(a) for a in range(1, p)) == max(1, (p - 1) // 2)


def test_fields_above_the_guard_are_refused_before_any_work():
    assert MAX_FIELD_ORDER == 2 ** 20
    first_prime_above_guard = 1048583
    assert all(first_prime_above_guard % d for d in range(2, 1025))
    for p in (first_prime_above_guard, 2 ** 31 - 1, 2 ** 61 - 1, 2 ** 127 - 1, 2 ** 255 - 19):
        assert "max_order" in str(_raised(ValueError, lambda p=p: PrimeField(p)))
    assert "max_order" in str(_raised(ValueError, lambda: PrimeField(257, max_order=256)))
    assert PrimeField(257, max_order=257) == GF257
    for max_order in (1, MAX_FIELD_ORDER + 1, 2 ** 255):
        _raised(ValueError, lambda max_order=max_order: PrimeField(2, max_order=max_order))


def test_non_primes_and_non_integers_are_refused():
    for n in (-7, 0, 1, 4, 9, 91, 561, 65535, 2 ** 20):
        assert "not prime" in str(_raised(ValueError, lambda n=n: PrimeField(n)))
    for bad in (True, 7.0, "7", None):
        _raised(TypeError, lambda bad=bad: PrimeField(bad))
    _raised(TypeError, lambda: PrimeField(7, max_order=True))
    _raised(TypeError, lambda: GF257.mul(1.5, 2))
    _raised(TypeError, lambda: GF257.antilog(True))
    _raised(TypeError, lambda: GF257.pow(2, 0.5))
    _raised(TypeError, lambda: GF257.discrete_log("3"))


def test_fields_are_immutable_values_with_int_results():
    assert repr(GF257) == "PrimeField(p=257, generator=3)"
    assert PrimeField(13) != GF257
    assert len({PrimeField(13), PrimeField(13), GF257}) == 2
    for value in (GF257.mul(2, 3), GF257.antilog(5), GF257.discrete_log(5), GF257.zech_log(1)):
        assert type(value) is int
    _raised(AttributeError, lambda: setattr(GF257, "p", 5))
    _raised(AttributeError, lambda: setattr(GF257, "extra", 1))
