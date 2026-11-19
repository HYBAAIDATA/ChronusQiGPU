# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""Value-share reconciliation (P7a, P7b, P11), Tier 4 and Scale only."""

import unittest

from chronus.fleet.errors import TierGateRejected, VerificationError
from chronus.fleet.phase import TIER_1, TIER_4, scale_tier
from chronus.fleet.value_share import (
    Contribution,
    build_value_share_matrix,
    contributions_from_receipts,
    is_irreducible,
    reconcile_value_share,
)
import pytest

pytestmark = pytest.mark.real

FOUR = ["hyba-data", "hyba-security", "hyba-software", "hyba-finance"]


def ring(amount=100):
    """Each participant contributes the same total, around a ring and to itself."""
    out = []
    for i, name in enumerate(FOUR):
        out.append(Contribution(name, FOUR[(i + 1) % 4], amount))
        out.append(Contribution(name, name, amount))
    return out


class MatrixTests(unittest.TestCase):
    def test_p7a_entries_are_summed_verified_items(self):
        matrix = build_value_share_matrix(
            [Contribution("a", "b", 5), Contribution("a", "b", 7), Contribution("b", "a", 1)], ["a", "b"]
        )
        self.assertEqual(matrix, [[0, 12], [1, 0]])
        with self.assertRaises(VerificationError):
            build_value_share_matrix([Contribution("a", "z", 1)], ["a", "b"])

    def test_irreducibility(self):
        self.assertTrue(is_irreducible([[0, 1], [1, 0]]))
        self.assertFalse(is_irreducible([[1, 1], [0, 1]]))
        self.assertFalse(is_irreducible([[0]]))

    def test_contributions_come_from_measured_receipt_devices(self):
        # Extraction fixture represents a body after signature/anchor verification.
        receipts = [
            {"submitter": "hyba-data", "devices": [{"owner": "hyba", "items": 20, "verified_items": 10, "measured": True},
                                                   {"owner": "x", "items": 4, "verified_items": 4, "measured": False}]}
        ]
        self.assertEqual(contributions_from_receipts(receipts), [Contribution("hyba", "hyba-data", 10)])


class ReconcileTests(unittest.TestCase):
    def test_balanced_four_designated_participants_reconcile_at_a_quarter(self):
        result = reconcile_value_share(TIER_4, FOUR, ring(), FOUR, period_closed=True)
        for share in result.shares:
            self.assertAlmostEqual(share, 0.25, places=12)
        self.assertGreater(result.perron_root, 0)

    def test_only_tier_four_and_scale(self):
        with self.assertRaises(TierGateRejected):
            reconcile_value_share(TIER_1, FOUR, ring(), FOUR, period_closed=True)
        scale = scale_tier(200_000, 150_000, "HYBA-SCALE-TEST")
        self.assertEqual(len(reconcile_value_share(scale, FOUR, ring(), FOUR, period_closed=True).shares), 4)

    def test_negative_cases_from_the_spec(self):
        with self.assertRaises(VerificationError):
            reconcile_value_share(TIER_4, FOUR, ring(), FOUR[:3], period_closed=True)
        with self.assertRaises(VerificationError):
            reconcile_value_share(TIER_4, FOUR, ring(), FOUR, period_closed=False)
        reducible = [Contribution(n, n, 10) for n in FOUR]
        with self.assertRaises(VerificationError):
            reconcile_value_share(TIER_4, FOUR, reducible, FOUR, period_closed=True)
        unbalanced = ring() + [Contribution("hyba-data", "hyba-data", 500)]
        with self.assertRaises(VerificationError):
            reconcile_value_share(TIER_4, FOUR, unbalanced, FOUR, period_closed=True)
        fifth = ring() + [Contribution("partner", "hyba-data", 1), Contribution("hyba-data", "partner", 1)]
        with self.assertRaises(VerificationError):
            reconcile_value_share(TIER_4, FOUR + ["partner"], fifth, FOUR, period_closed=True)


if __name__ == "__main__":
    unittest.main()
