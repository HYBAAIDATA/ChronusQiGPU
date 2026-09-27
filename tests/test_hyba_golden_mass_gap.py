"""Exact spectrum of the canonical M32 Laplacian. Not a Clay proof."""

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from millennium.hyba_golden_mass_gap import cached_report, verify_algebra


class GoldenMassGapTests(unittest.TestCase):
    def test_algebra_certificates_hold(self) -> None:
        checks = dict(verify_algebra(40))
        self.assertTrue(all(checks.values()), checks)

    def test_gap_is_the_quintic_root_and_does_not_close_yang_mills(self) -> None:
        report = cached_report()
        self.assertEqual(report["sites"], 32)
        self.assertEqual(report["edges"], 192)
        self.assertEqual(report["degree_mean"], 12)
        self.assertEqual(report["geometry"], "truncated_icosahedron_32f")
        self.assertTrue(report["mining_truncated_icosahedron"])
        self.assertEqual(report["kernel_multiplicity"], 1)
        self.assertEqual(report["gap_degree"], 5)
        self.assertFalse(report["gap_in_golden_field"])
        self.assertGreater(report["gap_lower"], 5)
        self.assertLess(report["gap_upper"], 6)
        self.assertLess(report["gap_upper"] - report["gap_lower"], 1e-9)
        self.assertTrue(report["golden_partner_above_gap"])
        self.assertFalse(report["cassini_certifies_gap"])
        self.assertFalse(report["index_potential_is_geometric"])
        self.assertFalse(report["proof_claim"])
        self.assertFalse(report["continuum_claim"])
        self.assertFalse(report["physical_qcd_claim"])
        self.assertFalse(report["share_acceptance"])
        self.assertFalse(report["binary_icosahedral_2i"])
        self.assertEqual(report["evidence_class"], "EXACT_ARITHMETIC")
        self.assertEqual(report["rungs"][-1], "continuum Yang-Mills: open")


if __name__ == "__main__":
    unittest.main()
