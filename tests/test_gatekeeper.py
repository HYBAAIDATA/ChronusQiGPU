import unittest
from fractions import Fraction
from chronus.stratum.gatekeeper import (
    LocalPreSubmitGatekeeper,
    compute_share_target_exact,
    decode_nbits_target,
    DropReason,
    TRUEDIFF1_TARGET,
)


class TestGatekeeper(unittest.TestCase):
    def test_compute_share_target_exact(self):
        target1 = compute_share_target_exact(1)
        target1024 = compute_share_target_exact(1024)
        self.assertEqual(target1, TRUEDIFF1_TARGET)
        self.assertEqual(target1024, target1 // 1024)

        with self.assertRaises(ValueError):
            compute_share_target_exact(0)
        with self.assertRaises(ValueError):
            compute_share_target_exact(-1)

    def test_decode_nbits_target(self):
        target = decode_nbits_target("1d00ffff")
        self.assertEqual(target, 0x00000000FFFF0000000000000000000000000000000000000000000000000000)

        # Regtest difficulty 0x207fffff
        target_regtest = decode_nbits_target("207fffff")
        self.assertEqual(target_regtest, 0x7FFFFF0000000000000000000000000000000000000000000000000000000000)

        # Small exponent <= 3
        target_small = decode_nbits_target(0x0200ffff)
        self.assertGreaterEqual(target_small, 0)

    def test_gatekeeper_en2_width_reject(self):
        gk = LocalPreSubmitGatekeeper()
        valid, reason, _, _, _, _ = gk.verify_candidate(
            job_data={"prevhash_hex": "00"*32, "coinb1_hex": "01", "coinb2_hex": "02", "merkle_branches": [], "version_hex": "20000000", "nbits_hex": "1d00ffff"},
            extranonce1_hex="a45b7889",
            extranonce2_hex="00", # Wrong size! Expected 4 bytes = 8 hex chars
            extranonce2_size=4,
            ntime_hex="60000000",
            nonce_int=1,
            version_bits_hex="00000000",
            pool_mask_hex="1fffe000",
            current_difficulty=Fraction(1)
        )
        self.assertFalse(valid)
        self.assertEqual(reason, DropReason.EN2_WIDTH)
        self.assertEqual(gk.reject_counts[DropReason.EN2_WIDTH], 1)

    def test_gatekeeper_version_mask_reject(self):
        gk = LocalPreSubmitGatekeeper()
        valid, reason, _, _, _, _ = gk.verify_candidate(
            job_data={"prevhash_hex": "00"*32, "coinb1_hex": "01", "coinb2_hex": "02", "merkle_branches": [], "version_hex": "20000000", "nbits_hex": "1d00ffff"},
            extranonce1_hex="a45b7889",
            extranonce2_hex="00000001",
            extranonce2_size=4,
            ntime_hex="60000000",
            nonce_int=1,
            version_bits_hex="ffffffff", # Violates mask 0x1fffe000!
            pool_mask_hex="1fffe000",
            current_difficulty=Fraction(1)
        )
        self.assertFalse(valid)
        self.assertEqual(reason, DropReason.VERSION_MASK)

    def test_gatekeeper_bad_hex_reject(self):
        gk = LocalPreSubmitGatekeeper()
        valid, reason, _, _, _, _ = gk.verify_candidate(
            job_data={"prevhash_hex": "not_hex", "coinb1_hex": "01", "coinb2_hex": "02", "merkle_branches": [], "version_hex": "20000000", "nbits_hex": "1d00ffff"},
            extranonce1_hex="a45b7889",
            extranonce2_hex="00000001",
            extranonce2_size=4,
            ntime_hex="60000000",
            nonce_int=1,
            version_bits_hex="00000000",
            pool_mask_hex="1fffe000",
            current_difficulty=Fraction(1)
        )
        self.assertFalse(valid)
        self.assertEqual(reason, DropReason.BAD_HEX)

    def test_gatekeeper_above_target_reject(self):
        gk = LocalPreSubmitGatekeeper()
        valid, reason, _, _, _, _ = gk.verify_candidate(
            job_data={"prevhash_hex": "00"*32, "coinb1_hex": "01", "coinb2_hex": "02", "merkle_branches": [], "version_hex": "20000000", "nbits_hex": "1d00ffff"},
            extranonce1_hex="a45b7889",
            extranonce2_hex="00000001",
            extranonce2_size=4,
            ntime_hex="60000000",
            nonce_int=1,
            version_bits_hex="00000000",
            pool_mask_hex="1fffe000",
            current_difficulty=Fraction(10**12) # Extremely high difficulty -> target ~0 -> hash > target
        )
        self.assertFalse(valid)
        self.assertEqual(reason, DropReason.ABOVE_TARGET)

    def test_gatekeeper_stale_and_submitted_shares_rate(self):
        gk = LocalPreSubmitGatekeeper()
        self.assertEqual(gk.stale_share_rate, 0.0)

        # Record 100 submitted shares and 2 stale shares
        for _ in range(100):
            gk.record_submitted_share()
        gk.record_stale_share()
        gk.record_stale_share()
        gk.record_duplicate_share()

        self.assertEqual(gk.submitted_shares_count, 100)
        self.assertEqual(gk.stale_shares_count, 2)
        self.assertEqual(gk.stale_share_rate, 2.0)
        self.assertEqual(gk.reject_counts[DropReason.STALE_JOB], 2)
        self.assertEqual(gk.reject_counts[DropReason.DUP], 1)


if __name__ == "__main__":
    unittest.main()
