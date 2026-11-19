import asyncio
import unittest
from chronus.stratum.sharding import WorkPartitioner, DedupLedger, ShareCandidate, emit_share_candidate
import pytest

pytestmark = pytest.mark.real


class TestSharding(unittest.TestCase):
    def test_partitioner_non_overlapping_ranges(self):
        partitioner = WorkPartitioner(shard_count=8, pool_mask_hex="1fffe000")
        self.assertEqual(len(partitioner.ranges), 8)

        # Assert zero overlap
        for i in range(7):
            r1 = partitioner.get_range(i)
            r2 = partitioner.get_range(i + 1)
            self.assertEqual(r1.end_nonce, r2.start_nonce)

        self.assertEqual(partitioner.get_range(0).start_nonce, 0)
        self.assertEqual(partitioner.get_range(7).end_nonce, 1 << 32)

    def test_nonce_ranges_do_not_overlap(self):
        """Validates that all shard nonce ranges strictly partition [0, 2^32) with zero overlap."""
        shard_count = 16
        partitioner = WorkPartitioner(shard_count=shard_count, pool_mask_hex="1fffe000")
        ranges = partitioner.ranges
        self.assertEqual(len(ranges), shard_count)

        for i in range(shard_count - 1):
            r_curr = ranges[i]
            r_next = ranges[i + 1]
            # Strict arithmetic bounds
            self.assertLess(r_curr.start_nonce, r_curr.end_nonce)
            self.assertEqual(r_curr.end_nonce, r_next.start_nonce)
            self.assertTrue((r_curr.end_nonce - 1) < r_next.start_nonce)

        self.assertEqual(ranges[0].start_nonce, 0)
        self.assertEqual(ranges[-1].end_nonce, 1 << 32)

    def test_version_bits_do_not_overlap(self):
        """Validates that each shard owns a distinct, non-overlapping version_bits sub-mask."""
        shard_count = 16
        pool_mask = 0x1fffe000
        partitioner = WorkPartitioner(shard_count=shard_count, pool_mask_hex=f"{pool_mask:08x}")

        v_offsets = [partitioner.get_range(i).version_bits_offset for i in range(shard_count)]
        self.assertEqual(len(v_offsets), len(set(v_offsets)), "All version bit offsets must be unique.")

        for i in range(shard_count):
            expected = (i << 13) & pool_mask
            self.assertEqual(partitioner.get_range(i).version_bits_offset, expected)
            computed_version = partitioner.compute_version_bits(i, base_version=0x20000000)
            self.assertEqual(computed_version, 0x20000000 | expected)

    def test_dedup_ledger(self):
        ledger = DedupLedger(max_entries=5)
        res1 = ledger.record("j1", "00000000", "00000001", "60000000", 100)
        self.assertTrue(res1)

        # Immediate duplicate
        res2 = ledger.record("j1", "00000000", "00000001", "60000000", 100)
        self.assertFalse(res2)

    def test_dedup_ledger_blocks_duplicate(self):
        """Validates that DedupLedger correctly blocks duplicate submissions across shards."""
        ledger = DedupLedger(max_entries=100)
        key = ("job_alpha", "00002000", "00000001", "60000000", 123456)
        
        self.assertFalse(ledger.is_duplicate(*key))
        self.assertTrue(ledger.record(*key))
        self.assertTrue(ledger.is_duplicate(*key))
        self.assertFalse(ledger.record(*key))

        # Distinct nonce or version_bits allowed
        self.assertTrue(ledger.record("job_alpha", "00002000", "00000001", "60000000", 123457))
        self.assertTrue(ledger.record("job_alpha", "00004000", "00000001", "60000000", 123456))

    def test_discard_job_preserves_other_entries_and_eviction_order(self):
        ledger = DedupLedger(max_entries=2)
        key = ("00000000", "00000001", "60000000", 100)
        ledger.record("replaced", *key)
        ledger.record("retained", *key)
        ledger.discard_job("replaced")
        ledger.discard_job("absent")
        self.assertFalse(ledger.is_duplicate("replaced", *key))
        self.assertTrue(ledger.is_duplicate("retained", *key))
        self.assertTrue(ledger.record("replacement", *key))
        self.assertTrue(ledger.record("next", *key))
        self.assertFalse(ledger.is_duplicate("retained", *key))
        self.assertTrue(ledger.is_duplicate("replacement", *key))
        self.assertTrue(ledger.is_duplicate("next", *key))

    def test_emit_share_candidate_bounded_queue(self):
        """Validates that emit_share_candidate enforces queue bounds and dedup."""
        queue = asyncio.Queue(maxsize=2)
        ledger = DedupLedger()

        c1 = ShareCandidate("j1", "01", "60", 1, "00", 10)
        c2 = ShareCandidate("j1", "01", "60", 2, "00", 20)
        c3 = ShareCandidate("j1", "01", "60", 3, "00", 30)

        # 1 and 2 succeed
        self.assertTrue(asyncio.run(emit_share_candidate(queue, c1, ledger)))
        self.assertTrue(asyncio.run(emit_share_candidate(queue, c2, ledger)))

        # Duplicate of c1 rejected by dedup
        self.assertFalse(asyncio.run(emit_share_candidate(queue, c1, ledger)))

        # 3 rejected due to queue bounded capacity backpressure
        self.assertFalse(asyncio.run(emit_share_candidate(queue, c3, ledger)))
        self.assertEqual(queue.qsize(), 2)

        # Unbounded queue rejected fail-closed
        unbounded = asyncio.Queue(maxsize=0)
        with self.assertRaises(ValueError):
            asyncio.run(emit_share_candidate(unbounded, c3))


if __name__ == "__main__":
    unittest.main()
