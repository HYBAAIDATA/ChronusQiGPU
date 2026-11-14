"""Regression tests for numerical behavior at the MCP boundary."""
import math
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from turing import QuantumState, computational_basis_measurement
from turing.mcp_tools import turing_decompose_pauli, turing_measure


@pytest.mark.parametrize("outcome", [0, 1])
def test_collapse_matches_projective_measurement(outcome):
    amplitudes = (0.6j, -0.8)
    expected = computational_basis_measurement(2).collapse(QuantumState(amplitudes), outcome)
    result = turing_measure([[0, 0.6], -0.8], outcome)
    actual = [complex(*value) for value in result["collapsed_state"]["amplitudes"]]
    assert actual == pytest.approx(expected.amplitudes)
    assert result["probabilities"] == pytest.approx([0.36, 0.64])


@pytest.mark.parametrize("outcome", [-2, 2, 64])
def test_collapse_rejects_out_of_range(outcome):
    with pytest.raises(ValueError, match="^outcome index is out of range$"):
        turing_measure([1, 0], outcome)


@pytest.mark.parametrize("amplitudes", [[1, 0], [1, 1e-200]])
def test_collapse_rejects_zero_probability(amplitudes):
    with pytest.raises(ValueError, match="^cannot condition on a zero-probability outcome$"):
        turing_measure(amplitudes, 1)


def test_measure_without_collapse_and_maximum_dimension():
    assert turing_measure([1, 0]) == {"probabilities": [1, 0]}
    result = turing_measure([0] * 63 + [[0, -1]], 63)
    assert result["collapsed_state"]["amplitudes"] == [[0, 0]] * 63 + [[0, -1]]


@pytest.mark.parametrize("component", [1, 1j])
@pytest.mark.parametrize("sign", [1, -1])
def test_pauli_large_representable_coefficients(component, sign):
    value = sys.float_info.max * component
    encoded = [value.real, value.imag]
    other = [sign * value.real, sign * value.imag]
    result = turing_decompose_pauli([[encoded, 0], [0, other]])["coefficients"]
    assert result["I" if sign == 1 else "Z"] == encoded
    assert all(math.isfinite(part) for coefficient in result.values() for part in coefficient)


@pytest.mark.parametrize("value", [complex(math.inf, 0), complex(0, math.inf), complex(math.nan, 0)])
def test_pauli_rejects_nonfinite_coefficients_before_encoding(value):
    operator = SimpleNamespace(dimension=2, matrix=((value, 0j), (0j, 0j)))
    with patch("turing.mcp_tools._operator", return_value=operator):
        with pytest.raises(ValueError, match="Pauli coefficients must be finite"):
            turing_decompose_pauli("I")
