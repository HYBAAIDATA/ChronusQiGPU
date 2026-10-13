import unittest

from chronus.mining_bridge import ChronusSubstrateMiningBridge
from mining.hash_pipeline import HashPipeline


class RecordingHasher:
    backend = "test-cpu"
    device = "recording-sha256d-boundary"
    kernel_ms = 0.0
    launches = 0

    def __init__(self):
        self.seen = []

    def grind_target_batch(self, header, target, nonces):
        batch = [int(value) for value in nonces]
        self.seen.extend(batch)
        self.launches += 1
        return None, None, len(batch)


class ChronusSubstrateMiningUnitTests(unittest.TestCase):
    def test_order_is_deterministic_sealed_permutation(self):
        bridge = ChronusSubstrateMiningBridge(seed=7)
        nonces = list(range(32))
        scores = [((value * 17) % 31) / 31.0 for value in nonces]
        first, evidence = bridge.order(nonces, scores, fold_depth=1)
        second, repeated = bridge.order(nonces, scores, fold_depth=1)

        self.assertEqual(first, second)
        self.assertEqual(evidence.output_fingerprint, repeated.output_fingerprint)
        self.assertEqual(sorted(first), nonces)
        self.assertTrue(evidence.permutation_preserved)
        self.assertAlmostEqual(evidence.state_norm, 1.0, places=12)
        self.assertAlmostEqual(evidence.transformed_norm, 1.0, places=12)
        self.assertGreater(evidence.compression_ratio, 1.0)
        self.assertEqual(evidence.role, "SEARCH_OPTIMIZATION")
        self.assertEqual(evidence.execution_scope, "CPU/GPU/ASIC/SUPER_ASIC")
        self.assertFalse(evidence.consensus_authority)

    def test_invalid_input_fails_closed(self):
        bridge = ChronusSubstrateMiningBridge()
        cases = [
            ([1, 1], [0.1, 0.2]),
            ([-1, 2], [0.1, 0.2]),
            ([1, 2], [0.1]),
            ([1, 2], [0.1, float("nan")]),
        ]
        for nonces, scores in cases:
            with self.subTest(nonces=nonces, scores=scores):
                with self.assertRaises(ValueError):
                    bridge.order(nonces, scores)


class ChronusSubstrateMiningIntegrationTests(unittest.TestCase):
    def test_pipeline_hashes_complete_substrate_order(self):
        hasher = RecordingHasher()
        pipe = HashPipeline(host=object(), hasher=hasher)
        nonces = list(range(64))
        result, evidence = pipe.grind_with_chronus_substrate(
            bytes(80),
            bytes(32),
            nonces,
            fold_depth=1,
            seed=0,
        )

        self.assertEqual(result.hashes_computed, len(nonces))
        self.assertFalse(result.mining_success)
        self.assertEqual(sorted(hasher.seen), nonces)
        self.assertEqual(hasher.seen, list(dict.fromkeys(hasher.seen)))
        self.assertEqual(result.scoring_backend, "chronus-substrate")
        self.assertEqual(result.scoring_device, "phi-tensor-diffusion")
        self.assertEqual(evidence.candidate_count, len(nonces))
        self.assertTrue(evidence.permutation_preserved)


if __name__ == "__main__":
    unittest.main()