"""The traversal adapter reads the real successors and does not invent probes."""

from __future__ import annotations

import unittest
from fractions import Fraction
from pathlib import Path

from aethel.overhead import price_addresses
from kellogg.scales import fibonacci
from kellogg.traversal import TRAVERSAL_STRIDE, coverage_certificate
from benchmarks.traversal_map import (
    HORIZON,
    LARGE_JUMP,
    PROBE_ORDER,
    SCAN_MODULUS,
    characterize,
    lucas_phi_32,
    render_reports,
)


ROOT = Path(__file__).resolve().parents[1]


class AdapterTests(unittest.TestCase):
    def test_lucas_walk_is_the_certified_face_stride(self):
        addresses = lucas_phi_32()
        self.assertEqual(addresses, coverage_certificate(HORIZON).faces)
        self.assertEqual(TRAVERSAL_STRIDE, 5)
        self.assertEqual(len(set(addresses)), 32)

    def test_every_named_traversal_has_one_reproducible_row(self):
        first = characterize()
        second = characterize()
        self.assertEqual([row.name for row in first], list(PROBE_ORDER))
        self.assertEqual(first, second)

    def test_integrable_circle_walks_have_exact_zero_probes(self):
        rows = {row.name: row for row in characterize()}
        for name in ("lucas_phi_32", "sequential", "korobov_d1", "chirikov_k0_control"):
            row = rows[name]
            self.assertEqual(row.lyapunov, Fraction(0))
            self.assertEqual(row.greene, Fraction(0))
            self.assertEqual(row.action_variance, Fraction(0))
            self.assertIs(row.period1, False)
        self.assertIs(rows["morton"].greene, None)
        self.assertIs(rows["korobov_d3"].greene, None)
        self.assertIs(rows["uniform_random"].lyapunov, None)
        self.assertIs(rows["uniform_random"].greene, None)
        self.assertEqual(rows["sequential"].addresses, rows["korobov_d1"].addresses)
        self.assertEqual(rows["cassini_index"].lyapunov_status, "log(phi)")
        self.assertIs(rows["cassini_index"].period1, True)
        self.assertEqual(fibonacci(1), fibonacci(2))

    def test_aethel_cost_is_the_address_sum(self):
        for row in characterize():
            if row.name == "chirikov_k0_control":
                self.assertEqual(row.jump_sum, 0)
                continue
            ledger = price_addresses(row.addresses, label=row.name)
            self.assertEqual(row.jump_sum, ledger.miss_cost)
            self.assertEqual(row.jump_count, len(row.addresses) - 1)
            self.assertEqual(
                row.large_jumps,
                sum(
                    1
                    for left, right in zip(row.addresses, row.addresses[1:])
                    if abs(right - left) > LARGE_JUMP
                ),
            )
        self.assertEqual(SCAN_MODULUS, 64)

    def test_published_tables_match_the_measurement(self):
        rendered = render_reports()
        for relative, text in rendered.items():
            path = ROOT / relative
            self.assertTrue(path.is_file(), relative)
            self.assertEqual(path.read_text(encoding="utf-8"), text)
            for name in PROBE_ORDER:
                self.assertIn(name, text)


if __name__ == "__main__":
    unittest.main()
