"""Exact structure of the Fibonacci-Korobov lattice.

The square congruence is Cassini. Dimension three collapses. The
modulus-64 walk in the traversal adapter is a different lattice.
"""

from __future__ import annotations

import unittest
from fractions import Fraction

from kellogg.first_principles import fibonacci_lattice, fibonacci_number, korobov_points


class FibonacciKorobovTests(unittest.TestCase):
    def test_generator_square_is_plus_or_minus_one(self):
        for n in range(3, 31):
            modulus = fibonacci_number(n)
            generator = fibonacci_number(n - 1)
            # F_n F_{n-2} - F_{n-1}^2 = (-1)^{n-1}
            self.assertEqual(
                modulus * fibonacci_number(n - 2) - generator * generator,
                -1 if n % 2 == 0 else 1,
            )
            residue = pow(generator, 2, modulus)
            self.assertEqual(residue, 1 if n % 2 == 0 else modulus - 1)
            self.assertEqual(pow(generator, 3, modulus), (generator * residue) % modulus)

    def test_two_dimensional_rule_is_the_korobov_lattice(self):
        for n in (8, 12, 18):
            modulus = fibonacci_number(n)
            generator = fibonacci_number(n - 1)
            self.assertEqual(
                fibonacci_lattice(n),
                korobov_points(modulus, generator, 2),
            )
            grid = [Fraction(k, modulus) for k in range(modulus)]
            points = fibonacci_lattice(n)
            self.assertEqual(sorted(point[0] for point in points), grid)
            self.assertEqual(sorted(point[1] for point in points), grid)

    def test_third_power_coordinate_collapses(self):
        for n in (8, 9, 15, 18):
            modulus = fibonacci_number(n)
            points = korobov_points(modulus, fibonacci_number(n - 1), 3)
            for x, _y, z in points:
                if n % 2 == 0:
                    self.assertEqual(z, x)
                else:
                    self.assertEqual(z, 0 if x == 0 else 1 - x)

    def test_consecutive_fibonacci_residues_are_a_line(self):
        for n in (10, 18):
            modulus = fibonacci_number(n)
            first = fibonacci_number(n - 1)
            second = fibonacci_number(n - 2)
            for k in range(modulus):
                self.assertEqual(
                    ((k * first) % modulus + (k * second) % modulus) % modulus,
                    0,
                )

    def test_published_modulus_has_an_exact_product_and_corner(self):
        points = fibonacci_lattice(18)
        modulus = len(points)
        self.assertEqual(modulus, 2584)
        mean = sum((x * y for x, y in points), Fraction(0)) / modulus
        self.assertEqual(mean - Fraction(1, 4), Fraction(-1621, 13354112))
        corner = sum(
            1 for x, y in points if x < Fraction(1, 2) and y < Fraction(1, 2)
        )
        self.assertEqual(corner, modulus // 4)

    def test_half_square_count_through_f21(self):
        for n in range(3, 22):
            points = fibonacci_lattice(n)
            modulus = len(points)
            corner = sum(
                1 for x, y in points if x < Fraction(1, 2) and y < Fraction(1, 2)
            )
            self.assertEqual(corner, (modulus + 3) // 4)

    def test_modulus_64_is_not_the_fibonacci_lattice(self):
        self.assertTrue(all(fibonacci_number(n) != 64 for n in range(1, 24)))
        self.assertEqual(pow(55, 2, 64), 17)
        self.assertNotEqual(17, 1)
        self.assertNotEqual(17, 63)


if __name__ == "__main__":
    unittest.main()
