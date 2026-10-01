"""Tests for the ported VQC-for-phi-Grover variational circuit."""

import math
import unittest

import numpy as np

from turing_universal_quantum_computer.variational import (
    NUM_FACES,
    PHI,
    VQCConfig,
    VQCError,
    VQCPhiGroverIntegration,
    VQCTrainingDataGenerator,
    VariationalQuantumCircuit,
    demonstrate_vqc,
)


def _header(nbits="1d00ffff", **overrides):
    header = {
        "version": "1",
        "prev_hash": "0" * 64,
        "merkle_root": "0" * 64,
        "ntime": "0",
        "nbits": nbits,
    }
    header.update(overrides)
    return header


class VQCCircuitTests(unittest.TestCase):
    def test_parameter_shape_and_phi_scaling(self):
        vqc = VariationalQuantumCircuit(VQCConfig())
        self.assertEqual(vqc.theta.shape, (4, NUM_FACES, 3))
        self.assertLessEqual(np.abs(vqc.theta).max(), math.pi * PHI)

    def test_m32_adjacency_is_symmetric_and_phi_connected(self):
        vqc = VariationalQuantumCircuit(VQCConfig())
        adj = vqc.M_32_adjacency
        np.testing.assert_array_equal(adj, adj.T)
        self.assertTrue(vqc._phi_connected(0, 1))
        self.assertFalse(vqc._phi_connected(0, 3))
        degree = np.diag(vqc.M_32_laplacian)
        np.testing.assert_allclose(degree, adj.sum(axis=1))

    def test_forward_distribution_sums_to_one(self):
        vqc = VariationalQuantumCircuit(VQCConfig())
        result = vqc.forward(_header())
        self.assertAlmostEqual(float(result["probabilities"].sum()), 1.0)
        self.assertIn(result["nonce"], result["candidates"])
        self.assertEqual(len(result["top_nonces"]), 5)
        self.assertGreater(result["confidence"], 0.0)

    def test_parameter_shift_gradient_shape(self):
        vqc = VariationalQuantumCircuit(VQCConfig())
        gradient = vqc._quantum_natural_gradient(_header(), target_nonce=7)
        self.assertEqual(gradient.shape, vqc.theta.shape)
        self.assertTrue(np.all(np.isfinite(gradient)))

    def test_train_records_history_and_best_params(self):
        vqc = VariationalQuantumCircuit(VQCConfig())
        generator = VQCTrainingDataGenerator()
        data = generator.generate_from_blocks(
            [{"header": _header(ntime=str(i)), "nonce": i} for i in range(4)]
        )
        result = vqc.train(data, epochs=1, batch_size=2)
        self.assertEqual(len(result["loss_history"]), 1)
        self.assertIsNotNone(vqc.best_params)
        self.assertEqual(result["best_loss"], min(result["loss_history"]))

    def test_config_validation(self):
        with self.assertRaises(VQCError):
            VariationalQuantumCircuit(VQCConfig(num_layers=0))


class VQCIntegrationTests(unittest.TestCase):
    def test_verified_path_when_target_is_huge(self):
        # nbits 0x24ffffff -> exponent 36 -> target >> 2^256: any nonce passes
        vqc = VariationalQuantumCircuit(VQCConfig())
        integration = VQCPhiGroverIntegration(vqc)
        result = integration.mine_block(_header(nbits="24ffffff"))
        self.assertTrue(result["valid"])
        self.assertEqual(result["method"], "vqc")
        self.assertEqual(integration.performance["total_predictions"], 1)

    def test_strict_target_falls_back_then_reports(self):
        # nbits 0x01010000 -> target 0 -> nothing verifies
        vqc = VariationalQuantumCircuit(VQCConfig(nonce_window=256))
        integration = VQCPhiGroverIntegration(vqc)
        result = integration.mine_block(_header(nbits="01010000"))
        self.assertFalse(result["valid"])
        self.assertEqual(result["method"], "vqc_unverified")

    def test_demonstrate_vqc_end_to_end(self):
        results = demonstrate_vqc()
        for key in ("vqc", "training", "prediction", "integration"):
            self.assertIn(key, results)


if __name__ == "__main__":
    unittest.main()
