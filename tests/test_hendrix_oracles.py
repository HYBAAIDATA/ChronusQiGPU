"""Hendrix oracles: protocol shape, exact marked sets, periods and Simon's promise."""

from chronus.hendrix import (
    GF257,
    MAX_PROMISE_CHECK_BITS,
    DiscreteLogOracle,
    PeriodOracle,
    PrimeField,
    QuadraticResidueElementOracle,
    QuadraticResidueOracle,
    XorPeriodOracle,
    is_oracle,
)

ODD_PRIMES = (3, 5, 7, 11, 13, 17, 97, 257)


def _raised(exc_type, call):
    try:
        call()
    except exc_type as exc:
        return exc
    raise AssertionError(f"{exc_type.__name__} was not raised")


def _marked_by_querying(oracle):
    values = [oracle(x) for x in range(oracle.domain_size)]
    assert set(values) <= {0, 1}
    return frozenset(x for x, value in enumerate(values) if value == 1)


def _order_by_repeated_multiplication(a, p):
    value, order = a % p, 1
    while value != 1:
        value = value * a % p
        order += 1
    return order


def test_hendrix_oracles_satisfy_the_protocol():
    oracles = (
        DiscreteLogOracle(GF257, 5),
        QuadraticResidueOracle(GF257),
        QuadraticResidueElementOracle(GF257),
        PeriodOracle(GF257, 2),
        XorPeriodOracle(4, 0b1010),
    )
    for oracle in oracles:
        assert is_oracle(oracle), oracle
        assert type(oracle.domain_size) is int
        assert all(type(oracle(x)) is int for x in range(oracle.domain_size))


def test_is_oracle_checks_the_protocol_by_duck_typing():
    class Parity:
        domain_size = 8

        def __call__(self, x):
            return x & 1

    class NotCallable:
        domain_size = 8

    class SizedOracle:
        def __init__(self, size):
            self.domain_size = size

        def __call__(self, x):
            return 0

    assert is_oracle(Parity())
    assert is_oracle(SizedOracle(1))
    assert not is_oracle(Parity)
    assert not is_oracle(NotCallable())
    assert not is_oracle(lambda x: 0)
    for size in (0, -1, True, 8.0, "8", None):
        assert not is_oracle(SizedOracle(size)), size


def test_discrete_log_oracle_marks_exactly_the_logarithm():
    for p in (2,) + ODD_PRIMES:
        field = PrimeField(p)
        for y in range(1, p):
            oracle = DiscreteLogOracle(field, y)
            assert oracle.domain_size == p - 1
            marked = _marked_by_querying(oracle)
            assert len(marked) == 1 == oracle.marked_count
            assert marked == oracle.marked() == {field.discrete_log(y)}
            (x,) = marked
            assert pow(field.generator, x, p) == y


def test_discrete_log_oracle_validates_its_inputs():
    _raised(ValueError, lambda: DiscreteLogOracle(GF257, 0))
    _raised(ValueError, lambda: DiscreteLogOracle(GF257, 514))
    _raised(TypeError, lambda: DiscreteLogOracle(257, 3))
    _raised(TypeError, lambda: DiscreteLogOracle(GF257, 3.0))
    assert DiscreteLogOracle(GF257, 260).target == 3
    oracle = DiscreteLogOracle(GF257, 3)
    assert oracle(1) == 1
    assert oracle(0) == 0
    for x in (-1, 256, 10 ** 9):
        _raised(ValueError, lambda x=x: oracle(x))
    for x in (True, 1.0, "1"):
        _raised(TypeError, lambda x=x: oracle(x))


def test_quadratic_residue_oracles_mark_half_of_f257():
    over_exponents = QuadraticResidueOracle(GF257)
    assert over_exponents.domain_size == 256
    exponents = _marked_by_querying(over_exponents)
    assert len(exponents) == 128 == over_exponents.marked_count
    assert exponents == over_exponents.marked() == frozenset(range(0, 256, 2))

    over_elements = QuadraticResidueElementOracle(GF257)
    assert over_elements.domain_size == 257
    assert over_elements(0) == 0
    squares = _marked_by_querying(over_elements)
    assert len(squares) == 128 == over_elements.marked_count
    assert squares == over_elements.marked()
    assert squares == {y * y % 257 for y in range(1, 257)}
    assert squares == {x for x in range(1, 257) if pow(x, 128, 257) == 1}
    assert squares == {GF257.antilog(k) for k in exponents}


def test_quadratic_residue_oracles_on_small_odd_primes():
    for p in ODD_PRIMES:
        field = PrimeField(p)
        by_exponent = QuadraticResidueOracle(field)
        by_element = QuadraticResidueElementOracle(field)
        assert _marked_by_querying(by_exponent) == by_exponent.marked()
        assert by_exponent.marked() == frozenset(range(0, p - 1, 2))
        assert _marked_by_querying(by_element) == by_element.marked()
        assert by_element.marked() == {y * y % p for y in range(1, p)}
        assert by_exponent.marked_count == by_element.marked_count == (p - 1) // 2
        assert len(by_element.marked()) == (p - 1) // 2


def test_quadratic_residue_oracles_need_an_odd_prime_field():
    for oracle_type in (QuadraticResidueOracle, QuadraticResidueElementOracle):
        _raised(ValueError, lambda oracle_type=oracle_type: oracle_type(PrimeField(2)))
        _raised(TypeError, lambda oracle_type=oracle_type: oracle_type(257))


def test_period_is_the_brute_force_order_for_every_unit_of_f257():
    for a in range(1, 257):
        oracle = PeriodOracle(GF257, a)
        assert oracle.domain_size == 256
        assert [oracle(x) for x in range(256)] == [pow(a, x, 257) for x in range(256)]
        assert oracle.period() == _order_by_repeated_multiplication(a, 257)
        assert oracle.validate_promise() is True


def test_period_oracle_on_small_primes():
    for p in (2,) + ODD_PRIMES[:-1]:
        field = PrimeField(p)
        for a in range(1, p):
            oracle = PeriodOracle(field, a)
            assert oracle.period() == _order_by_repeated_multiplication(a, p)
            assert (p - 1) % oracle.period() == 0
            assert oracle.validate_promise() is True
    _raised(ValueError, lambda: PeriodOracle(GF257, 0))
    _raised(TypeError, lambda: PeriodOracle(GF257, None))


def test_period_promise_check_rejects_functions_that_break_it():
    class Constant(PeriodOracle):
        def __call__(self, x):
            return 1

    class Shifted(PeriodOracle):
        def __call__(self, x):
            return x + 1

    class WrongPeriod(PeriodOracle):
        def period(self):
            return 2 * super().period()

    assert PeriodOracle(GF257, 16).period() == 4
    assert PeriodOracle(GF257, 16).validate_promise() is True
    assert Constant(GF257, 3).validate_promise() is False
    assert Shifted(GF257, 16).validate_promise() is False
    assert WrongPeriod(GF257, 9).validate_promise() is False
    assert WrongPeriod(GF257, 3).validate_promise() is False


def test_xor_period_oracle_is_two_to_one_with_hidden_period_s():
    for n in range(1, 9):
        for s in range(1, 1 << n):
            oracle = XorPeriodOracle(n, s)
            assert oracle.domain_size == 1 << n
            assert oracle.bits == n
            assert oracle.period() == s
            values = [oracle(x) for x in range(1 << n)]
            preimages = {}
            for x, value in enumerate(values):
                assert value == values[x ^ s] == min(x, x ^ s)
                preimages.setdefault(value, set()).add(x)
            assert all(len(inputs) == 2 for inputs in preimages.values())
            assert preimages[values[0]] == {0, s}
            assert oracle.validate_promise() is True


def test_xor_period_oracle_is_gf2_linear_with_kernel_0_and_s():
    for n in range(1, 6):
        for s in range(1, 1 << n):
            oracle = XorPeriodOracle(n, s)
            values = [oracle(x) for x in range(1 << n)]
            for x in range(1 << n):
                for y in range(1 << n):
                    assert values[x ^ y] == values[x] ^ values[y]
            assert {x for x in range(1 << n) if values[x] == 0} == {0, s}


def test_xor_period_oracle_validates_its_parameters():
    for n, s in ((0, 1), (3, 0), (3, 8), (3, -1), (-2, 1)):
        _raised(ValueError, lambda n=n, s=s: XorPeriodOracle(n, s))
    for n, s in ((True, 1), (3, 1.0), ("3", 1)):
        _raised(TypeError, lambda n=n, s=s: XorPeriodOracle(n, s))
    wide = XorPeriodOracle(64, 2 ** 63 + 5)
    assert wide.domain_size == 2 ** 64
    top = 2 ** 64 - 1
    assert wide(top) == wide(top ^ wide.period()) == top ^ wide.period()
    assert MAX_PROMISE_CHECK_BITS == 20
    _raised(ValueError, lambda: wide.validate_promise())
    _raised(ValueError, lambda: XorPeriodOracle(MAX_PROMISE_CHECK_BITS + 1, 1).validate_promise())
    _raised(ValueError, lambda: XorPeriodOracle(3, 5)(8))


def test_xor_promise_check_rejects_functions_that_break_it():
    class Injective(XorPeriodOracle):
        def __call__(self, x):
            return x

    class Constant(XorPeriodOracle):
        def __call__(self, x):
            return 0

    assert XorPeriodOracle(4, 6).validate_promise() is True
    assert Injective(4, 6).validate_promise() is False
    assert Constant(4, 6).validate_promise() is False


def test_oracle_parameters_are_read_only():
    oracle = DiscreteLogOracle(GF257, 3)
    for name in ("domain_size", "target", "field", "marked_count"):
        _raised(AttributeError, lambda name=name: setattr(oracle, name, 1))
    _raised(AttributeError, lambda: setattr(XorPeriodOracle(3, 5), "bits", 4))


def test_oracles_are_deterministic_across_instances():
    first = PeriodOracle(GF257, 6)
    second = PeriodOracle(PrimeField(257), 6)
    assert [first(x) for x in range(256)] == [second(x) for x in range(256)]
    assert repr(first) == "PeriodOracle(p=257, a=6)"
    assert repr(XorPeriodOracle(3, 5)) == "XorPeriodOracle(n=3, s=5)"
