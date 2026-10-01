from fractions import Fraction

from python_backend.core_modules.math_folding import (
    PHI,
    below_pisot_threshold,
    pisot_threshold,
    pulvini_fold,
    truncate_pisot,
    zeckendorf_address,
)


def test_zeckendorf_addresses_round_trip_and_are_non_adjacent():
    for index in range(0, 10_000):
        address = zeckendorf_address(index)
        assert address.verify()
        assert address.non_adjacent


def test_pulvini_fold_round_trip_is_bit_exact():
    values = tuple(Fraction(index, index + 1) for index in range(1, 100))
    assert pulvini_fold(values).unfold() == values


def test_pisot_threshold_is_exact_algebraic_inverse():
    for n in range(0, 100):
        assert pisot_threshold(n) * (PHI**n) == PHI**0


def test_pisot_comparison_and_discarded_weight_are_exact():
    assert below_pisot_threshold(Fraction(1, 100), 5)
    result = truncate_pisot(
        [Fraction(1, 100), Fraction(1, 10), Fraction(1, 1)],
        5,
    )
    assert result.discarded == (Fraction(1, 100),)
    assert result.discarded_weight == Fraction(1, 10_000)
    assert result.retained == (Fraction(1, 10), Fraction(1, 1))


def test_float_inputs_are_rejected():
    try:
        truncate_pisot([0.01], 5)
    except TypeError:
        pass
    else:
        raise AssertionError("floating-point truncation input must fail")
