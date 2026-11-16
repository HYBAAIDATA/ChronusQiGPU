"""Historical QuantumStateEngine alias tests: classical predictive numerical methods; no device execution."""

import unittest
import pytest

pytestmark = pytest.mark.simulated  # seeded synthetic training data
import tempfile
import shutil
import os
import numpy as np
from chronus.intelligence import QuantumStateEngine, PredictiveEngine


class TestQuantumStateEngine(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="chronus_qse_test_")
        self.engine = QuantumStateEngine(config={
            "model_names": ["rf", "gb"],
            "model_dir": self.test_dir,
            "n_estimators": 5,
            "max_depth": 3,
            "feature_dim": 6,
            "use_random_baseline": True,
            "allow_missing_boosters": True,
        })

    def tearDown(self):
        if hasattr(self, "test_dir") and os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_alias(self):
        self.assertIs(QuantumStateEngine, PredictiveEngine)
        self.assertIsInstance(self.engine, PredictiveEngine)

    def test_to_quantum_state_normalization(self):
        x = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
        psi = self.engine.to_quantum_state(x)
        self.assertEqual(len(psi), 6)
        self.assertTrue(np.iscomplexobj(psi))
        norm = np.linalg.norm(psi)
        self.assertAlmostEqual(norm, 1.0, places=6)
        # Inner product <psi|psi> == 1.0
        inner_prod = np.vdot(psi, psi)
        self.assertAlmostEqual(np.real(inner_prod), 1.0, places=6)
        self.assertAlmostEqual(np.imag(inner_prod), 0.0, places=6)

    def test_to_quantum_state_zero_vector(self):
        x_zero = np.zeros(6)
        psi = self.engine.to_quantum_state(x_zero)
        self.assertEqual(len(psi), 6)
        norm = np.linalg.norm(psi)
        self.assertAlmostEqual(norm, 1.0, places=6)

    def test_density_matrix_properties(self):
        x = np.array([0.5, -1.2, 3.4, 0.0, 2.1, -0.7])
        psi = self.engine.to_quantum_state(x)
        rho = self.engine.compute_density_matrix(psi)
        
        self.assertEqual(rho.shape, (6, 6))
        # 1. Tr(rho) == 1.0
        trace = np.trace(rho)
        self.assertAlmostEqual(np.real(trace), 1.0, places=6)
        self.assertAlmostEqual(np.imag(trace), 0.0, places=6)
        
        # 2. rho^dagger == rho (Hermitian)
        self.assertTrue(np.allclose(rho, rho.conj().T, atol=1e-6))
        
        # 3. rho >= 0 (positive semi-definite)
        eigvals = np.linalg.eigvalsh(rho)
        self.assertTrue(np.all(eigvals >= -1e-6))
        
        # 4. Pure state: rho^2 == rho
        rho_sq = rho @ rho
        self.assertTrue(np.allclose(rho, rho_sq, atol=1e-6))

    def test_von_neumann_entropy(self):
        # Pure state has zero von Neumann entropy
        x = np.array([2.0, 1.0, 0.5, -0.5, 1.5, 0.0])
        psi = self.engine.to_quantum_state(x)
        rho = self.engine.compute_density_matrix(psi)
        entropy = self.engine.compute_von_neumann_entropy(rho)
        self.assertAlmostEqual(entropy, 0.0, places=5)

        # Maximally mixed state rho = (1/d) * I has entropy log2(d)
        d = 6
        rho_mixed = np.eye(d, dtype=complex) / d
        mixed_entropy = self.engine.compute_von_neumann_entropy(rho_mixed)
        self.assertAlmostEqual(mixed_entropy, np.log2(d), places=5)

    def test_quantum_born_measurement(self):
        x = np.array([1.0, 0.0, 2.0, 0.0, 1.0, 0.0])
        psi = self.engine.to_quantum_state(x)
        rho = self.engine.compute_density_matrix(psi)
        
        # Default computational basis
        probs = self.engine.quantum_born_measurement(rho)
        self.assertEqual(len(probs), 6)
        self.assertTrue(np.all(probs >= 0.0))
        self.assertAlmostEqual(np.sum(probs), 1.0, places=6)

        # Custom orthonormal basis
        e0 = np.array([1, 0, 0, 0, 0, 0], dtype=complex)
        e1 = np.array([0, 1, 0, 0, 0, 0], dtype=complex)
        custom_probs = self.engine.quantum_born_measurement(rho, basis_states=[e0, e1])
        self.assertEqual(len(custom_probs), 2)
        self.assertAlmostEqual(np.sum(custom_probs), 1.0, places=6)

    def test_compute_quantum_fidelity(self):
        x1 = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
        x2 = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
        psi1 = self.engine.to_quantum_state(x1)
        psi2 = self.engine.to_quantum_state(x2)
        
        # Self-fidelity == 1.0
        fid_self = self.engine.compute_quantum_fidelity(psi1, psi2)
        self.assertAlmostEqual(fid_self, 1.0, places=6)

        # Different states: fidelity in [0, 1]
        x3 = np.array([-5.0, 0.0, 1.0, 2.0, -1.0, 3.0])
        psi3 = self.engine.to_quantum_state(x3)
        fid_diff = self.engine.compute_quantum_fidelity(psi1, psi3)
        self.assertTrue(0.0 <= fid_diff <= 1.0)

    def test_unitary_hamiltonian_evolution(self):
        x = np.array([1.0, 0.5, -0.2, 0.8, -1.0, 0.3])
        psi0 = self.engine.to_quantum_state(x)
        
        # Construct random Hermitian Hamiltonian H = H^dagger
        rng = np.random.default_rng(42)
        A = rng.normal(size=(6, 6)) + 1j * rng.normal(size=(6, 6))
        H = 0.5 * (A + A.conj().T)
        
        # Evolve under time t = 2.5
        psi_t = self.engine.evolve_quantum_state(psi0, H, time_delta=2.5, hbar=1.0)
        self.assertEqual(len(psi_t), 6)
        
        # Norm is strictly preserved under unitary evolution: ||psi(t)|| == 1.0
        norm_t = np.linalg.norm(psi_t)
        self.assertAlmostEqual(norm_t, 1.0, places=6)
        
        # Time reversal: evolve by -t brings state back to psi0
        psi_back = self.engine.evolve_quantum_state(psi_t, H, time_delta=-2.5, hbar=1.0)
        fid_rev = self.engine.compute_quantum_fidelity(psi0, psi_back)
        self.assertAlmostEqual(fid_rev, 1.0, places=5)

    def test_predict_proba_and_evaluate(self):
        rng = np.random.default_rng(42)
        X = rng.normal(size=(20, 6))
        y = rng.integers(0, 2, size=20)
        
        probs = self.engine.predict_proba(X)
        self.assertEqual(probs.shape, (20, 2))
        self.assertTrue(np.allclose(np.sum(probs, axis=1), 1.0))
        
        preds = self.engine.predict(X, threshold=0.5)
        self.assertEqual(len(preds), 20)
        self.assertTrue(set(preds).issubset({0, 1}))
        
        metrics = self.engine.evaluate(X, y)
        self.assertIn("accuracy", metrics)
        self.assertIn("precision", metrics)
        self.assertIn("recall", metrics)
        self.assertIn("f1_score", metrics)
        for val in metrics.values():
            self.assertTrue(0.0 <= val <= 1.0)


if __name__ == "__main__":
    unittest.main()
