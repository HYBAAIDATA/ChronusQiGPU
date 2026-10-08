import sys
from dataclasses import replace
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))
from chronos.lucas_datapath import (
    DatapathConfig, DatapathFailure, JsonShareAdapter, MiningTarget, SpatialLucasPipeline,
    disjoint_segments, nonce_window,
)

class DatapathTests(unittest.TestCase):
    def setUp(self):
        self.pipeline = SpatialLucasPipeline(DatapathConfig(working_width=32, prime_rom_limit=1000))
    def test_six_stage_spec_and_records(self):
        self.assertEqual(self.pipeline.specification()['pipeline_depth'], 6)
        records = self.pipeline.process_batch(range(32))
        self.assertEqual(len(records), 32)
        for record in records: self.pipeline.verify(record)
    def test_fixed_width_cassini_and_fail_closed_certificate(self):
        record = self.pipeline.process_one(10)
        self.assertTrue(record.cassini_pass)
        with self.assertRaises(DatapathFailure):
            self.pipeline.verify(replace(record, value=record.value + 1))
    def test_prime_rom_boundary(self):
        self.pipeline.process_one(999)
        with self.assertRaises(DatapathFailure): self.pipeline.process_one(1000)
    def test_mining_share_and_segments(self):
        target = MiningTarget(max_value=2**32 - 1)
        shares = self.pipeline.mine_segment(0, 16, target)
        self.assertEqual(len(shares), 16)
        segments = disjoint_segments(0, 100, 7)
        self.assertEqual(segments[0][0], 0)
        self.assertEqual(segments[-1][1], 100)
        self.assertEqual(sum(b-a for a,b in segments), 100)
        for left, right in zip(segments, segments[1:]): self.assertEqual(left[1], right[0])
        window = nonce_window(10)
        self.assertEqual(window.rung, 10)
        self.assertGreater(window.length, 0)
        payload = JsonShareAdapter().encode(shares[0])
        self.assertIn(b"certificate", payload)

if __name__ == '__main__': unittest.main()
