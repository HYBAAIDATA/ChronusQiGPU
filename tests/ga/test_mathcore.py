import random

import pytest

from ga.mathcore import GALOIS, ORDER

_RANDOM = random.Random(20261114)
SAMPLES = tuple(_RANDOM.randrange(0, GALOIS.q) for _ in range(48))


def test_primitive_polynomial_is_verified():
    assert GALOIS.modulus.bit_length() == 17
    assert GALOIS.modulus == GALOIS.PRIMITIVE_POLY
    assert GALOIS.pow(GALOIS.primitive, ORDER) == 1
    for factor in (3, 5, 17, 257):
        assert GALOIS.pow(GALOIS.primitive, ORDER // factor) != 1


def test_field_axioms():
    assert GALOIS.mul(0x8000, 2) == 0x002D
    for index, a in enumerate(SAMPLES):
        b = SAMPLES[(index + 1) % len(SAMPLES)]
        c = SAMPLES[(index + 2) % len(SAMPLES)]
        assert GALOIS.add(a, b) == GALOIS.add(b, a)
        assert GALOIS.mul(a, b) == GALOIS.mul(b, a)
        assert GALOIS.add(GALOIS.add(a, b), c) == GALOIS.add(a, GALOIS.add(b, c))
        assert GALOIS.mul(GALOIS.mul(a, b), c) == GALOIS.mul(a, GALOIS.mul(b, c))
        assert GALOIS.mul(a, GALOIS.add(b, c)) == GALOIS.add(
            GALOIS.mul(a, b), GALOIS.mul(a, c)
        )
        assert GALOIS.add(a, 0) == a
        assert GALOIS.mul(a, 1) == a
        assert GALOIS.add(a, a) == 0
        assert GALOIS.trace(a) in (0, 1)
        if a:
            assert GALOIS.mul(a, GALOIS.inv(a)) == 1


def test_polynomial_index_round_trip():
    for value in (0, 1, 2, 0xBEEF, GALOIS.q - 1):
        assert GALOIS.poly_to_index(GALOIS.index_to_poly(value)) == value


def test_zeckendorf_coding_reconstructs_input():
    from ga.mathcore import PhyllotaxisLattice

    lattice = PhyllotaxisLattice(capacity=10_007)
    for value in (0, 1, 2, 3, 4, 12, 100, 10**18 - 1):
        coding = lattice._zeckendorf_index(value)
        assert coding & (coding >> 1) == 0
        fibonacci = lattice._fibonacci_up_to(value)
        assert (
            sum(
                fibonacci[index]
                for index in range(coding.bit_length())
                if coding & (1 << index)
            )
            == value
        )


def test_invalid_field_inputs_fail_explicitly():
    with pytest.raises(ZeroDivisionError):
        GALOIS.inv(0)
    with pytest.raises(ValueError):
        type(GALOIS)(2, 8)
