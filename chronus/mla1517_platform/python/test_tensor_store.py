import tempfile
import unittest
from pathlib import Path
from chronus.mla1517.store import PrimeDB


class TensorStoreTests(unittest.TestCase):
    def test_exact_long4_round_trip(self):
        payload = bytes(range(64))
        with tempfile.TemporaryDirectory() as d:
            db = PrimeDB(Path(d) / "prime.db")
            tid = db.put_exact_tensor(payload, 3)
            out = db.get_exact_tensor(tid)
            self.assertEqual(out["payload"], payload)
            self.assertEqual(out["amplitude_count"], 2)
            self.assertEqual(out["global_scale"], 3)
            db.close()

    def test_truncated_tensor_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            db = PrimeDB(Path(d) / "prime.db")
            with self.assertRaises(ValueError):
                db.put_exact_tensor(b"123", 0)
            db.close()


if __name__ == "__main__":
    unittest.main()
