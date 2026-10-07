"""Offline check of the blockstream headers. No nonce is generated here."""

from __future__ import annotations

import unittest
from pathlib import Path

from mining.public_headers import render, survey


ROOT = Path(__file__).resolve().parents[1]


class PublicApiNonceTests(unittest.TestCase):
    def test_every_stored_header_meets_its_own_target(self):
        result = survey()
        self.assertEqual(result["checked"], 1640)
        self.assertEqual(result["pow_fail"], 0)
        self.assertEqual(result["zero_nonce_meets"], 0)
        self.assertEqual(result["chain_breaks"], 0)
        self.assertEqual(result["nonce_805000"], 2431510578)
        self.assertEqual(
            result["bits_runs"],
            [
                (805000, 805009, 386207611),
                (808370, 808415, 386216622),
                (808416, 809999, 386198911),
            ],
        )

    def test_report_matches_the_survey(self):
        path = ROOT / "reports" / "public_api_nonce_check.md"
        self.assertEqual(path.read_text(encoding="utf-8"), render())


if __name__ == "__main__":
    unittest.main()
