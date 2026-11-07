from fractions import Fraction
import hashlib
from importlib.resources import files
import sys

import pytest

from chronus.backends.lattice import (
    ParityVerificationError,
    HardwareUnavailableError,
    LatticeOverflowError,
    PhiElement,
    phi_power,
    verify_fold,
)
from chronus.backends.opencl_pv import (
    KERNEL_SHA256,
    OpenCLPVBackend,
    validate_fixed_width,
)
from chronus.backends.lattice_workload import wire_integer
from chronus.backends.limbs import decode_int256, encode_int256


def test_q5_conversion_is_exact_for_fractional_coefficients():
    element = PhiElement.from_q5(Fraction(3, 7), Fraction(2, 5))
    assert Fraction(element.a, element.denominator) == Fraction(3, 7) - Fraction(2, 5)
    assert Fraction(element.b, element.denominator) == Fraction(4, 5)


def test_lucas_90_known_answer_and_norm():
    element = phi_power(90)
    assert element.b == 2880067194370816120
    assert element.trace() == 6440026026380244498
    assert element.norm() == 1


def test_exact_parity_detects_sign_flip_that_preserves_norm():
    input_value = PhiElement(1, 2)
    correct = input_value.multiply(phi_power(3))
    wrong = PhiElement(-correct.a, -correct.b)
    assert correct.norm() == wrong.norm()
    with pytest.raises(ParityVerificationError):
        verify_fold([input_value], [wrong], 3)
    verify_fold([input_value], [correct], 3)


def test_fixed_width_checks_every_intermediate_before_dispatch():
    validate_fixed_width([PhiElement(1, 0)], phi_power(90))
    with pytest.raises(LatticeOverflowError):
        validate_fixed_width([PhiElement(2**63 - 1, 1)], phi_power(2))
    with pytest.raises(LatticeOverflowError):
        validate_fixed_width([PhiElement(-(2**63), 0)], phi_power(3))


def test_packaged_kernel_has_expected_fingerprint():
    source = files("chronus.kernels").joinpath("pv_lattice.cl").read_bytes()
    assert hashlib.sha256(source).hexdigest() == KERNEL_SHA256


def test_opencl_backend_fails_closed_when_dependency_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "pyopencl", None)
    with pytest.raises(HardwareUnavailableError):
        OpenCLPVBackend()


@pytest.mark.parametrize(
    "value",
    [0, 1, -1, -(2**255), 2**255 - 1, -(2**127), 2**127, -(2**63), 2**63],
)
def test_signed_256_limb_round_trip(value):
    assert decode_int256(encode_int256(value)) == value


def test_signed_256_rejects_out_of_range_and_invalid_limbs():
    with pytest.raises(OverflowError):
        encode_int256(2**255)
    with pytest.raises(OverflowError):
        encode_int256(-(2**255) - 1)
    with pytest.raises(ValueError):
        decode_int256((0, 0, 0, 2**64))


def test_deep_lucas_reference_limb_round_trip():
    result = phi_power(360)
    assert decode_int256(encode_int256(result.a)) == result.a
    assert decode_int256(encode_int256(result.b)) == result.b
    assert result.norm() == 1


def test_wire_integer_preserves_precision_and_rejects_non_integer_values():
    assert wire_integer("9223372036854775807") == 9223372036854775807
    for invalid in (True, 1.0, "1e10", "", "9" * 1025, 10**1024):
        with pytest.raises(ValueError):
            wire_integer(invalid)
