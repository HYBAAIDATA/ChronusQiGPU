import unittest
import numpy as np

from turing.applications.vqc_fold import ValidationError
from turing.applications.vqc_grover import (
    PhiGroverVQC, VQCConfig, VQCPhiGroverIntegration, VQCTrainingDataGenerator,
)


def easy_header(seed=0):
    return {
        'version': 1,
        'prev_hash': f'{seed:064x}',
        'merkle_root': f'{seed + 1:064x}',
        'ntime': 1700000000 + seed,
        'nbits': '207fffff',
    }


class TestPhiGroverVQC(unittest.TestCase):
    def test_topology_contract(self):
        vqc = PhiGroverVQC()
        self.assertEqual(vqc.adjacency.shape, (32, 32))
        self.assertTrue(np.allclose(vqc.adjacency, vqc.adjacency.T))
        self.assertTrue(np.allclose(np.diag(vqc.adjacency), 0))
        self.assertTrue(np.allclose(vqc.laplacian.sum(axis=1), 0))

    def test_private_topology_injection(self):
        adjacency = np.zeros((32, 32)); adjacency[0, 1] = adjacency[1, 0] = 1
        vqc = PhiGroverVQC(adjacency=adjacency)
        self.assertEqual(vqc.adjacency.sum(), 2)
        with self.assertRaises(ValidationError): PhiGroverVQC(adjacency=np.ones((31, 31)))

    def test_feature_hook(self):
        vqc = PhiGroverVQC(feature_hook=lambda _: np.arange(32))
        self.assertEqual(vqc.extract_features(easy_header()).shape, (32,))
        self.assertTrue(np.all(np.isfinite(vqc.encode_input(easy_header()))))

    def test_forward_is_bounded_without_dense_nonce_space(self):
        vqc = PhiGroverVQC(VQCConfig(candidate_count=128))
        probs = vqc.bit_probabilities(easy_header())
        self.assertEqual(probs.shape, (32,))
        self.assertTrue(np.all((probs > 0) & (probs < 1)))
        ranked = vqc.rank_candidates(easy_header())
        self.assertLessEqual(len(ranked['candidates']), 128)
        self.assertTrue(all(0 <= n <= 0xffffffff for n in ranked['candidates']))

    def test_nonce_bit_roundtrip(self):
        values = [0, 1, 0x12345678, 0xffffffff]
        for value in values:
            bits = PhiGroverVQC.nonce_to_bits(value)[None, :]
            self.assertEqual(int(PhiGroverVQC.bits_to_nonces(bits)[0]), value)

    def test_training_reduces_repeated_sample_loss(self):
        vqc = PhiGroverVQC(VQCConfig(learning_rate=0.08, candidate_count=64))
        header = easy_header(2); nonce = 0x12345678
        target = vqc.nonce_to_bits(nonce)
        before = vqc.binary_cross_entropy(vqc.bit_probabilities(header, use_best=False), target)
        result = vqc.train([{'header': header, 'nonce': nonce}], epochs=80, batch_size=1)
        after = vqc.binary_cross_entropy(vqc.bit_probabilities(header), target)
        self.assertLess(after, before)
        self.assertLess(result['best_loss'], before)

    def test_exact_nonce_verifier(self):
        header = easy_header(3)
        found = next(n for n in range(1000) if PhiGroverVQC.verify_nonce(header, n))
        self.assertTrue(PhiGroverVQC.verify_nonce(header, found))

    def test_mining_never_false_reports_success(self):
        vqc = PhiGroverVQC(VQCConfig(candidate_count=32))
        integration = VQCPhiGroverIntegration(vqc)
        result = integration.mine_block(easy_header(4), max_fallback_checks=1000)
        self.assertTrue(result['valid'])
        self.assertTrue(vqc.verify_nonce(easy_header(4), result['nonce']))

    def test_invalid_fallback_is_rejected(self):
        vqc = PhiGroverVQC(VQCConfig(candidate_count=1))
        hard = easy_header(5); hard['nbits'] = '01003456'
        integration = VQCPhiGroverIntegration(vqc, fallback=lambda header, budget: 0)
        result = integration.mine_block(hard, max_fallback_checks=0)
        self.assertFalse(result['valid'])
        self.assertIsNone(result['nonce'])

    def test_quantum_skeleton_runs_on_machine(self):
        result = PhiGroverVQC().run_quantum_skeleton(shots=8)
        self.assertEqual(result['logical_qubits'], 32)
        self.assertGreater(result['gates'], 32)
        self.assertLess(result['checkpoint_error'], 1e-12)

    def test_training_data_generator_marks_validity(self):
        header = easy_header(6)
        nonce = next(n for n in range(1000) if PhiGroverVQC.verify_nonce(header, n))
        data = VQCTrainingDataGenerator().generate_from_blocks([{'header': header, 'nonce': nonce}])
        self.assertTrue(data[0]['valid'])


if __name__ == '__main__':
    unittest.main()
