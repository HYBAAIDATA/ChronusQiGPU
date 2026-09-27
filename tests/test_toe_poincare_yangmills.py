"""What the finite 2I thread unlocks inside the TOE, and what it does not."""

from __future__ import annotations

import math
import unittest

from toe.poincare_yangmills import (
    EXACT_GAP,
    capability_record,
    finite_gauge_gap,
    join_summary,
    unlocked_capabilities,
)

PHI = (1.0 + math.sqrt(5.0)) / 2.0


class ToeJoinTests(unittest.TestCase):
    def test_gap_the_toe_reads_is_the_computed_eigenvalue(self) -> None:
        gap = finite_gauge_gap()
        self.assertAlmostEqual(gap, EXACT_GAP, places=6)
        self.assertAlmostEqual(gap, 1.0 - PHI / 2.0, places=6)
        self.assertNotAlmostEqual(gap, math.sqrt(5.0), places=2)

    def test_unlocked_capabilities_are_exactly_the_computed_ones(self) -> None:
        report = unlocked_capabilities()
        self.assertFalse(report["proof_claim"])
        self.assertFalse(report["continuum_claim"])
        self.assertEqual(
            report["unlocked_ids"],
            [
                "finite_su2_spectrum",
                "gauge_invariant_states",
                "casimir_multiplicities",
                "six_hundred_cell",
                "phi_thread",
                "two_poincares_distinguished",
            ],
        )
        self.assertEqual(
            report["locked_ids"],
            [
                "continuum_yang_mills",
                "share_acceptance",
                "riemann_p_vs_np_bsd_hodge_navier_stokes",
                "device_throughput",
            ],
        )
        self.assertTrue(all(item["status"] == "unlocked" for item in report["unlocked"]))
        self.assertTrue(all(item["status"] == "locked" for item in report["still_locked"]))

    def test_join_summary_keeps_the_two_poincare_geometries_apart(self) -> None:
        summary = join_summary()
        self.assertTrue(summary["available"])
        self.assertEqual(summary["order"], 120)
        self.assertEqual(summary["topology"]["euler"], 0)
        self.assertIn("11D hyperbolic", summary["distinct_from"])
        self.assertTrue(summary["matches_one_minus_phi_over_two"])
        self.assertFalse(summary["proof_claim"])
        self.assertFalse(summary["continuum_claim"])

    def test_expansion_record_does_not_inflate_the_claim(self) -> None:
        record = capability_record()
        self.assertEqual(record["status"], "implemented")
        self.assertEqual(record["truth_class"], "finite_volume_spectrum")
        self.assertFalse(record["proof_claim"])
        self.assertFalse(record["continuum_claim"])
        self.assertIn("not the continuum", record["claim"])


if __name__ == "__main__":
    unittest.main()
