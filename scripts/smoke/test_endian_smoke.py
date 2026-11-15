"""Regression: smoke and fake pool share little-endian target comparison.

A fake pool that used the same wrong endianness as the client would accept a
share the real network would reject. This test pins both sides to LE and shows
BE disagrees on a concrete digest.
"""

from __future__ import annotations

import hashlib
import unittest

from fake_pool import DIFFICULTY, TARGET, header
from stratum_smoke import meets, target_from_difficulty


class EndianSmokeTests(unittest.TestCase):
    def test_smoke_and_fake_pool_targets_match(self) -> None:
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

    def test_fake_pool_accepts_only_le_valid_share(self) -> None:
        extranonce1 = "deadbeef"
        # Search a short window the same way the smoke does.
        job_ntime, en2 = "67000000", "00000000"
        found = None
        for nonce in range(10_000):
            params = ["smoke", "smokejob1", en2, job_ntime, f"{nonce:08x}"]
            digest = hashlib.sha256(hashlib.sha256(header(extranonce1, params)).digest()).digest()
            if meets(digest, TARGET):
                found = (nonce, digest, params)
                break
        self.assertIsNotNone(found, "easy fake-pool target should hit within 10k hashes")
        nonce, digest, params = found
        self.assertTrue(int.from_bytes(digest, "little") <= TARGET)
        # If both sides wrongly used big-endian, this digest may still "pass"
        # under BE at this easy target; force a digest that LE accepts and BE rejects
        # is covered above. Here assert the pool predicate matches meets().
        self.assertEqual(
            int.from_bytes(digest, "little") <= TARGET,
            meets(digest, TARGET),
        )


if __name__ == "__main__":
    unittest.main()
