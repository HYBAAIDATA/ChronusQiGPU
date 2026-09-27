"""Executable positive tests for the MLA1517 scaling contract."""

import math
import unittest
from mla1517.core import lucas, fib_pair
from mla1517.scale import ScaleBudget, ScaleController, ScalePoint, parse_scale_token


class CapabilityTests(unittest.TestCase):
    def test_lucas_growth_follows_dominant_root(self):
        # L_(n+k)/L_n -> phi^k; this tests the actual Lucas growth law.
        phi = (1 + math.sqrt(5.0)) / 2.0
        n, k = 100, 20
        measured = lucas(n + k) / lucas(n)
        expected = phi**k
        self.assertLess(abs(measured / expected - 1.0), 1e-12)

    def test_scale_controller_is_not_catalogue_limited(self):
        c = ScaleController(
            ScaleBudget(max_index=2048, max_work_units=10_000_000, max_physical_bytes=10_000_000)
        )
        points = [ScalePoint(n) for n in [10, 12, 15, 18, 20, 31, 50, 76, 128, 256, 512, 1024]]
        self.assertTrue(all(d.accepted for d in c.plan(points)))
        magnitudes = [c.estimate(p).math_magnitude_log10 for p in points]
        self.assertEqual(magnitudes, sorted(magnitudes))

    def test_exact_state_scales_without_float_storage(self):
        for n in [15, 31, 50, 76]:
            a, b = fib_pair(n)
            self.assertEqual(b - a, fib_pair(n - 1)[0])
            self.assertGreater(a, 0)

    def test_power_scaling_is_structured(self):
        p = parse_scale_token("10^12")
        self.assertEqual(p.base, 10)
        self.assertEqual(p.exponent, 12)
        self.assertEqual(p.label, "10^12")


if __name__ == "__main__":
    unittest.main(verbosity=2)
