import unittest
from fractions import Fraction
from math import gcd

from chronus.calkin_wilf import (
    binary_path, calkin_wilf, calkin_wilf_index, phi_convergents, stern_brocot_neighbors,
)


class CalkinWilfTests(unittest.TestCase):
    def test_initial_breadth_first_order(self):
        self.assertEqual(
            [calkin_wilf(n) for n in range(1, 8)],
            [(1, 1), (1, 2), (2, 1), (1, 3), (3, 2), (2, 3), (3, 1)],
        )
        self.assertEqual(binary_path(1), [])
        self.assertEqual(binary_path(13), [1, 0, 1])

    def test_inverse_and_uniqueness(self):
        seen = set()
        for n in range(1, 10001):
            value = calkin_wilf(n)
            self.assertEqual(gcd(*value), 1)
            self.assertEqual(calkin_wilf_index(*value), n)
            self.assertNotIn(value, seen)
            seen.add(value)

    def test_fraction_roundtrip(self):
        for a in range(1, 51):
            for b in range(1, 51):
                if gcd(a, b) == 1:
                    self.assertEqual(calkin_wilf(calkin_wilf_index(a, b)), (a, b))

    def test_euclidean_runs(self):
        self.assertEqual(calkin_wilf_index(1, 1000), 1 << 999)
        self.assertEqual(calkin_wilf_index(1000, 1), (1 << 1000) - 1)

    def test_stern_brocot_mediant_parents(self):
        for a in range(1, 31):
            for b in range(1, 31):
                if gcd(a, b) != 1:
                    continue
                (p, q), (r, s) = stern_brocot_neighbors(a, b)
                self.assertEqual((p + r, q + s), (a, b))
                self.assertEqual(r * q - p * s, 1)
                self.assertGreaterEqual(p, 0)
                self.assertGreaterEqual(s, 0)

    def test_exact_convergents(self):
        self.assertEqual(
            phi_convergents(5),
            [Fraction(1), Fraction(2), Fraction(3, 2), Fraction(5, 3), Fraction(8, 5)],
        )
        self.assertEqual(phi_convergents(0), [])

    def test_invalid_inputs(self):
        for n in (0, -1):
            with self.assertRaises(ValueError):
                calkin_wilf(n)
        for n in (True, 1.0):
            with self.assertRaises(TypeError):
                calkin_wilf(n)
        for fraction in ((0, 1), (1, 0), (2, 2), (-1, 2)):
            with self.assertRaises(ValueError):
                calkin_wilf_index(*fraction)
        with self.assertRaises(TypeError):
            calkin_wilf_index(True, 1)
        with self.assertRaises(ValueError):
            phi_convergents(-1)
