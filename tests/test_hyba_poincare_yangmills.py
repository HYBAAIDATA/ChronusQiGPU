"""The finite 2I / Poincare-homology thread computes its own gap.

These checks pin the mathematics of ``millennium.hyba_poincare_yangmills``.
They do not, and must not, promote that finite spectrum to a continuum
Yang-Mills theorem.
"""

from __future__ import annotations

import math
import unittest

from millennium.hyba_poincare_yangmills import cached_report

PHI = (1.0 + math.sqrt(5.0)) / 2.0


class HybaPoincareYangMillsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = cached_report(verbose=False)

    def test_golden_seed_holds(self) -> None:
        self.assertTrue(self.report["golden_checks"])
        self.assertTrue(all(item["pass"] for item in self.report["golden_checks"]))

    def test_binary_icosahedral_group(self) -> None:
        self.assertEqual(self.report["group_order"], 120)
        self.assertEqual(self.report["rotation_order"], 5)
        self.assertEqual(self.report["edge_class_order"], 10)
        self.assertEqual(self.report["edge_class_size"], 12)
        self.assertTrue(self.report["all_units"])
        self.assertTrue(self.report["closed_product"])
        self.assertTrue(self.report["closed_inverse"])

    def test_poincare_homology_sphere_classes(self) -> None:
        self.assertEqual(self.report["class_count"], 9)
        self.assertEqual(sorted(self.report["class_sizes"]), [1, 1, 12, 12, 12, 12, 20, 20, 30])
        self.assertEqual(sum(self.report["class_sizes"]), 120)

    def test_six_hundred_cell_is_a_three_sphere(self) -> None:
        topology = self.report["topology"]
        self.assertEqual(
            (topology["V"], topology["E"], topology["F"], topology["C"]), (120, 720, 1200, 600)
        )
        self.assertEqual(topology["euler"], 0)

    def test_character_table_is_the_group(self) -> None:
        self.assertEqual(sorted(self.report["dims"]), [1, 2, 2, 3, 3, 4, 4, 5, 6])
        self.assertEqual(self.report["sum_squares"], 120)
        self.assertTrue(self.report["orthogonality"])

    def test_spectrum_reads_off_a_positive_gap(self) -> None:
        self.assertTrue(self.report["hermitian"])
        self.assertTrue(self.report["inverse_closed"])
        self.assertLess(abs(self.report["lambda0"]), 1e-8)
        expected = 1.0 - PHI / 2.0
        self.assertAlmostEqual(self.report["gap"], expected, places=6)
        self.assertAlmostEqual(self.report["gap"], 1.0 / (2.0 * PHI * PHI), places=6)
        self.assertAlmostEqual(self.report["gap"], (3.0 - math.sqrt(5.0)) / 4.0, places=6)
        self.assertGreater(self.report["gap"], 0.0)
        # chi(g)/d on the gap irrep is phi/2 = (1 + sqrt(5))/4, recognized, not typed in.
        self.assertEqual(self.report["gap_algebraic"], {"p": 1, "q": 1, "k": 4})
        multiplicities = sorted(level["multiplicity"] for level in self.report["levels"])
        self.assertEqual(multiplicities, sorted(d * d for d in self.report["dims"]))

    def test_finite_result_does_not_claim_the_clay_problem(self) -> None:
        self.assertFalse(self.report["proof_claim"])
        self.assertFalse(self.report["continuum_claim"])
        self.assertEqual(self.report["evidence_class"], "FINITE_VOLUME_VERIFIED")
        self.assertIn("not continuum", self.report["scope"])


if __name__ == "__main__":
    unittest.main()
