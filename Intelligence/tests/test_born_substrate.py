"""Regression tests for the Born-rule substrate conversions in Intelligence/.

Pins the semantics every converted learner relies on: probabilities come
out of a qubit rotation, never a linear ``w += k`` step, and stay inside
[0, 1] for all inputs without clamping.
"""

from __future__ import annotations

import math

import pytest

from Intelligence._born import (
    QUARTER_TURN,
    adjust_probability,
    born_evidence,
    probability_qubit,
)


class TestBornEvidence:
    def test_flat_prior_is_half(self):
        assert born_evidence(0, 0) == pytest.approx(0.5)

    def test_posterior_counts(self):
        assert born_evidence(1, 0) == pytest.approx(2 / 3)
        assert born_evidence(0, 1) == pytest.approx(1 / 3)
        assert born_evidence(3, 1) == pytest.approx(4 / 6)

    def test_symmetric_counts_stay_half(self):
        assert born_evidence(5, 5) == pytest.approx(0.5)


class TestProbabilityQubit:
    def test_probabilities_round_trip(self):
        for p in (0.0, 0.25, 0.5, 0.618, 0.99, 1.0):
            state = probability_qubit(p)
            assert state.probabilities()[0] == pytest.approx(p, abs=1e-12)

    def test_normalized(self):
        state = probability_qubit(0.3)
        assert state.norm() == pytest.approx(1.0, abs=1e-12)


class TestAdjustProbability:
    """The unitary replacement for linear ``w +=`` / ``w *=`` updates."""

    @pytest.mark.parametrize("p", [0.0, 0.1, 0.37, 0.5, 0.9, 1.0])
    @pytest.mark.parametrize("angle", [0.0, 0.1, QUARTER_TURN / 2, QUARTER_TURN, math.pi])
    def test_stays_in_unit_interval(self, p, angle):
        for toward in (True, False):
            out = adjust_probability(p, toward, angle)
            assert 0.0 <= out <= 1.0, (p, angle, toward, out)

    def test_zero_angle_is_identity(self):
        assert adjust_probability(0.42, True, 0.0) == pytest.approx(0.42, abs=1e-12)
        assert adjust_probability(0.42, False, 0.0) == pytest.approx(0.42, abs=1e-12)

    def test_monotone_convergence_to_one(self):
        p = 0.5
        seen = [p]
        for _ in range(20):
            p = adjust_probability(p, True, QUARTER_TURN)
            seen.append(p)
        assert all(b >= a for a, b in zip(seen, seen[1:]))
        assert seen[-1] == pytest.approx(1.0, abs=1e-9)

    def test_monotone_convergence_to_zero(self):
        p = 0.5
        seen = [p]
        for _ in range(20):
            p = adjust_probability(p, False, QUARTER_TURN)
            seen.append(p)
        assert all(b <= a for a, b in zip(seen, seen[1:]))
        assert seen[-1] == pytest.approx(0.0, abs=1e-9)

    def test_extreme_angles_do_not_wrap(self):
        # A half-turn overshoot is clamped by measured separation —
        # pushing toward |1> from p=1.0 must not wrap to p<1.
        assert adjust_probability(1.0, True, math.pi) == pytest.approx(1.0)
        assert adjust_probability(0.0, False, math.pi) == pytest.approx(0.0)


class TestNeuralPlasticityRotation:
    def test_reward_updates_weights_within_bounds(self):
        from Intelligence.neural_plasticity import NeuralPlasticity

        np_sys = NeuralPlasticity(sprout_threshold=1)
        np_sys.co_activate("a", "b")
        assert ("a", "b") in np_sys.synapses
        for _ in range(10):
            np_sys.co_activate("a", "b")
            np_sys.deliver_reward(1.0)
            np_sys.decay()
        w = np_sys.synapses[("a", "b")].weight
        assert 0.0 < w <= 1.0
        # Repeated positive reward potentiates beyond the 0.1 seed weight.
        assert w > 0.1

    def test_negative_reward_depresses(self):
        from Intelligence.neural_plasticity import NeuralPlasticity

        np_sys = NeuralPlasticity(sprout_threshold=1)
        np_sys.co_activate("a", "b")
        w0 = np_sys.synapses[("a", "b")].weight
        np_sys.co_activate("a", "b")
        np_sys.deliver_reward(-1.0)
        assert np_sys.synapses[("a", "b")].weight < w0
