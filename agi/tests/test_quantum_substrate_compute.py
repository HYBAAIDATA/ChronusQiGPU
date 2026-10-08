"""Regression tests for the agi/ quantum-substrate compute paths.

These pin the production-closure contract: every computed quantity is
substrate math (deterministic on the kellogg quantum substrate), an
honestly labelled classical deterministic evaluation, or an explicit
unavailability marker — never an RNG draw, invented constant, or canned
payload reaching a result.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agi.quantum_decision import (
    _erf_vec,
    _erfinv_series,
    decision_analysis,
    expectation_on_context,
    grover_amplify,
    normal_quantile_grid,
    quantile_grid,
    substrate_state_from_belief,
    weyl_unit_sequence,
)


class TestQuantileGrid:
    def test_deterministic(self):
        a = normal_quantile_grid(0.0, 1.0, 64)
        b = normal_quantile_grid(0.0, 1.0, 64)
        np.testing.assert_array_equal(a, b)

    def test_normal_moments(self):
        grid = normal_quantile_grid(2.0, 0.5, 4001)
        assert abs(float(grid.mean()) - 2.0) < 0.02
        assert abs(float(grid.std()) - 0.5) < 0.02

    def test_normal_symmetric(self):
        grid = normal_quantile_grid(0.0, 1.0, 101)
        np.testing.assert_allclose(grid, -grid[::-1], atol=1e-12)

    def test_quantile_grid_supported_distributions(self):
        for dist, params in (
            ("uniform", {"low": 0.0, "high": 2.0}),
            ("exponential", {"scale": 1.5}),
            ("lognormal", {"mean": 0.0, "std": 0.5}),
            ("normal", {"mean": 1.0, "std": 0.5}),
        ):
            g = quantile_grid(dist, params, 257)
            assert len(g) == 257
            assert np.isfinite(g).all()

    def test_erfinv_roundtrip(self):
        # erf(erfinv(y)) == y across the interior of (-1, 1).
        y = np.linspace(-0.99, 0.99, 99)
        np.testing.assert_allclose(_erf_vec(_erfinv_series(y)), y, atol=1e-6)


class TestWeylSequence:
    def test_unit_interval_and_distinct(self):
        seq = weyl_unit_sequence(12345, 500)
        assert seq.shape == (500,)
        assert (seq >= 0.0).all() and (seq < 1.0).all()
        assert len(set(seq.tolist())) == 500

    def test_deterministic_per_seed(self):
        np.testing.assert_array_equal(weyl_unit_sequence(7, 50), weyl_unit_sequence(7, 50))
        assert not np.array_equal(weyl_unit_sequence(7, 50), weyl_unit_sequence(8, 50))


class TestBeliefState:
    def test_born_rule_recovers_distribution(self):
        belief = [0.25, 0.25, 0.5]
        state = substrate_state_from_belief(belief, dim=3)
        np.testing.assert_allclose(state.probabilities(), belief, atol=1e-9)

    def test_normalized(self):
        state = substrate_state_from_belief([0.2, 0.8], dim=2)
        assert abs(sum(state.probabilities()) - 1.0) < 1e-9

    def test_zero_belief_falls_back_uniform(self):
        state = substrate_state_from_belief([0.0, 0.0], dim=2)
        np.testing.assert_allclose(state.probabilities(), [0.5, 0.5])


class TestDecisionAnalysis:
    def test_returns_measured_keys(self):
        state = substrate_state_from_belief([0.1, 0.6, 0.3], dim=3)
        result = decision_analysis(state, [0.0, 1.0, 0.5])
        assert result["evidence_class"] == "quantum_substrate_measured"
        assert 0 <= result["optimal_action"] < 3
        assert isinstance(result["expected_utility"], float)
        assert result["quantum_fisher_information"] >= 0.0
        assert "born_probabilities" in result

    def test_argmax_born_is_selected(self):
        state = substrate_state_from_belief([0.7, 0.2, 0.1], dim=3)
        result = decision_analysis(state, [1.0, 1.0, 1.0])
        assert result["optimal_action"] == 0

    def test_expectation_matches_born_weighted_utility(self):
        state = substrate_state_from_belief([0.25, 0.75], dim=2)
        result = decision_analysis(state, [0.0, 1.0])
        assert abs(result["expected_utility"] - 0.75) < 1e-6


class TestExpectationOnContext:
    def test_measured_expectation(self):
        ctx = [0.4, 0.6, 0.2, 0.9]
        result = expectation_on_context(ctx)
        assert result["evidence_class"] == "quantum_substrate_measured"
        assert 0.0 <= result["expectation"] <= 1.0
        assert result["fisher_information"] >= 0.0

    def test_deterministic(self):
        a = expectation_on_context([1.0, 2.0, 3.0])
        b = expectation_on_context([1.0, 2.0, 3.0])
        assert a["expectation"] == b["expectation"]


class TestGroverAmplify:
    def test_marked_state_amplified(self):
        state = substrate_state_from_belief([1 / 8] * 8, dim=8)
        evolved, iters = grover_amplify(state, {3}, iterations=2)
        probs = evolved.probabilities()
        assert probs[3] > 0.9
        assert iters == 2

    def test_deterministic(self):
        state = substrate_state_from_belief([0.25] * 4, dim=4)
        a, _ = grover_amplify(state, {1}, iterations=1)
        b, _ = grover_amplify(state, {1}, iterations=1)
        np.testing.assert_allclose(a.probabilities(), b.probabilities())
