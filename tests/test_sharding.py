import unittest
from chronus.stratum.sharding import WorkPartitioner, DedupLedger


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

    def test_dedup_ledger(self):
        ledger = DedupLedger(max_entries=5)
        res1 = ledger.record("j1", "00000000", "00000001", "60000000", 100)
        self.assertTrue(res1)

        # Immediate duplicate
        res2 = ledger.record("j1", "00000000", "00000001", "60000000", 100)
        self.assertFalse(res2)


if __name__ == "__main__":
    unittest.main()
