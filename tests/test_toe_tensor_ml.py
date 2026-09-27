import ast
import hashlib
import json
import subprocess
import sys
import unittest
import warnings
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from kellogg.tensor_ml import (
    F4,
    GradientBoostingClassifier,
    LGBMClassifier,
    DiagnosticValue,
    PlaneViolation,
    RandomForestClassifier,
    SimpleImputer,
    StandardScaler,
    TfidfVectorizer,
    TensorState,
    XGBClassifier,
    accuracy_score,
    apply_unitary,
    center_apply,
    center_fit,
    commit,
    exact_accuracy,
    exact_f1,
    f1_score,
    from_rat,
    load,
    merkle_root,
    partial_trace,
    plane_multiply,
    range_apply,
    range_fit,
    re_encode,
    tensor_cross_val_score,
    Unitary,
    verify,
)
import kellogg.tensor_ml as tensor_ml


class TensorMLContractTests(unittest.TestCase):
    def setUp(self):
        self.X = np.array(
            [[0.0, 0.0], [0.1, 0.2], [1.0, 1.0], [0.9, 0.8]], dtype=float
        )
        self.y = np.array([0, 0, 1, 1], dtype=int)

    def test_preprocessing_contracts_are_deterministic(self):
        imputed = SimpleImputer(strategy="median").fit_transform(
            np.array([[1.0, np.nan], [3.0, 5.0]])
        )
        self.assertEqual(imputed.tolist(), [[1.0, 5.0], [3.0, 5.0]])
        scaled = StandardScaler().fit_transform(self.X)
        np.testing.assert_allclose(scaled.mean(axis=0), [0.0, 0.0], atol=1e-12)
        center = StandardScaler().fit_exact(TensorState.from_values([[0], [1], [2], [3]]))
        self.assertFalse(center.scale_field_closed_)
        from kellogg.exact_field import sqrt_f
        with self.assertRaises(ValueError):
            sqrt_f(F4(5, 0))

    def test_text_projection_is_dense_and_repeatable(self):
        vectorizer = TfidfVectorizer(max_features=4, stop_words="english")
        first = vectorizer.fit_transform(["great work", "difficult work"]).toarray()
        second = vectorizer.transform(["great work"]).toarray()
        self.assertEqual(first.shape[1], 3)
        np.testing.assert_allclose(first[0], second[0])

    def test_all_model_contracts_bind_exact_tensor_witnesses(self):
        model_types = [
            RandomForestClassifier,
            XGBClassifier,
            LGBMClassifier,
            GradientBoostingClassifier,
        ]
        for model_type in model_types:
            with self.subTest(model_type=model_type.__name__):
                model = model_type(n_estimators=4, max_depth=3, random_state=42).fit(
                    self.X, self.y
                )
                probabilities = model.predict_proba(self.X[:2])
                self.assertEqual(probabilities.shape, (2, 2))
                self.assertEqual(model.tensor_backend, "mla1517_exact_tensor")
                self.assertFalse(model.theorem_proven)
                self.assertEqual(len(model.fit_tensor_commitment_), 64)
                self.assertEqual(len(model.last_tensor_commitments_), 2)
                self.assertGreaterEqual(f1_score(self.y, model.predict(self.X)), 0.5)

    def test_field_and_plane_guards(self):
        one = F4(1)
        sqrt_two = F4(0, 1)
        self.assertEqual(sqrt_two * sqrt_two, F4(2))
        self.assertEqual(one / one, one)
        self.assertEqual((one + sqrt_two) - sqrt_two, one)
        with self.assertRaises(PlaneViolation):
            re_encode(0.5)
        self.assertEqual(re_encode(Fraction(1, 2)), F4(Fraction(1, 2)))
        with self.assertRaises(PlaneViolation):
            plane_multiply(F4(1), DiagnosticValue(0, "test"))

    def test_commitments_are_domain_separated_and_tamper_evident(self):
        state = TensorState.from_values(self.X)
        self.assertNotEqual(commit(state, "fit"), commit(state, "predict"))
        root, proofs = merkle_root(state, "fit")
        self.assertEqual(len(root), 64)
        self.assertEqual(len(proofs), len(self.X))
        tampered_values = self.X.copy()
        tampered_values[0, 0] = 7.0
        tampered = TensorState.from_values(tampered_values)
        self.assertNotEqual(root, merkle_root(tampered, "fit")[0])

    def test_exact_metrics_and_json_persistence(self):
        predicted = np.array([0, 1, 1, 0])
        truth = np.array([0, 1, 0, 0])
        self.assertEqual(exact_accuracy(truth, predicted), from_rat(3, 4))
        self.assertEqual(accuracy_score(truth, predicted), 0.75)
        self.assertEqual(exact_f1(truth, predicted), from_rat(2, 3))
        model = RandomForestClassifier(random_state=42).fit(self.X, self.y)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "model.joblib"
            # The legacy filename is retained, but the artifact is canonical JSON.
            from kellogg.tensor_ml import dump
            dump(model, path)
            self.assertTrue(path.read_text().startswith("{"))
            restored = load(path)
            np.testing.assert_array_equal(model.predict(self.X), restored.predict(self.X))
            self.assertFalse(restored.theorem_proven)
            self.assertEqual(verify(restored).value["status"], "checked")
            stale = json.loads(path.read_text())
            stale["schema"]["toe_version"] = "3.4.0"
            path.write_text(json.dumps(stale))
            with self.assertRaises(ValueError):
                load(path)
            # The version lock covers the whole schema: substrate version
            # and declared field order must reject on load, not just the
            # tensor-family version.
            for field, bad in (("mla_version", "OTHER"), ("order", "lexicographic")):
                dump(model, path)
                drifted = json.loads(path.read_text())
                drifted["schema"][field] = bad
                path.write_text(json.dumps(drifted))
                with self.assertRaises(ValueError, msg=field):
                    load(path)

    def test_cross_validation_is_deterministic(self):
        model = RandomForestClassifier(random_state=42)
        first = tensor_cross_val_score(model, self.X, self.y, cv=2)
        second = tensor_cross_val_score(model, self.X, self.y, cv=2)
        np.testing.assert_array_equal(first, second)

    def test_cross_validation_duplicate_rows_cannot_leak(self):
        # Identical rows must stay on their assigned fold side. Resolving
        # indices via rows.index() would alias a test row onto its first
        # equal twin in the train fold — silent leakage.
        dup_X = np.array(
            [[1.0, 2.0], [1.0, 2.0], [1.0, 2.0], [1.0, 2.0],
             [3.0, 4.0], [3.0, 4.0], [3.0, 4.0], [3.0, 4.0]],
            dtype=float,
        )
        dup_y = np.array([0, 0, 0, 0, 1, 1, 1, 1], dtype=int)
        state = TensorState.from_values(dup_X)
        folds = tensor_ml.joint_for_cv(state, 2)
        covered = set()
        for fold in folds:
            self.assertEqual(len(fold.train_indices) + len(fold.test_indices), len(dup_X))
            self.assertTrue(set(fold.train_indices).isdisjoint(fold.test_indices))
            self.assertEqual(
                {i for i in fold.test_indices},
                set(range(len(dup_X))) - set(fold.train_indices),
            )
            covered.update(fold.test_indices)
        self.assertEqual(covered, set(range(len(dup_X))))
        scores = tensor_cross_val_score(
            RandomForestClassifier(random_state=42), dup_X, dup_y, cv=2
        )
        self.assertEqual(scores.shape, (2,))
        np.testing.assert_array_equal(
            scores, tensor_cross_val_score(
                RandomForestClassifier(random_state=42), dup_X, dup_y, cv=2
            )
        )

    def test_center_and_range_are_field_closed(self):
        state = TensorState.from_values([[1, 10], [3, 14]])
        centered = center_apply(state, center_fit(state))
        self.assertEqual(centered.rows[0][0], F4(-1))
        ranged = range_apply(state, range_fit(state))
        self.assertEqual(ranged.rows[0][0], F4(0))
        self.assertEqual(ranged.rows[1][1], F4(1))

    def test_tfidf_plane_is_explicit(self):
        vectorizer = TfidfVectorizer(max_features=4, stop_words="english").fit(
            ["great work", "difficult work"]
        )
        tensor_ml.TFIDF_MODE = "exact_linear"
        exact = vectorizer.transform(["great work"]).toarray()
        self.assertTrue(np.isfinite(exact).all())
        tensor_ml.TFIDF_MODE = "diagnostic_log"
        diagnostic = vectorizer.transform(["great work"]).toarray()
        self.assertTrue(np.isfinite(diagnostic).all())
        self.assertFalse(np.allclose(exact, diagnostic))
        tensor_ml.TFIDF_MODE = "exact_linear"

    def test_unitary_validation_is_cached(self):
        state = TensorState.from_values([[1, 0]])
        unitary = Unitary([[F4(1), F4(0)], [F4(0), F4(1)]])
        first = apply_unitary(unitary, state)
        second = apply_unitary(unitary, state)
        self.assertTrue(unitary._checked)
        self.assertEqual(first.rows, second.rows)
        with self.assertRaises(AttributeError):
            unitary.M = unitary.M

    def test_fold_binding_and_governance_gate(self):
        folds = tensor_ml.joint_for_cv(TensorState.from_values(self.X), 2)
        self.assertEqual(len(folds), 2)
        self.assertTrue(all(len(fold.tag) == 64 for fold in folds))
        self.assertEqual(tensor_ml.govern("missing-claim").value["state"], "unproven")
        model = tensor_ml.exact_linear().fit(self.X, self.y)
        with self.assertRaises(PlaneViolation):
            model.theorem_proven = True
        with self.assertRaises(PlaneViolation):
            tensor_ml.exact_linear(theorem_proven=False)
        with self.assertRaises(PlaneViolation):
            model.revoke_proof("unproven", actor="test-suite")
        with TemporaryDirectory() as directory:
            proof_dir = Path(directory)
            proof_path = proof_dir / "claim.json"
            blob = json.dumps({"claim_id": "claim", "checked": True}).encode()
            proof_path.write_bytes(blob)
            old_dir, old_index = tensor_ml.PROOF_DIR, tensor_ml.PROOF_INDEX
            tensor_ml.PROOF_DIR = proof_dir
            tensor_ml.PROOF_INDEX = proof_dir / "index.json"
            tensor_ml.PROOF_INDEX.write_text(
                json.dumps(
                    {
                        "claim": {
                            "path": "claim.json",
                            "sha256": hashlib.sha256(blob).hexdigest(),
                        }
                    }
                )
            )
            proven = tensor_ml.exact_linear(theorem_claim="claim")
            self.assertTrue(proven.theorem_proven)
            with self.assertRaises(PlaneViolation):
                proven.theorem_proven = False
            proven.revoke_proof("test-revocation", actor="test-suite")
            self.assertEqual(proven.governance_state, "revoked")
            self.assertEqual(proven.governance_events[-1]["actor"], "test-suite")
            with self.assertRaises(PlaneViolation):
                proven.revoke_proof("again", actor="test-suite")
            tensor_ml.PROOF_DIR, tensor_ml.PROOF_INDEX = old_dir, old_index

    def test_tampered_proof_is_loud_and_joint_prediction_is_rejected(self):
        old_dir, old_index = tensor_ml.PROOF_DIR, tensor_ml.PROOF_INDEX
        with TemporaryDirectory() as directory:
            proof_dir = Path(directory)
            proof_path = proof_dir / "claim.json"
            proof_path.write_text(json.dumps({"claim_id": "claim", "checked": True}))
            tensor_ml.PROOF_DIR = proof_dir
            tensor_ml.PROOF_INDEX = proof_dir / "index.json"
            tensor_ml.PROOF_INDEX.write_text(
                json.dumps({"claim": {"path": "claim.json", "sha256": "0" * 64}})
            )
            with self.assertRaises(tensor_ml.ProofTamperedError):
                tensor_ml.govern("claim")
        tensor_ml.PROOF_DIR, tensor_ml.PROOF_INDEX = old_dir, old_index

        model = tensor_ml.exact_linear().fit(self.X, self.y)
        joint_state = tensor_ml.joint(
            TensorState.from_values([[0, 0]]), TensorState.from_values([[1, 1]])
        )
        with self.assertRaises(ValueError):
            partial_trace(TensorState.from_values([[0, 1]]), [0])
        with self.assertRaises(MemoryError):
            partial_trace(joint_state, [0], max_dim=1)
        with self.assertRaises(PlaneViolation):
            model.predict(joint_state)
        # Unfitted prediction must be a clear domain error, not a leaked
        # AttributeError on an internal attribute.
        with self.assertRaises(ValueError):
            RandomForestClassifier().predict(self.X)

    def test_measure_pvm_threshold_is_bounded(self):
        from kellogg.quantum_tensor import QuantumState

        state = QuantumState.from_real_vector([1.0, 1.0])
        for bad in (-0.1, 1.0, 2.5):
            with self.assertRaises(ValueError, msg=f"seed={bad}"):
                state.measure_pvm(random_seed=bad)
        outcome, prob, collapsed = state.measure_pvm(random_seed=0.9)
        self.assertIn(outcome, (0, 1))
        self.assertAlmostEqual(prob, 0.5)

    def test_training_module_cannot_import_field_sqrt(self):
        tree = ast.parse(Path(tensor_ml.__file__).read_text(encoding="utf-8"))
        forbidden = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.endswith("exact_field")
        ]
        self.assertEqual(forbidden, [])
        self.assertNotIn("sqrt_f", {alias.name for node in ast.walk(tree)
                                    if isinstance(node, (ast.Import, ast.ImportFrom))
                                    for alias in node.names})
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; import kellogg.tensor_ml as m; "
                "assert 'sqrt_f' not in dir(m); "
                "assert 'kellogg.exact_field' not in sys.modules; "
                "assert 'toe.exact_field' not in sys.modules",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)

    def test_legacy_fit_names_are_exactly_equivalent(self):
        fixtures = [
            (np.arange(6).reshape(3, 2), np.array([0, 1, 0])),
            (np.arange(20).reshape(5, 4) / 10.0, np.array([0, 1, 0, 1, 0])),
            (np.arange(15, dtype=np.float32).reshape(5, 3), np.array([1, 0, 1, 0, 1])),
        ]
        for X, y in fixtures:
            canonical = tensor_ml.fit("exact_linear", X, y)
            for name in ("rf", "xgb", "lgbm", "gb"):
                with self.subTest(name=name, shape=X.shape, dtype=X.dtype):
                    legacy = tensor_ml.fit(name, X, y)
                    self.assertEqual(legacy.model_family, tensor_ml.CANONICAL)
                    self.assertEqual(legacy.weights_exact_, canonical.weights_exact_)
                    self.assertEqual(legacy.bias_exact_, canonical.bias_exact_)
                    np.testing.assert_array_equal(legacy.predict(X), canonical.predict(X))

    def test_legacy_names_warn_and_collapse(self):
        tensor_ml._warned_aliases.clear()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            legacy = tensor_ml.rf(random_state=42)
        self.assertTrue(any(item.category is DeprecationWarning for item in caught))
        self.assertEqual(legacy.model_family, tensor_ml.CANONICAL)


if __name__ == "__main__":
    unittest.main()
