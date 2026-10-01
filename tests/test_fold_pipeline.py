import os
import tempfile
import unittest
from fractions import Fraction

from python_backend.core_modules.fold_pipeline import FoldPipeline
from python_backend.core_modules.pisot_truncation import UnsupportedExactSVD
from python_backend.core_modules.pisot_truncation import truncate_diagonal_tensor


class Tests(unittest.TestCase):
    def test_persist_execute_and_proof(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            p = FoldPipeline(f.name, b"k" * 32)
            self.addCleanup(lambda: (p.db.close(), os.unlink(f.name)))
            oid = p.put_folded([Fraction(1, 2), Fraction(2, 3)])
            out = p.execute(oid, "pulvini_roundtrip")
            self.assertEqual(out["output"], (Fraction(1, 2), Fraction(2, 3)))
            self.assertTrue(out["proof"]["signature"])

    def test_general_svd_fails_closed(self):
        with self.assertRaises(UnsupportedExactSVD):
            truncate_diagonal_tensor([[1, 1], [0, 1]], threshold_index=5, max_bond=2)

    def test_nonzero_discard_cannot_claim_trace_preservation(self):
        with self.assertRaises(ValueError):
            truncate_diagonal_tensor([[Fraction(1, 100), 0], [0, 1]], threshold_index=5, max_bond=2)


if __name__ == "__main__":
    unittest.main()
