"""Falsification tests for the exact Lucas algebra boundary."""

import unittest

from lucas.algebra import (
    PHI,
    ZPhi,
    fibonacci,
    lucas,
    lucas_addition,
    lucas_matrix,
    lucas_subtraction,
    phi_power,
)


class TestLucasAlgebra(unittest.TestCase):
    def test_ring_relation_and_conjugation(self):
        self.assertEqual(PHI * PHI, PHI + ZPhi(1, 0))
        self.assertEqual(PHI.conjugate(), ZPhi(1, -1))
        self.assertEqual(PHI.norm(), -1)
        self.assertEqual(PHI.trace(), 1)

    def test_powers_are_exact_fibonacci_coordinates(self):
        expected_fib = [0, 1, 1, 2, 3, 5, 8, 13, 21]
        expected_lucas = [2, 1, 3, 4, 7, 11, 18, 29, 47]
        self.assertEqual([fibonacci(n) for n in range(9)], expected_fib)
        self.assertEqual([lucas(n) for n in range(9)], expected_lucas)
        for n in range(20):
            self.assertEqual(phi_power(n).trace(), lucas(n))

    def test_lucas_addition_and_subtraction_laws(self):
        for a in range(12):
            for b in range(12):
                self.assertEqual(lucas_addition(a, b), lucas(a + b))
                if a >= b:
                    self.assertEqual(lucas_subtraction(a, b), lucas(a - b))

    def test_matrix_representation_preserves_composition(self):
        for a in range(8):
            for b in range(8):
                left = lucas_matrix(a)
                right = lucas_matrix(b)
                product = tuple(
                    tuple(
                        sum(left[row][k] * right[k][column] for k in range(2))
                        for column in range(2)
                    )
                    for row in range(2)
                )
                composed = lucas_matrix(a + b)
                self.assertEqual(product, composed)
                self.assertEqual(
                    composed[0][0] + composed[1][1],
                    lucas(a + b),
                )

    def test_negative_power_is_exact_because_phi_is_a_unit(self):
        self.assertEqual(PHI**-1, PHI - ZPhi(1, 0))
        self.assertEqual(PHI**-3 * PHI**3, ZPhi(1, 0))

    def test_invalid_indices_fail_closed(self):
        with self.assertRaises(ValueError):
            lucas(-1)
        with self.assertRaises(ValueError):
            fibonacci(-1)
        with self.assertRaises(ValueError):
            lucas_subtraction(2, 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
