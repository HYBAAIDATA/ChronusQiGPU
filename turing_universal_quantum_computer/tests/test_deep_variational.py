"""Tests for the bounded deep multi-angle VQC extension."""
import unittest

import numpy as np

from turing_universal_quantum_computer.deep_variational import (
    FisherNaturalGradientTrainer,
    LayeredVariationalAnsatz,
)
from turing_universal_quantum_computer.midas_vqc import (
    MidasPhiVQCRanker,
    VQCConfig,
)


class DeepVariationalTests(unittest.TestCase):
    def test_reuses_midas_graph_and_has_384_parameters(self):
        ranker = MidasPhiVQCRanker(VQCConfig(seed=7))
        ansatz = LayeredVariationalAnsatz.from_midas_ranker(ranker)
        self.assertEqual(ansatz.parameter_count, 384)
        np.testing.assert_array_equal(ansatz.adjacency, ranker.adjacency)

    def test_evolution_preserves_norm(self):
        ranker = MidasPhiVQCRanker(VQCConfig(seed=3))
        ansatz = LayeredVariationalAnsatz.from_midas_ranker(ranker)
        rng = np.random.default_rng(3)
        state = ansatz.evolve(
            np.full(32, 1.0 / 32.0),
            rng.uniform(0.0, 1.0, 32),
            0.1 * rng.standard_normal((4, 32, 3)),
        )
        self.assertAlmostEqual(float(np.linalg.norm(state)), 1.0, places=12)

    def test_wrong_parameter_shape_fails_closed(self):
        adjacency = np.ones((4, 4)) - np.eye(4)
        ansatz = LayeredVariationalAnsatz(adjacency, layers=1)
        with self.assertRaises(ValueError):
            ansatz.evolve(
                np.full(4, 0.25),
                np.ones(4),
                np.zeros((2, 4, 3)),
            )

    def test_training_is_non_increasing_and_audited(self):
        adjacency = np.array(
            [
                [0, 1, 0, 1],
                [1, 0, 1, 0],
                [0, 1, 0, 1],
                [1, 0, 1, 0],
            ],
            dtype=np.float64,
        )
        ansatz = LayeredVariationalAnsatz(adjacency, layers=1)
        trainer = FisherNaturalGradientTrainer(ansatz, learning_rate=0.08)
        weights = np.array([0.1, 0.4, 0.7, 1.0])
        objective = -np.diag(weights) - 0.2 * ansatz.mixer
        result = trainer.train(
            np.full(4, 0.25),
            weights,
            objective,
            steps=5,
            seed=11,
        )
        self.assertTrue(
            all(
                next_loss <= loss + 1e-12
                for loss, next_loss in zip(
                    result.loss_curve,
                    result.loss_curve[1:],
                )
            )
        )
        self.assertLessEqual(result.energy, result.loss_curve[0] + 1e-12)
        self.assertEqual(result.parameters.shape, (1, 4, 3))
        self.assertAlmostEqual(float(result.distribution.sum()), 1.0, places=12)
        self.assertFalse(result.state_audit["tensor_compression_claimed"])
        self.assertFalse(result.state_audit["consensus_authority"])


if __name__ == "__main__":
    unittest.main()
