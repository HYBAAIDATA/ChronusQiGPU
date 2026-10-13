"""Tests for YangMillsScaffold internal research surface."""

from __future__ import annotations

import unittest

from integrations.solvers.yangmills_scaffold import YangMillsScaffold, YangMillsScaffoldConfig


class TestYangMillsScaffold(unittest.TestCase):
    def setUp(self) -> None:
        self.scaffold = YangMillsScaffold(YangMillsScaffoldConfig())

    def test_analyze_finite_spectrum(self) -> None:
        res = self.scaffold.analyze_finite_spectrum()
        self.assertEqual(res["status"], "FINITE_VOLUME_SPECTRAL_VERIFICATION")
        self.assertEqual(res["evidence_class"], "FINITE_VOLUME_VERIFIED")
        self.assertFalse(res["proof_claim"])
        self.assertFalse(res["continuum_claim"])
        self.assertEqual(res["level_count"], 9)
        self.assertTrue(res["gap_exact"]["verified"])
        self.assertEqual(res["gap_exact"]["dimension"], 2)

    def test_compute_gap_ratio(self) -> None:
        gap = self.scaffold.compute_gap_ratio()
        expected = (3.0 - 5.0**0.5) / 4.0
        self.assertAlmostEqual(gap, expected, places=12)


if __name__ == "__main__":
    unittest.main()
