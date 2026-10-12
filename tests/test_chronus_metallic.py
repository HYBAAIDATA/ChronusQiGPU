import unittest

from chronus.metallic import (
    MetallicElement, bronze, copper, metallic, metallic_exact,
    metallic_fast_doubling, metallic_ladder, silver,
)


class MetallicTests(unittest.TestCase):
    def test_identity_and_generator(self):
        for n in range(1, 9):
            mu = metallic_exact(n)
            self.assertEqual(mu**0, MetallicElement(n, 1, 0))
            self.assertEqual(mu**1, MetallicElement(n, 0, 1))
            self.assertEqual(mu**2, MetallicElement(n, 1, n))
            self.assertEqual(metallic(n), mu)

    def test_recurrence_coefficients(self):
        for n in range(1, 9):
            a, b = 1, 0
            for k in range(100):
                self.assertEqual(metallic_fast_doubling(n, k), MetallicElement(n, a, b))
                a, b = b, a + n * b

    def test_power_composition(self):
        for n in range(1, 5):
            mu = metallic(n)
            for k in range(15):
                for j in range(15):
                    self.assertEqual(mu**k * mu**j, mu ** (k + j))

    def test_conjugate_and_norm(self):
        for n in range(1, 6):
            for a in range(-3, 4):
                for b in range(-3, 4):
                    value = MetallicElement(n, a, b)
                    self.assertEqual(value.conjugate().conjugate(), value)
                    self.assertEqual(value * value.conjugate(), MetallicElement(n, value.norm()))
            self.assertEqual(metallic(n).norm(), -1)

    def test_named_family_and_ladder(self):
        self.assertEqual((silver().n, bronze().n, copper().n), (2, 3, 4))
        self.assertEqual(metallic_ladder(2, [0, 1, 3]), [silver()**k for k in (0, 1, 3)])

    def test_invalid_fields_and_coefficients(self):
        with self.assertRaises(ValueError):
            silver() * bronze()
        with self.assertRaises(ValueError):
            metallic(0)
        with self.assertRaises(ValueError):
            silver()**-1
        for value in (True, 1.0):
            with self.assertRaises(TypeError):
                metallic(value)
            with self.assertRaises(TypeError):
                MetallicElement(1, value)
            with self.assertRaises(TypeError):
                silver()**value
