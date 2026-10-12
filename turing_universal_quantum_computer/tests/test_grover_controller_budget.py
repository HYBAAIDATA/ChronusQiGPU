"""Exact peak-controller admission and regression checks."""

from fractions import Fraction
from unittest.mock import patch

import pytest

from turing_universal_quantum_computer.hilbert import (
    GroverControllerBudgetError,
    GroverExact,
)
from turing_universal_quantum_computer.quantum_library import QuantumLibrary


def test_large_default_request_refuses_before_fraction_work():
    controller = GroverExact(64)
    with patch(
        "turing_universal_quantum_computer.hilbert.Fraction",
        side_effect=AssertionError("controller entered expensive recurrence"),
    ):
        with pytest.raises(GroverControllerBudgetError, match="admission budget"):
            controller.optimal_iterations()


def test_facade_default_does_not_hide_controller_refusal():
    with pytest.raises(GroverControllerBudgetError, match="admission budget"):
        QuantumLibrary.grover(64, marked=0)


def test_explicit_large_width_iteration_count_stays_exact():
    controller = GroverExact(64)
    assert controller.success_probability(0) == Fraction(1, 1 << 64)
    result = QuantumLibrary.grover(64, marked=0, iterations=1)
    assert result.verify_exactness().exact


def test_bounded_small_peak_keeps_exact_result():
    controller = GroverExact(2)
    assert controller.optimal_iterations(max_stages=2) == 1
    assert controller.success_probability(1) == 1
    with pytest.raises(GroverControllerBudgetError):
        controller.optimal_iterations(max_stages=1)


@pytest.mark.parametrize("budget", [0, -1, True, 2.0, "2"])
def test_controller_budget_is_a_positive_exact_integer(budget):
    with pytest.raises((TypeError, ValueError)):
        GroverExact(2).optimal_iterations(max_stages=budget)
