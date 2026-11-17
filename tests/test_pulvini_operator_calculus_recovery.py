"""Archived PULVINI V3 linear-operator relations over full retained fold state."""
from __future__ import annotations

import numpy as np
import pytest

from chronus.pulvini.operator_calculus import PulviniOperatorCalculus

pytestmark = pytest.mark.simulated


@pytest.mark.parametrize("norm", ["orthonormal","legacy"])
@pytest.mark.parametrize("n", [1,2,3,8,21])
def test_full_state_induced_metric_is_scalar_identity(norm,n):
    calc = PulviniOperatorCalculus(normalization=norm)
    cert = calc.certificate(n)
    assert cert.verified is True
    assert cert.injective is True
    assert cert.induced_metric_relative_error <= 1e-10
    assert abs(cert.operator_condition_number-1) < 1e-10
    if norm == "orthonormal":
        assert cert.induced_metric_scale == pytest.approx(1.0, abs=1e-12)


@pytest.mark.parametrize("norm", ["orthonormal","legacy"])
def test_lifted_action_matches_direct_unfolded_operator(norm):
    calc = PulviniOperatorCalculus(normalization=norm)
    A = np.array([[.25, 1., 0.],[-.5, .2, 2.],[2., -1., .3]],dtype=np.float64)
    x = np.array([1.,2.,3.],dtype=np.float64)
    result = calc.verify_action(A,x)
    assert result["verified"] is True
    assert result["relative_error"] <= result["tolerance"]
    assert result["complete_state_required"] is True
    assert result["physical_accelerator_measured"] is False


def test_complex_operator_action_preserves_imaginary_information():
    calc = PulviniOperatorCalculus()
    A = np.array([[1+0j,1+2j],[0-1j,2+1j]],dtype=np.complex128)
    x = np.array([2+3j,4-1j],dtype=np.complex128)
    assert calc.verify_action(A,x)["verified"] is True


def test_illegal_matrix_budget_fails_before_dense_allocation():
    calc = PulviniOperatorCalculus(max_dimensions=32)
    with pytest.raises(ValueError,match="bounded"):
        calc.fold_matrix(1000000)
    with pytest.raises(ValueError,match="bounded"):
        calc.lift(np.eye(40))


def test_nonfinite_operator_and_mismatched_vector_rejected():
    calc = PulviniOperatorCalculus()
    with pytest.raises(ValueError):
        calc.lift(np.array([[float('nan')]]))
    with pytest.raises(ValueError,match="shape"):
        calc.verify_action(np.eye(3),np.ones(4))


def test_folded_channel_alone_is_not_the_certified_full_state():
    calc = PulviniOperatorCalculus()
    M = calc.fold_matrix(21)
    cert = calc.certificate(21)
    op = calc._operator
    n1,_ = op.fibonacci_split(21)
    collapsed = M[:n1,:]
    assert collapsed.shape[0] < 21
    assert np.linalg.matrix_rank(collapsed) < 21
    assert cert.verified is True


def test_large_integer_action_uses_promoted_reference_not_wrapping_int64():
    calc = PulviniOperatorCalculus()
    A = np.array([[2**62]], dtype=np.int64)
    x = np.array([4], dtype=np.int64)
    assert calc.verify_action(A, x)["verified"] is True


def test_nonrepresentable_integer_operator_rejected_before_lift():
    calc = PulviniOperatorCalculus()
    with pytest.raises(ValueError, match="exactly representable"):
        calc.lift(np.array([[2**53+1]], dtype=np.int64))


def test_finite_large_matrix_cannot_return_nonfinite_lift():
    calc = PulviniOperatorCalculus()
    A = np.full((2, 2), np.finfo(np.float64).max)
    with pytest.raises(ValueError, match="overflow"):
        calc.lift(A)


def test_numeric_looking_text_matrix_cannot_be_promoted_to_valid_operator():
    calc = PulviniOperatorCalculus()
    A = np.array([["1.0", "2.0"], ["3.0", "4.0"]])
    with pytest.raises(ValueError, match="finite numeric original"):
        calc.verify_action(A, np.array([1.0, 2.0]))
