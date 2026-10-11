import sys
from dataclasses import replace
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))
from chronos.lucas_engine import (
    InvariantViolation, PrimeIndexedStore, binet_exact, binet_fold,
    binet_unfold, fibonacci_pair, lucas, lucas_recurrence, make_record,
    process_batch, zeckendorf_decode, zeckendorf_encode,
)

class LucasEngineTests(unittest.TestCase):
    def test_base_and_differential_values(self):
        self.assertEqual([lucas(n) for n in range(8)], [2,1,3,4,7,11,18,29])
        self.assertEqual([binet_exact(n) for n in range(501)], lucas_recurrence(500))
        for n in range(0, 5001, 37): self.assertEqual(binet_exact(n), lucas(n))

    def test_zeckendorf_property_and_fold_round_trip(self):
        for n in range(10001):
            mask = zeckendorf_encode(n)
            self.assertEqual(zeckendorf_decode(mask), n)
            self.assertEqual(mask & (mask << 1), 0)
        for n in range(1001): self.assertEqual(binet_unfold(binet_fold(n)), n)

    def test_record_and_batch_contract(self):
        records = process_batch([0, 1, 2, 10])
        self.assertEqual([r.index for r in records], [0,1,2,10])
        for record in records: record.verify()

    def test_fail_closed_store(self):
        store = PrimeIndexedStore(); record = make_record(8); store.write(record)
        with self.assertRaises(InvariantViolation): store.write(replace(record, lucas_value=0))
        store._rows[0] = (record.prime_address, replace(record, lucas_value=0))
        with self.assertRaises(InvariantViolation): store.read(record.prime_address)

if __name__ == '__main__': unittest.main()
