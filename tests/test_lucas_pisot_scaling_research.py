"""Falsification tests for the birth-derived Lucas/Pisot scaling family."""

from decimal import Decimal, localcontext
import math
import unittest

from lucas.algebra import fibonacci as algebra_fibonacci
from lucas.algebra import lucas as algebra_lucas
from lucas.core import fibonacci, lucas
from lucas.scaling_research import DISCOVERY_INDICES, float64_boundary, pisot_certificate


class TestLucasPisotScalingResearch(unittest.TestCase):
    def test_discovery_indices_and_values_are_stable(self):
        self.assertEqual(DISCOVERY_INDICES, (10, 12, 15, 18, 20))
        self.assertEqual([lucas(n) for n in DISCOVERY_INDICES], [123, 322, 1364, 5778, 15127])

    def test_independent_exact_implementations_agree(self):
        for n in range(501):
            self.assertEqual(lucas(n), algebra_lucas(n))
            self.assertEqual(fibonacci(n), algebra_fibonacci(n))

    def test_cassini_hoggatt_identity_exact_through_500(self):
        for n in range(501):
            self.assertEqual(lucas(n) ** 2 - 5 * fibonacci(n) ** 2, 4 * ((-1) ** n))

    def test_pisot_identity_and_nearest_integer(self):
        for n in (*DISCOVERY_INDICES, 31, 39, 50, 76, 100, 500):
            row = pisot_certificate(n)
            residual = Decimal(row["absolute_residual"])
            expected = Decimal(row["expected_residual"])
            tolerance = Decimal(10) ** (-max(60, n // 2))
            self.assertLess(abs(residual / expected - 1), tolerance)
            if n >= 2:
                self.assertEqual(int(row["nearest_integer"]), lucas(n))

    def test_selected_indices_have_no_special_normalized_pisot_effect(self):
        controls = sorted({n + d for n in DISCOVERY_INDICES for d in (-1, 0, 1)})
        for n in controls:
            normalized = Decimal(pisot_certificate(n)["normalized_residual"])
            self.assertLess(abs(normalized - 1), Decimal("1e-90"))

    def test_float64_precision_boundary_is_explicit(self):
        boundary = float64_boundary()
        self.assertEqual(boundary["true_residual_unrepresentable_first_n"], 39)
        self.assertEqual(boundary["float_pow_integral_first_n"], 70)
        self.assertEqual(boundary["float_pow_error_at_first_integral"], 1)
        self.assertEqual(boundary["float_pow_error_at_n76"], 19)

    def test_float_integrality_must_not_masquerade_as_exactness(self):
        phi_float = (1.0 + math.sqrt(5.0)) / 2.0
        self.assertEqual(phi_float**70, round(phi_float**70))
        self.assertNotEqual(int(phi_float**70), lucas(70))
        self.assertNotEqual(int(phi_float**76), lucas(76))


if __name__ == "__main__":
    unittest.main(verbosity=2)
