"""Property tests pinning two structural findings about the mining path.

1. The miner's Zeckendorf traversal is linear by construction:
   ``zeckendorf_increment`` adds exactly one (its docstring says so; the
   rewrite identities are value-preserving normal forms of +1), so the
   candidate sequence visited by ``GeometricGaloisMiner.solve_header_range``
   equals nonce_start, nonce_start + 1, ... for the whole scan window. Any
   "geometric ordering" claim about that traversal is therefore void.

2. The implemented phi-resonance filter in ``chronos_gpu`` is a monotone
   no-op: with the identity placeholder kernels, the fused score is a strictly
   increasing function of the nonce, so the >= 128 threshold admits every
   nonce except 0.

Both tests are hermetic: no network, no mining, no timing assertions.
"""
import unittest

from chronus.acceleration import chronos_gpu
from chronus.execution.structural import (
    zeckendorf_decode,
    zeckendorf_encode,
    zeckendorf_increment,
)


class ZeckendorfTraversalIsLinearTest(unittest.TestCase):
    def test_traversal_equals_linear_from_zero(self) -> None:
        z = zeckendorf_encode(0)
        for expected in range(20_000):
            self.assertEqual(zeckendorf_decode(z), expected)
            z = zeckendorf_increment(z)

    def test_traversal_equals_linear_from_high_seed(self) -> None:
        start = 4_000_000_000
        z = zeckendorf_encode(start)
        for offset in range(20_000):
            self.assertEqual(zeckendorf_decode(z), start + offset)
            z = zeckendorf_increment(z)

    def test_traversal_stays_within_32_bits_to_the_end(self) -> None:
        start = (1 << 32) - 5_000
        z = zeckendorf_encode(start)
        for _ in range(4_999):
            value = zeckendorf_decode(z)
            self.assertLess(value, 1 << 32)
            z = zeckendorf_increment(z)
        self.assertEqual(zeckendorf_decode(z), (1 << 32) - 1)


class ResonanceFilterIsNoopTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import numpy as np

        cls.np = np

    def _score(self, nonce: int) -> float:
        arr = self.np.array([nonce], dtype=self.np.int64)
        alignments = chronos_gpu.batch_align_gpu(chronos_gpu.batch_embed_gpu(arr))
        ym = chronos_gpu.batch_yang_mills_gpu(arr)
        qw = chronos_gpu.continuous_time_quantum_walk_gpu(arr)
        return float(chronos_gpu.compute_phi_resonance_fused(alignments, ym, qw)[0])

    def test_score_is_monotone_in_nonce(self) -> None:
        scores = [self._score(n) for n in (0, 1, 2, 10, 1_000, 10**6, 2**32 - 1)]
        self.assertEqual(scores, sorted(scores))

    def test_threshold_admits_every_nonce_except_zero(self) -> None:
        self.assertLess(self._score(0), 128.0)
        for nonce in (1, 2, 3, 4_096, 65_535, 2**31, 2**32 - 1):
            self.assertGreaterEqual(self._score(nonce), 128.0)


if __name__ == "__main__":
    unittest.main()
