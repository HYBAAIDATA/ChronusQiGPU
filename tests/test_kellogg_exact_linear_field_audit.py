"""Pin the field-channel finding for exact_linear.

The public fit path casts through float before F4 construction, so only
rational channel a is populated. These tests use exact F4 and Fraction
equality. They do not change fit, predict, sign_sigma, or witness_scalar.
"""

from __future__ import annotations

import inspect
import unittest
import warnings
from fractions import Fraction

import numpy as np
from numpy.exceptions import ComplexWarning

from kellogg.exact_tensor import F4
from kellogg.tensor_ml import (
    FIELD_ID,
    MLA1517_VERSION,
    TOE_VERSION,
    PlaneViolation,
    TensorModelAPI,
    TensorState,
    exact_linear,
    witness_scalar,
)


def _channels_are_rational(value: F4) -> None:
    if value.b != Fraction(0) or value.c != Fraction(0) or value.d != Fraction(0):
        raise AssertionError(f"non-rational channel populated: {value!r}")
    if not isinstance(value.a, Fraction):
        raise AssertionError(f"channel a is not a Fraction: {value.a!r}")


class ExactLinearFieldAuditTests(unittest.TestCase):
    """Tests A–I. Each numerical claim is exact equality in F4 or Fraction."""

    def test_A_declared_field_is_q_sqrt2_plus_i_q_sqrt2(self):
        self.assertEqual(FIELD_ID, "Q(sqrt2)+iQ(sqrt2)")
        one = F4(1)
        sqrt2 = F4(0, 1)
        imag = F4(0, 0, 1)
        imag_sqrt2 = F4(0, 0, 0, 1)
        self.assertEqual(sqrt2 * sqrt2, F4(2))
        self.assertEqual(imag * imag, F4(-1))
        self.assertEqual(imag_sqrt2 * imag_sqrt2, F4(-2))
        self.assertEqual((one + imag) * (one - imag), F4(2))
        self.assertEqual(one + imag, F4(1, 0, 1, 0))
        self.assertEqual((F4(1, 1) * F4(1, Fraction(-1, 1))), F4(-1))

    def test_B_public_fit_populates_only_rational_channel(self):
        model = exact_linear().fit(
            np.array([[0.1], [0.1], [0.3]]),
            np.array([0, 0, 1]),
        )
        self.assertEqual(model.weights_exact_, (F4(Fraction(1, 5)),))
        self.assertEqual(model.bias_exact_, F4(Fraction(-1, 150)))
        for value in (*model.weights_exact_, model.bias_exact_):
            _channels_are_rational(value)
        for row in model.fit_state_.rows:
            for value in row:
                _channels_are_rational(value)
                self.assertNotEqual(value.a, Fraction(0.1))
        self.assertEqual(model.fit_state_.rows[0][0].a, Fraction(1, 10))
        self.assertEqual(model.fit_state_.rows[2][0].a, Fraction(3, 10))
        self.assertIn("_as_2d", inspect.getsource(model._state))
        from kellogg import tensor_ml

        self.assertIn("dtype=float", inspect.getsource(tensor_ml._as_2d))

    def test_C_sqrt2_channel_is_dormant_on_public_ingress(self):
        observed = witness_scalar(2 ** 0.5)
        _channels_are_rational(observed)
        self.assertNotEqual(observed, F4(0, 1))
        self.assertNotEqual(observed.a, Fraction(0))
        model = exact_linear().fit(
            np.array([[2 ** 0.5], [0.0], [2 ** 0.5], [0.0]]),
            np.array([0, 0, 1, 1]),
        )
        for value in model.weights_exact_:
            _channels_are_rational(value)
            self.assertNotEqual(value, F4(0, 1))

    def test_D_direct_f4_coefficients_keep_the_sqrt2_channel(self):
        artifact = {
            "schema": {
                "toe_version": TOE_VERSION,
                "mla_version": MLA1517_VERSION,
                "field": FIELD_ID,
                "order": "sigma:real-then-imag",
            },
            "model": "exact_linear",
            "params": {},
            "exact": True,
            "n_features_in": 1,
            "preprocessing_mode": "center_only",
            "preprocessing": {
                "mu": [F4(0).to_json()],
                "commit": "",
                "mode": "center_only",
            },
            "weights": [F4(0, 1).to_json()],
            "bias": F4(0).to_json(),
            "commits": [],
        }
        model = TensorModelAPI.from_artifact(artifact)
        score = model.exact_scores([[1]])[0]
        self.assertEqual(score, F4(0, 1))
        self.assertEqual(score.a, Fraction(0))
        self.assertEqual(score.b, Fraction(1))
        self.assertEqual(score.c, Fraction(0))
        self.assertEqual(score.d, Fraction(0))
        # Channel a is zero, so this sign is not an integer comparison of a.
        self.assertEqual(score.sign_sigma(), 1)
        direct = TensorState.from_values([[F4(0, 1)]])
        self.assertEqual(direct.rows[0][0], F4(0, 1))

    def test_E_sign_sigma_degenerates_to_channel_a_comparison(self):
        model = exact_linear().fit(
            np.array([[0.0], [0.0], [6.0]]),
            np.array([0, 0, 1]),
        )
        for score in model.exact_scores(np.array([[0.0], [6.0], [3.0]])):
            _channels_are_rational(score)
            self.assertEqual(score.a.denominator, 1)
            if score.a.numerator == 0:
                expected = 0
            elif score.a.numerator > 0:
                expected = 1
            else:
                expected = -1
            self.assertEqual(score.sign_sigma(), expected)
        # The quadratic √2 test is live only when channel b is supplied.
        self.assertEqual(F4(-1, 1).sign_sigma(), 1)
        self.assertEqual(F4(-3, 1).sign_sigma(), -1)

    def test_F_one_plus_i_raises_plane_violation(self):
        one_plus_i = F4(1, 0, 1, 0)
        with self.assertRaises(TypeError):
            one_plus_i.sign_sigma()
        model = exact_linear().fit(
            np.array([[-0.5], [0.5]]),
            np.array([0, 1]),
        )
        self.assertEqual(model.weights_exact_, (F4(1),))
        self.assertEqual(model.bias_exact_, F4(0))
        state = TensorState.from_values([[one_plus_i]])
        score = model.exact_scores(state)[0]
        self.assertEqual(score, one_plus_i)
        with self.assertRaises(PlaneViolation):
            model.predict(state)

    def test_G_imaginary_channel_is_discarded_by_the_float_cast(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ComplexWarning)
            model = exact_linear().fit(
                np.array([[1 + 1j], [0 + 0j]]),
                np.array([1, 0]),
            )
        for row in model.fit_state_.rows:
            for value in row:
                _channels_are_rational(value)
                self.assertNotEqual(value, F4(1, 0, 1, 0))
        self.assertEqual(model.fit_state_.rows[0][0].a, Fraction(1))
        self.assertEqual(model.fit_state_.rows[0][0].c, Fraction(0))

    def test_H_float_witness_is_decimal_text_not_binary_fraction(self):
        observed = witness_scalar(0.1)
        self.assertEqual(observed, F4(Fraction(1, 10)))
        self.assertEqual(observed.a, Fraction(1, 10))
        self.assertNotEqual(observed.a, Fraction(0.1))
        self.assertEqual(observed.b, Fraction(0))
        self.assertEqual(observed.c, Fraction(0))
        self.assertEqual(observed.d, Fraction(0))
        self.assertNotEqual(Fraction(0.1), Fraction(1, 10))

    def test_I_zero_score_predicts_class_zero_by_integer_comparison(self):
        model = exact_linear().fit(
            np.array([[-2.0], [2.0]]),
            np.array([0, 1]),
        )
        score = model.exact_scores(np.array([[0.0]]))[0]
        self.assertEqual(score, F4(0))
        self.assertEqual(score.a, Fraction(0))
        self.assertEqual(score.sign_sigma(), 0)
        predicted = model.predict(np.array([[0.0]]))
        self.assertEqual(predicted.tobytes(), np.array([0], dtype=int).tobytes())
        positive = model.exact_scores(np.array([[2.0]]))[0]
        self.assertEqual(positive.a.denominator, 1)
        self.assertEqual(positive.sign_sigma(), 1 if positive.a.numerator > 0 else 0)
        self.assertEqual(
            model.predict(np.array([[2.0]])).tobytes(),
            np.array([1], dtype=int).tobytes(),
        )


if __name__ == "__main__":
    unittest.main()
