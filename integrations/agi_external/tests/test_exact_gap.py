"""Tests verifying boundary isolation and exact gap computation for ExternalAGI."""

from __future__ import annotations

import unittest

from integrations.agi_external import ExternalAGI, EXTERNAL_AGI_CAPABILITIES
from millennium.exact_gap import exact_gap_from_class_algebra


class TestExactGapExternalBoundary(unittest.TestCase):
    def test_yang_mills_not_in_external_capabilities(self) -> None:
        """Yang-Mills and P vs NP must remain internal per directive."""
        agi = ExternalAGI()
        caps = agi.capabilities()
        self.assertNotIn("yang_mills", caps)
        self.assertNotIn("p_vs_np", caps)
        self.assertIn("bsd_conjecture", caps)

    def test_exact_gap_algebraic_consistency(self) -> None:
        """The mathematical exactness of the finite mass gap holds."""
        gap_record = exact_gap_from_class_algebra()
        self.assertTrue(gap_record.verify_exact())
        self.assertEqual(gap_record.gap_exact_form, (3, -1))
        self.assertEqual(gap_record.k, 4)
        self.assertEqual(gap_record.dimension, 2)


if __name__ == "__main__":
    unittest.main()
