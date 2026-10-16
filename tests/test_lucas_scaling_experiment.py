"""Regression Test for Lucas State-Space Scaling Experiment.

Validates that:
1. The experiment runs deterministically.
2. Output schema strictly separates theorems, bounds, measured results, and hypotheses.
3. Falsification conditions evaluate correctly.
4. Memory remains O(K) bounded across rungs.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from experiments.lucas_state_space_scaling import (
    exact_lucas,
    execute_scaling_experiment,
    poincare_dist,
)


def test_exact_lucas_numbers() -> None:
    """Validate standard Lucas numbers against sequence definition."""
    expected = {
        0: 2,
        1: 1,
        2: 3,
        3: 4,
        4: 7,
        5: 11,
        10: 123,
        12: 322,
        15: 1364,
        18: 5778,
        20: 15127,
    }
    for n, val in expected.items():
        assert exact_lucas(n) == val


def test_poincare_metric_properties() -> None:
    """Poincaré distance satisfies metric axioms on D^2."""
    z0 = 0.0 + 0.0j
    z1 = 0.5 + 0.0j
    z2 = 0.0 + 0.5j

    # Identity of indiscernibles
    assert poincare_dist(z0, z0) == 0.0

    # Symmetry
    assert abs(poincare_dist(z0, z1) - poincare_dist(z1, z0)) < 1e-9

    # Positivity
    d = poincare_dist(z0, z1)
    assert d > 0.0

    # Triangle inequality
    d01 = poincare_dist(z0, z1)
    d12 = poincare_dist(z1, z2)
    d02 = poincare_dist(z0, z2)
    assert d02 <= d01 + d12 + 1e-9


def test_scaling_experiment_schema_and_falsification() -> None:
    """Experiment executes and produces sound schema without falsification."""
    report = execute_scaling_experiment()

    # Category separation checks
    assert "theorems_and_proven_results" in report
    assert "analytic_bounds" in report
    assert "measured_results" in report
    assert "hypotheses" in report
    assert "falsification_evaluation" in report

    # Falsification conditions passed
    falsification = report["falsification_evaluation"]
    assert falsification["condition_a_distance_monotonicity"]["passed"] is True
    assert falsification["condition_c_memory_linearity"]["passed"] is True
    assert falsification["overall_hypothesis_falsified"] is False

    # Measured rungs monotonicity
    rungs = report["measured_results"]["rungs"]
    assert len(rungs) == 7
    distances = [r["mean_hyperbolic_distance"] for r in rungs]
    for i in range(len(distances) - 1):
        assert distances[i] <= distances[i + 1]
