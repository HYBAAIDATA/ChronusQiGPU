import unittest
from chronus.mla1517.accelerator import AcceleratorUnavailable, CanonicalAccelerator
from chronus.mla1517.quantum import ExactStateVector, H


class AcceleratorTests(unittest.TestCase):
    def test_canonical_exact_execution(self):
        state, receipt = CanonicalAccelerator().execute(
            ExactStateVector.basis(1), [lambda s: s.apply_single(0, H)]
        )
        self.assertTrue(receipt.exact)
        self.assertEqual(receipt.transformations, 1)
        self.assertTrue(state.normalized_exact())

    def test_hardware_path_fails_closed(self):
        with self.assertRaises(AcceleratorUnavailable):
            CanonicalAccelerator("mla1517_chronus")


if __name__ == "__main__":
    unittest.main()
