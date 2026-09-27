import tempfile
import unittest
from pathlib import Path
from mla1517 import PrimeDB, cassini, fib, lucas, zeckendorf, zeckendorf_decode


class ProductionTests(unittest.TestCase):
    def test_exact_primitives(self):
        self.assertEqual(fib(15), 610)
        self.assertEqual(lucas(15), 1364)
        for n in range(1, 201):
            self.assertEqual(cassini(n), (-1) ** n)
        for n in range(1, 1000):
            self.assertEqual(zeckendorf_decode(zeckendorf(n)[0]), n)

    def test_content_addressed_store(self):
        with tempfile.TemporaryDirectory() as d:
            db = PrimeDB(Path(d) / "prime.db")
            obj = db.put({"kind": "demo", "value": 610}, sequence_index=15, scale=15)
            self.assertEqual(db.count(), 1)
            self.assertTrue(db.verify(obj.object_id)["valid"])
            self.assertEqual(db.get(obj.object_id).to_dict(), obj.to_dict())
            db.put({"kind": "demo", "value": 610}, sequence_index=15, scale=15)
            self.assertEqual(db.count(), 1)
            db.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
