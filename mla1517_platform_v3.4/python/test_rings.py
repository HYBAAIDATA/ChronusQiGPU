import unittest
from mla1517.rings import ZPhi, ZRho, ZPsi, ZTau


class ExactRingTests(unittest.TestCase):
    def test_phi_relation_and_norm(self):
        phi = ZPhi(0, 1)
        self.assertEqual(phi * phi, ZPhi(1, 1))
        self.assertEqual((ZPhi(3, 2)).norm(), 11)

    def test_cubic_relations(self):
        self.assertEqual(ZRho((0, 1, 0)) ** 3, ZRho((1, 1, 0)))
        self.assertEqual(ZPsi((0, 1, 0)) ** 3, ZPsi((1, 0, 1)))
        self.assertEqual(ZTau((0, 1, 0)) ** 3, ZTau((1, 1, 1)))

    def test_cubic_norm_is_integer(self):
        for cls in (ZRho, ZPsi, ZTau):
            self.assertIsInstance(cls((2, 3, 4)).norm(), int)


if __name__ == "__main__":
    unittest.main()
