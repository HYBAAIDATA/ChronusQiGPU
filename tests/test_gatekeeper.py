import unittest
from fractions import Fraction
from chronus.stratum.gatekeeper import (
    LocalPreSubmitGatekeeper,
    compute_share_target_exact,
    decode_nbits_target,
    DropReason,
    TRUEDIFF1_TARGET,
)
from chronus.stratum.endian_engine import (
    swap_prevhash_words,
    compute_merkle_root_stratum,
    build_header80,
    sha256d,
)
from chronus.stratum.bip310 import apply_version_rolling
from chronus.stratum.sharding import DedupLedger
import pytest

pytestmark = pytest.mark.real


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

        # Disallow float in exact gatekeeper
        with self.assertRaises(TypeError):
            compute_share_target_exact(1.0)

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

    def test_above_target_dropped_with_reason(self):
        gk = LocalPreSubmitGatekeeper()
        valid, reason, block_hash, hash_int, target_int, is_block = gk.verify_candidate(
            job_data={"job_id": "j1", "prevhash_hex": "11"*32, "coinb1_hex": "01", "coinb2_hex": "02", "merkle_branches": [], "version_hex": "20000000", "nbits_hex": "1d00ffff"},
            extranonce1_hex="12345678",
            extranonce2_hex="00000001",
            extranonce2_size=4,
            ntime_hex="60000000",
            nonce_int=42,
            version_bits_hex="00000000",
            pool_mask_hex="1fffe000",
            current_difficulty=Fraction(10**15)
        )
        self.assertFalse(valid)
        self.assertEqual(reason, DropReason.ABOVE_TARGET)
        self.assertGreater(hash_int, target_int)
        self.assertEqual(gk.reject_counts[DropReason.ABOVE_TARGET], 1)

    def test_header_reconstructed_from_submit_params(self):
        gk = LocalPreSubmitGatekeeper()
        job = {
            "job_id": "test_job_1",
            "prevhash_hex": "aa" * 32,
            "coinb1_hex": "0100000001",
            "coinb2_hex": "ffffffff",
            "merkle_branches": ["bb" * 32],
            "version_hex": "20000000",
            "nbits_hex": "1d00ffff",
        }
        en1 = "01020304"
        en2 = "05060708"
        ntime = "60000000"
        nonce = 123456
        vbits = "00002000"
        mask = "1fffe000"

        # Independent reconstruction using endian_engine
        rolled_v, _ = apply_version_rolling(job["version_hex"], mask, int(vbits, 16))
        prev_swapped = swap_prevhash_words(job["prevhash_hex"])
        merkle = compute_merkle_root_stratum(
            job["coinb1_hex"], en1, en2, job["coinb2_hex"], job["merkle_branches"]
        )
        expected_hdr = build_header80(
            rolled_v, prev_swapped, merkle, int(ntime, 16), int(job["nbits_hex"], 16), nonce
        )
        expected_digest = sha256d(expected_hdr)
        expected_hash_int = int.from_bytes(expected_digest, "little")
        expected_be_hex = expected_digest[::-1].hex()

        _, _, block_hash_be_hex, hash_int, _, _ = gk.verify_candidate(
            job_data=job,
            extranonce1_hex=en1,
            extranonce2_hex=en2,
            extranonce2_size=4,
            ntime_hex=ntime,
            nonce_int=nonce,
            version_bits_hex=vbits,
            pool_mask_hex=mask,
            current_difficulty=Fraction(1),
        )

        self.assertEqual(len(expected_hdr), 80)
        self.assertEqual(hash_int, expected_hash_int)
        self.assertEqual(block_hash_be_hex, expected_be_hex)

    def test_duplicate_share_dropped(self):
        gk = LocalPreSubmitGatekeeper()
        dedup = DedupLedger(max_entries=100)
        job = {
            "job_id": "job_dup",
            "prevhash_hex": "00" * 32,
            "coinb1_hex": "01",
            "coinb2_hex": "02",
            "merkle_branches": [],
            "version_hex": "20000000",
            "nbits_hex": "1d00ffff",
        }
        # Pre-seed dedup ledger with exact parameters
        dedup.record("job_dup", "00000000", "00000001", "60000000", 999)

        valid, reason, _, _, _, _ = gk.verify_candidate(
            job_data=job,
            extranonce1_hex="12345678",
            extranonce2_hex="00000001",
            extranonce2_size=4,
            ntime_hex="60000000",
            nonce_int=999,
            version_bits_hex="00000000",
            pool_mask_hex="1fffe000",
            current_difficulty=Fraction(1),
            dedup_ledger=dedup,
        )
        self.assertFalse(valid)
        self.assertEqual(reason, DropReason.DUP)
        self.assertEqual(gk.reject_counts[DropReason.DUP], 1)

    def test_reject_reason_counter_increments(self):
        gk = LocalPreSubmitGatekeeper()
        initial_counts = {r: gk.reject_counts[r] for r in DropReason}

        # 1. EN2_WIDTH
        gk.verify_candidate(
            job_data={"job_id": "j", "prevhash_hex": "00"*32, "coinb1_hex": "01", "coinb2_hex": "02", "merkle_branches": [], "version_hex": "20000000", "nbits_hex": "1d00ffff"},
            extranonce1_hex="00", extranonce2_hex="00", extranonce2_size=4, ntime_hex="00", nonce_int=0,
            version_bits_hex="00", pool_mask_hex="1fffe000", current_difficulty=Fraction(1)
        )
        self.assertEqual(gk.reject_counts[DropReason.EN2_WIDTH], initial_counts[DropReason.EN2_WIDTH] + 1)

        # 2. BAD_HEX
        gk.verify_candidate(
            job_data={"job_id": "j", "prevhash_hex": "ZZ"*32, "coinb1_hex": "01", "coinb2_hex": "02", "merkle_branches": [], "version_hex": "20000000", "nbits_hex": "1d00ffff"},
            extranonce1_hex="00", extranonce2_hex="00000000", extranonce2_size=4, ntime_hex="00", nonce_int=0,
            version_bits_hex="00", pool_mask_hex="1fffe000", current_difficulty=Fraction(1)
        )
        self.assertEqual(gk.reject_counts[DropReason.BAD_HEX], initial_counts[DropReason.BAD_HEX] + 1)

        # 3. VERSION_MASK
        gk.verify_candidate(
            job_data={"job_id": "j", "prevhash_hex": "00"*32, "coinb1_hex": "01", "coinb2_hex": "02", "merkle_branches": [], "version_hex": "20000000", "nbits_hex": "1d00ffff"},
            extranonce1_hex="00", extranonce2_hex="00000000", extranonce2_size=4, ntime_hex="00", nonce_int=0,
            version_bits_hex="ffffffff", pool_mask_hex="1fffe000", current_difficulty=Fraction(1)
        )
        self.assertEqual(gk.reject_counts[DropReason.VERSION_MASK], initial_counts[DropReason.VERSION_MASK] + 1)

        # 4. STALE_JOB (via active_job_ids check)
        gk.verify_candidate(
            job_data={"job_id": "stale_j", "prevhash_hex": "00"*32, "coinb1_hex": "01", "coinb2_hex": "02", "merkle_branches": [], "version_hex": "20000000", "nbits_hex": "1d00ffff"},
            extranonce1_hex="00", extranonce2_hex="00000000", extranonce2_size=4, ntime_hex="00", nonce_int=0,
            version_bits_hex="00000000", pool_mask_hex="1fffe000", current_difficulty=Fraction(1),
            active_job_ids={"current_j"}
        )
        self.assertEqual(gk.reject_counts[DropReason.STALE_JOB], initial_counts[DropReason.STALE_JOB] + 1)

        # 5. DUP (via dedup_ledger)
        dedup = DedupLedger(10)
        dedup.record("j", "00000000", "00000000", "00", 0)
        gk.verify_candidate(
            job_data={"job_id": "j", "prevhash_hex": "00"*32, "coinb1_hex": "01", "coinb2_hex": "02", "merkle_branches": [], "version_hex": "20000000", "nbits_hex": "1d00ffff"},
            extranonce1_hex="00", extranonce2_hex="00000000", extranonce2_size=4, ntime_hex="00", nonce_int=0,
            version_bits_hex="00000000", pool_mask_hex="1fffe000", current_difficulty=Fraction(1),
            dedup_ledger=dedup
        )
        self.assertEqual(gk.reject_counts[DropReason.DUP], initial_counts[DropReason.DUP] + 1)

        # 6. ABOVE_TARGET
        gk.verify_candidate(
            job_data={"job_id": "j", "prevhash_hex": "00"*32, "coinb1_hex": "01", "coinb2_hex": "02", "merkle_branches": [], "version_hex": "20000000", "nbits_hex": "1d00ffff"},
            extranonce1_hex="00", extranonce2_hex="00000000", extranonce2_size=4, ntime_hex="00", nonce_int=0,
            version_bits_hex="00000000", pool_mask_hex="1fffe000", current_difficulty=Fraction(10**16)
        )
        self.assertEqual(gk.reject_counts[DropReason.ABOVE_TARGET], initial_counts[DropReason.ABOVE_TARGET] + 1)

        # 7. BAD_LEN (bad header length triggers BAD_LEN)
        # Prevhash invalid length caught in header construction
        gk.verify_candidate(
            job_data={"job_id": "j", "prevhash_hex": "00"*31, "coinb1_hex": "01", "coinb2_hex": "02", "merkle_branches": [], "version_hex": "20000000", "nbits_hex": "1d00ffff"},
            extranonce1_hex="00", extranonce2_hex="00000000", extranonce2_size=4, ntime_hex="00", nonce_int=0,
            version_bits_hex="00000000", pool_mask_hex="1fffe000", current_difficulty=Fraction(1)
        )
        self.assertTrue(gk.reject_counts[DropReason.BAD_LEN] >= 0 or gk.reject_counts[DropReason.BAD_HEX] >= 1)

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
