"""Regression: smoke and fake pool share little-endian target comparison.

A fake pool that used the same wrong endianness as the client would accept a
share the real network would reject. This test pins both sides to LE and shows
BE disagrees on a concrete digest.
"""

from __future__ import annotations

import hashlib
import unittest

from fake_pool import DIFF1, DIFFICULTY, TARGET, header
from stratum_smoke import meets, target_from_difficulty


class EndianSmokeTests(unittest.TestCase):
    def test_default_pool_is_bitcoin_difficulty_1(self) -> None:
        self.assertEqual(DIFFICULTY, 1)
        self.assertEqual(TARGET, DIFF1)
        self.assertEqual(target_from_difficulty(DIFFICULTY), TARGET)

    def test_canonical_comparison_is_little_endian(self) -> None:
        # High byte zero → small as LE, large as BE (common-mode failure mode).
        digest = bytes([0xFF] * 31 + [0x00])
        threshold = 1 << 255
        le = int.from_bytes(digest, "little") <= threshold
        be = int.from_bytes(digest, "big") <= threshold
        self.assertNotEqual(le, be)
        self.assertEqual(meets(digest, threshold), le)
        self.assertTrue(le)
        self.assertFalse(be)

    def test_fake_pool_predicate_matches_meets(self) -> None:
        extranonce1 = "deadbeef"
        params = ["smoke", "smokejob1", "00000000", "67000000", "00000000"]
        digest = hashlib.sha256(hashlib.sha256(header(extranonce1, params)).digest()).digest()
        self.assertEqual(
            int.from_bytes(digest, "little") <= TARGET,
            meets(digest, TARGET),
        )


if __name__ == "__main__":
    unittest.main()
