"""Pin the algorithm-class finding for exact_linear.

fit computes w = μ₁ − μ₀ and b = −w · ((μ₁ + μ₀)/2). It is a
nearest-centroid classifier expressed as an exact linear threshold.
These tests use exact F4 and Fraction equality. They do not change
fit, predict, sign_sigma, or witness_scalar, and they do not remove
the dead parameters or the unused ExactTOETensor.
"""

from __future__ import annotations

import ast
import inspect
import json
import textwrap
import unittest
import warnings
from fractions import Fraction
from pathlib import Path

import numpy as np

from kellogg.exact_tensor import ExactTOETensor, F4
from kellogg.tensor_ml import (
    PlaneViolation,
    TensorClassifier,
    exact_linear,
    witness_scalar,
)
import kellogg.tensor_ml as tensor_ml


def _f4_bytes(value: F4) -> bytes:
    return json.dumps(value.to_json(), separators=(",", ":")).encode("ascii")


def _weights_bytes(model) -> bytes:
    payload = [value.to_json() for value in model.weights_exact_]
    return json.dumps(payload, separators=(",", ":")).encode("ascii")


def _attribute_names(tree: ast.AST) -> list[str]:
    return [node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)]


class ExactLinearAlgorithmAuditTests(unittest.TestCase):
    """Tests N1–N14. Numerical claims are exact equality in F4 or Fraction."""

    def test_N1_weight_formula_is_centroid_difference(self):
        # Class 0 twice at 0, class 1 once at 6. After center_only the
        # class means are −2 and 4, so w = 6 and the midpoint is 1.
        model = exact_linear().fit(
            np.array([[0.0], [0.0], [6.0]]),
            np.array([0, 0, 1]),
        )
        mu0 = F4(-2)
        mu1 = F4(4)
        weight = mu1 - mu0
        midpoint = (mu1 + mu0) / F4(2)
        bias = -(weight * midpoint)
        self.assertEqual(weight, F4(6))
        self.assertEqual(midpoint, F4(1))
        self.assertEqual(bias, F4(-6))
        self.assertEqual(model.weights_exact_, (weight,))
        self.assertEqual(model.bias_exact_, bias)
        self.assertEqual(model.weights_exact_[0].a, Fraction(6))
        self.assertEqual(model.bias_exact_.a, Fraction(-6))
        for channel in (
            model.weights_exact_[0].b,
            model.weights_exact_[0].c,
            model.weights_exact_[0].d,
            model.bias_exact_.b,
            model.bias_exact_.c,
            model.bias_exact_.d,
        ):
            self.assertEqual(channel, Fraction(0))

    def test_N2_symmetric_midpoint_scores_zero_and_predicts_class_zero(self):
        model = exact_linear().fit(
            np.array([[-2.0], [2.0]]),
            np.array([0, 1]),
        )
        score = model.exact_scores(np.array([[0.0]]))[0]
        self.assertEqual(score, F4(0))
        self.assertEqual(score.a, Fraction(0))
        self.assertEqual(score.b, Fraction(0))
        self.assertEqual(score.c, Fraction(0))
        self.assertEqual(score.d, Fraction(0))
        predicted = model.predict(np.array([[0.0]]))
        self.assertEqual(predicted.tobytes(), np.array([0], dtype=int).tobytes())

    def test_N3_dead_parameters_do_not_change_the_fitted_threshold(self):
        features = np.array([[0.0, 0.0], [0.0, 0.0], [2.0, 6.0], [2.0, 6.0]])
        labels = np.array([0, 0, 1, 1])
        baseline = exact_linear().fit(features, labels)
        for name, value in (
            ("n_estimators", 7),
            ("max_depth", 3),
            ("learning_rate", Fraction(1, 5)),
            ("random_state", 123),
        ):
            with self.subTest(parameter=name):
                model = exact_linear().fit(features, labels)
                model.params[name] = value
                model.fit(features, labels)
                self.assertEqual(model.params[name], value)
                self.assertEqual(model.weights_exact_, baseline.weights_exact_)
                self.assertEqual(model.bias_exact_, baseline.bias_exact_)
                self.assertEqual(_weights_bytes(model), _weights_bytes(baseline))
                self.assertEqual(_f4_bytes(model.bias_exact_), _f4_bytes(baseline.bias_exact_))
                fit_tree = ast.parse(textwrap.dedent(inspect.getsource(TensorClassifier.fit)))
                used = [
                    node.id
                    for node in ast.walk(fit_tree)
                    if isinstance(node, ast.Name)
                ]
                self.assertNotIn(name, used)

    def test_N4_dead_prior_does_not_change_predictions(self):
        features = np.array([[0.0], [2.0], [0.0], [2.0]])
        labels = np.array([0, 1, 0, 1])
        model = exact_linear().fit(features, labels)
        before = model.predict(features).tobytes()
        weights = _weights_bytes(model)
        model.class_prior_exact_ = [F4(Fraction(9, 10)), F4(Fraction(1, 10))]
        self.assertEqual(model.predict(features).tobytes(), before)
        model.fit(features, labels)
        self.assertEqual(model.predict(features).tobytes(), before)
        self.assertEqual(_weights_bytes(model), weights)
        self.assertEqual(model.class_prior_exact_[0], F4(Fraction(1, 2)))
        self.assertEqual(model.class_prior_exact_[1], F4(Fraction(1, 2)))
        tree = ast.parse(textwrap.dedent(inspect.getsource(TensorClassifier.fit)))
        loads = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and node.attr == "class_prior_exact_"
            and isinstance(node.ctx, ast.Load)
        ]
        stores = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and node.attr == "class_prior_exact_"
            and isinstance(node.ctx, ast.Store)
        ]
        self.assertEqual(loads, [])
        self.assertEqual(len(stores), 1)

    def test_N5_exact_toe_tensor_is_constructed_and_unread(self):
        model = exact_linear()
        self.assertIsInstance(model.exact_tensor, ExactTOETensor)
        self.assertEqual(model.exact_tensor.num_qubits, 5)
        init_source = inspect.getsource(TensorClassifier.__init__)
        self.assertIn("ExactTOETensor(num_qubits=5)", init_source)
        accessed: list[str] = []

        class _Unread:
            def __getattribute__(self, name):
                accessed.append(name)
                raise AssertionError(f"exact_tensor was read: {name}")

        model.exact_tensor = _Unread()
        features = np.array([[0.0], [1.0]])
        labels = np.array([0, 1])
        model.fit(features, labels)
        model.predict(features)
        model.predict_proba(features)
        model.exact_scores(features)
        self.assertEqual(accessed, [])
        module = ast.parse(Path(tensor_ml.__file__).read_text(encoding="utf-8"))
        for node in module.body:
            if not isinstance(node, ast.ClassDef) or node.name != "TensorClassifier":
                continue
            for item in node.body:
                if not isinstance(item, ast.FunctionDef) or item.name == "__init__":
                    continue
                self.assertNotIn("exact_tensor", _attribute_names(item))

    def test_N6_exact_midpoint_has_sign_zero_and_predicts_class_zero(self):
        model = exact_linear().fit(
            np.array([[0.0], [0.0], [6.0]]),
            np.array([0, 0, 1]),
        )
        score = model.exact_scores(np.array([[3.0]]))[0]
        self.assertEqual(score, F4(0))
        self.assertEqual(score.sign_sigma(), 0)
        predicted = model.predict(np.array([[3.0]]))
        self.assertEqual(int(predicted[0]), 0)
        self.assertEqual(predicted.tobytes(), np.array([0], dtype=int).tobytes())

    def test_N7_predict_proba_is_a_display_map(self):
        features = np.array([[0.0], [0.0], [0.0], [2.0]])
        labels = np.array([0, 0, 0, 1])
        probabilities = exact_linear().fit(features, labels).predict_proba(features)
        self.assertEqual(probabilities.shape, (4, 2))
        for row in probabilities:
            self.assertEqual(row[0] + row[1], 1.0)
            self.assertNotIsInstance(row[0], F4)
            self.assertNotIsInstance(row[1], F4)
            self.assertNotEqual(row[1], 0.25)
        self.assertNotEqual(probabilities[0, 1], probabilities[3, 1])

    def test_N8_aliases_fit_the_same_exact_linear_object(self):
        features = np.array([[0.0, 0.0], [0.0, 0.0], [2.0, 6.0], [2.0, 6.0]])
        labels = np.array([0, 0, 1, 1])
        canonical = exact_linear().fit(features, labels)
        for name in ("rf", "xgb", "lgbm", "gb"):
            with self.subTest(alias=name):
                tensor_ml._warned_aliases.clear()
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    alias = getattr(tensor_ml, name)().fit(features, labels)
                self.assertTrue(any(item.category is DeprecationWarning for item in caught))
                self.assertEqual(alias.model_family.encode("ascii"), b"exact_linear")
                self.assertEqual(alias.name.encode("ascii"), canonical.name.encode("ascii"))
                self.assertEqual(alias.weights_exact_, canonical.weights_exact_)
                self.assertEqual(alias.bias_exact_, canonical.bias_exact_)
                self.assertEqual(_weights_bytes(alias), _weights_bytes(canonical))
                self.assertEqual(_f4_bytes(alias.bias_exact_), _f4_bytes(canonical.bias_exact_))

    def test_N9_one_class_input_has_zero_weights_and_predicts_class_zero(self):
        features = np.array([[1.0], [3.0], [5.0]])
        labels = np.array([1, 1, 1])
        model = exact_linear().fit(features, labels)
        self.assertEqual(len(model.weights_exact_), 1)
        weight = model.weights_exact_[0]
        self.assertEqual(weight, F4(0, 0, 0, 0))
        self.assertEqual(weight.a, Fraction(0))
        self.assertEqual(weight.b, Fraction(0))
        self.assertEqual(weight.c, Fraction(0))
        self.assertEqual(weight.d, Fraction(0))
        predicted = model.predict(features)
        self.assertEqual(predicted.tobytes(), np.array([0, 0, 0], dtype=int).tobytes())

    def test_N10_center_only_weights_match_the_raw_centroid_difference(self):
        features = np.array([[0.0, 1.0], [0.0, 1.0], [4.0, 5.0]])
        labels = np.array([0, 0, 1])
        rows = [
            [witness_scalar(value) for value in row]
            for row in np.asarray(features, dtype=float).tolist()
        ]
        width = len(rows[0])

        def mean_for(klass: int) -> tuple[F4, ...]:
            selected = [row for row, label in zip(rows, labels) if int(label) == klass]
            count = F4(len(selected))
            return tuple(
                sum((row[col] for row in selected), F4(0)) / count for col in range(width)
            )

        raw_mu0 = mean_for(0)
        raw_mu1 = mean_for(1)
        raw_weights = tuple(positive - negative for positive, negative in zip(raw_mu1, raw_mu0))
        raw_midpoint = tuple(
            (positive + negative) / F4(2) for positive, negative in zip(raw_mu1, raw_mu0)
        )
        raw_bias = -sum(
            (weight * centre for weight, centre in zip(raw_weights, raw_midpoint)),
            F4(0),
        )
        model = exact_linear(tensor_mode="center_only").fit(features, labels)
        self.assertEqual(raw_weights, (F4(4), F4(4)))
        self.assertEqual(model.weights_exact_, raw_weights)
        self.assertEqual(_weights_bytes(model), json.dumps(
            [value.to_json() for value in raw_weights], separators=(",", ":")
        ).encode("ascii"))
        self.assertEqual(raw_bias, F4(-20))
        self.assertEqual(model.bias_exact_, F4(Fraction(-16, 3)))
        self.assertNotEqual(model.bias_exact_, raw_bias)

    def test_N11_range_mode_differs_and_rejects_a_constant_column(self):
        features = np.array([[0.0, 0.0], [2.0, 10.0]])
        labels = np.array([0, 1])
        probe = np.array([[6.0, 0.0]])
        centered = exact_linear(tensor_mode="center_only").fit(features, labels)
        ranged = exact_linear(tensor_mode="range").fit(features, labels)
        self.assertEqual(centered.weights_exact_, (F4(2), F4(10)))
        self.assertEqual(ranged.weights_exact_, (F4(1), F4(1)))
        self.assertNotEqual(centered.weights_exact_, ranged.weights_exact_)
        self.assertNotEqual(
            centered.predict(probe).tobytes(),
            ranged.predict(probe).tobytes(),
        )
        self.assertEqual(int(centered.predict(probe)[0]), 0)
        self.assertEqual(int(ranged.predict(probe)[0]), 1)
        constant = np.array([[1.0, 0.0], [1.0, 2.0], [1.0, 4.0], [1.0, 6.0]])
        constant_labels = np.array([0, 0, 1, 1])
        with self.assertRaises(ValueError) as raised:
            exact_linear(tensor_mode="range").fit(constant, constant_labels)
        self.assertEqual(type(raised.exception), ValueError)
        self.assertIn("constant", str(raised.exception))

    def test_N12_float_ingress_witness_is_one_tenth_not_binary(self):
        observed = witness_scalar(0.1)
        self.assertEqual(observed, F4(Fraction(1, 10)))
        self.assertEqual(observed.a, Fraction(1, 10))
        self.assertNotEqual(observed.a, Fraction(0.1))
        self.assertNotEqual(Fraction(0.1), Fraction(1, 10))
        self.assertEqual(observed.b, Fraction(0))
        self.assertEqual(observed.c, Fraction(0))
        self.assertEqual(observed.d, Fraction(0))

    def test_N13_feature_importance_is_the_float_projection(self):
        features = np.array([[0.0, 0.0], [0.0, 0.0], [2.0, 6.0], [2.0, 6.0]])
        labels = np.array([0, 0, 1, 1])
        model = exact_linear().fit(features, labels)
        self.assertEqual(model.weights_exact_, (F4(2), F4(6)))
        projections = []
        for weight in model.weights_exact_:
            self.assertEqual(weight.b, Fraction(0))
            self.assertEqual(weight.c, Fraction(0))
            self.assertEqual(weight.d, Fraction(0))
            projections.append(abs(float(weight.a)))
        total = sum(projections)
        expected = [component / total for component in projections]
        self.assertEqual(expected[0], 0.25)
        self.assertEqual(expected[1], 0.75)
        self.assertEqual(model.feature_importances_[0], expected[0])
        self.assertEqual(model.feature_importances_[1], expected[1])
        self.assertNotIsInstance(model.feature_importances_[0], F4)
        self.assertNotIsInstance(model.feature_importances_[1], F4)

    def test_N14_theorem_proven_is_not_set_by_instance_methods(self):
        features = np.array([[0.0], [1.0]])
        labels = np.array([0, 1])
        model = exact_linear().fit(features, labels)
        self.assertIs(model.theorem_proven, False)
        with self.assertRaises(PlaneViolation):
            model.theorem_proven = True
        with self.assertRaises(PlaneViolation):
            exact_linear(theorem_proven=True)
        with self.assertRaises(PlaneViolation):
            object.__setattr__(model, "theorem_proven", True)
        model.__dict__["theorem_proven"] = True
        self.assertIs(model.theorem_proven, False)
        model.fit(features, labels)
        model.predict(features)
        model.predict_proba(features)
        model.exact_scores(features)
        model.get_params()
        model.to_artifact()
        model.kernel_commitment()
        self.assertIs(model.theorem_proven, False)
        artifact = model.to_artifact()
        artifact["theorem_proven"] = True
        loaded = type(model).from_artifact(artifact)
        self.assertIs(loaded.theorem_proven, False)
        module = ast.parse(Path(tensor_ml.__file__).read_text(encoding="utf-8"))
        proven_assignments = []
        load_proof_callers = []
        for node in module.body:
            if isinstance(node, ast.FunctionDef) and node.name == "govern":
                self.assertIn("load_proof", _attribute_names(node) + [
                    name.id for name in ast.walk(node) if isinstance(name, ast.Name)
                ])
            if isinstance(node, ast.ClassDef) and node.name == "TensorClassifier":
                for item in node.body:
                    if not isinstance(item, ast.FunctionDef):
                        continue
                    for child in ast.walk(item):
                        if (
                            isinstance(child, ast.Assign)
                            and any(
                                isinstance(target, ast.Attribute)
                                and target.attr == "_governance_state"
                                for target in child.targets
                            )
                            and isinstance(child.value, ast.Constant)
                            and child.value.value == "proven"
                        ):
                            proven_assignments.append(item.name)
            if isinstance(node, ast.FunctionDef):
                for child in ast.walk(node):
                    if isinstance(child, ast.Call) and getattr(child.func, "id", None) == "load_proof":
                        load_proof_callers.append(node.name)
        self.assertEqual(proven_assignments, ["__init__"])
        self.assertEqual(load_proof_callers, ["govern"])
        self.assertEqual(tensor_ml.govern("missing-claim").value["state"], "unproven")


if __name__ == "__main__":
    unittest.main()
