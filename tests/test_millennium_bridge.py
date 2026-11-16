"""Millennium bridge: checkable readings that cite GoldenArithmetic."""

from __future__ import annotations

import math
import unittest

from chronus.math.unified_quantum_engine import GoldenArithmetic
from chronus.research.millennium_bridge import (
    PHI,
    arccosh_sqrt5_over_2_is_ln_phi,
    betti_1,
    bridge,
    modular_geodesic,
    self_test,
    wilson_gap,
)


class GoldenArithmeticTests(unittest.TestCase):
    def test_lucas_and_cassini(self) -> None:
        self.assertEqual(GoldenArithmetic.lucas(1), 1)
        self.assertEqual(GoldenArithmetic.lucas(2), 3)
        self.assertEqual(GoldenArithmetic.cassini(7), -1)
        self.assertEqual(GoldenArithmetic.cassini(8), 1)


class MillenniumBridgeTests(unittest.TestCase):
    def test_self_test_and_seven_readings(self) -> None:
        self_test()
        readings = bridge()
        self.assertEqual(len(readings), 7)
        links = {item.link for item in readings}
        self.assertIn("PROVED", links)
        self.assertIn("OPEN", links)
        self.assertIn("ANALOGY", links)
        for item in readings:
            self.assertTrue(item.quantity)
            self.assertTrue(item.note)
            self.assertTrue(item.problem)

    def test_modular_systole_not_figure_eight_claim(self) -> None:
        # Arithmetic identity holds; figure-eight systole claim does not.
        self.assertAlmostEqual(
            arccosh_sqrt5_over_2_is_ln_phi(), math.log(PHI), places=12
        )
        self.assertAlmostEqual(modular_geodesic(1), 4 * math.log(PHI), places=12)
        # Known figure-eight systole ≈ 1.087; modular is ≈ 1.9248.
        self.assertGreater(modular_geodesic(1), 1.5)
        self.assertNotAlmostEqual(2 * math.log(PHI), 1.08707, places=2)

    def test_hodge_and_wilson(self) -> None:
        self.assertEqual(betti_1(3, [(0, 1), (1, 2), (0, 2)], []), 1)
        self.assertEqual(betti_1(3, [(0, 1), (1, 2), (0, 2)], [(0, 1, 2)]), 0)
        # Reversed listed edge still matches the face that walks 0→1.
        self.assertEqual(betti_1(3, [(1, 0), (1, 2), (0, 2)], [(0, 1, 2)]), 0)
        self.assertGreater(wilson_gap(2), wilson_gap(4))
        self.assertGreater(wilson_gap(4), wilson_gap(8))


if __name__ == "__main__":
    unittest.main()
