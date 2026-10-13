"""Tests verifying exact closed-form derivation of the Yang-Mills mass gap.

Ensures that the gap Δ = 1 - φ/2 = (3 - √5)/4 is derived exactly from the
character algebra without any floating-point tolerance searching.
"""

from __future__ import annotations

import unittest

from millennium.exact_gap import (
    ExactGap,
    derive_exact_mass_gap,
    exact_gap_from_class_algebra,
)

SQRT5 = 5.0**0.5
PHI = (1.0 + SQRT5) / 2.0


class ExactGapTests(unittest.TestCase):
    def test_exact_gap_proof_carrying(self) -> None:
        gap_obj = exact_gap_from_class_algebra()
        self.assertIsInstance(gap_obj, ExactGap)
        self.assertTrue(gap_obj.verify_exact())
        self.assertEqual(gap_obj.dimension, 2)
        # chi/d on gap irrep is phi/2 = (1 + sqrt(5))/4
        self.assertEqual(gap_obj.character_value, (1, 1))
        # gap = (3 - sqrt(5))/4
        self.assertEqual(gap_obj.gap_exact_form, (3, -1))
        self.assertEqual(gap_obj.k, 4)

        expected_gap = (3.0 - SQRT5) / 4.0
        self.assertAlmostEqual(gap_obj.gap_float, expected_gap, places=12)
        self.assertAlmostEqual(gap_obj.gap_float, 1.0 - PHI / 2.0, places=12)
        self.assertAlmostEqual(gap_obj.gap_float, 1.0 / (2.0 * PHI * PHI), places=12)

    def test_characteristic_polynomial_exact_match(self) -> None:
        gap_obj = exact_gap_from_class_algebra()
        # Characteristic polynomial of M_edge:
        # P(x) = x(x-12)(x-3)(x+3)(x+2)(x^2-6x-36)(x^2-4x-16)
        # = x^9 - 20x^8 + 39x^7 + 940x^6 - 1584x^5 - 18360x^4 - 3456x^3 + 103680x^2 + 124416x
        expected_poly = (1, -20, 39, 940, -1584, -18360, -3456, 103680, 124416, 0)
        self.assertEqual(gap_obj.char_poly_coeffs, expected_poly)

    def test_exact_spectrum_levels(self) -> None:
        gap_obj = exact_gap_from_class_algebra()
        self.assertEqual(len(gap_obj.levels), 9)

        # Multiplicities d^2 sum to 120
        total_dim_sq = sum(lvl.multiplicity for lvl in gap_obj.levels)
        self.assertEqual(total_dim_sq, 120)

        # Trivial rep (vacuum) has eigenvalue 0
        lvl0 = gap_obj.levels[0]
        self.assertEqual(lvl0.dimension, 1)
        self.assertEqual(lvl0.multiplicity, 1)
        self.assertEqual(lvl0.eigenvalue_exact, (0, 0, 1))
        self.assertEqual(lvl0.eigenvalue_float, 0.0)

        # Spinor rep (gap) has eigenvalue (3 - sqrt5)/4
        lvl1 = gap_obj.levels[1]
        self.assertEqual(lvl1.dimension, 2)
        self.assertEqual(lvl1.multiplicity, 4)
        self.assertEqual(lvl1.eigenvalue_exact, (3, -1, 4))

        # Check all dimensions
        dims = sorted(lvl.dimension for lvl in gap_obj.levels)
        self.assertEqual(dims, [1, 2, 2, 3, 3, 4, 4, 5, 6])

    def test_boundary_honesty(self) -> None:
        rep = derive_exact_mass_gap()
        self.assertFalse(rep["proof_claim"])
        self.assertFalse(rep["continuum_claim"])
        self.assertEqual(rep["evidence_class"], "FINITE_VOLUME_VERIFIED")
        self.assertIn("not continuum", rep["scope"])


if __name__ == "__main__":
    unittest.main()
