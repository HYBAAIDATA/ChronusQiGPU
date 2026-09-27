import unittest
from mla1517.scale import ScaleBudget, ScaleController, ScalePoint, parse_scale_token


class ScaleTests(unittest.TestCase):
    def test_arbitrary_scale_ladder(self):
        c = ScaleController(ScaleBudget(max_index=100, max_work_units=10000))
        decisions = c.plan([ScalePoint(n) for n in [10, 12, 15, 18, 20, 31, 50, 76]])
        self.assertTrue(all(d.accepted for d in decisions))
        self.assertEqual(c.execute_exact(ScalePoint(15))["lucas"], 1364)

    def test_estimate_is_conservative_for_exact_values(self):
        c = ScaleController()
        for n in [1, 10, 15, 31, 76]:
            d = c.authorize(ScalePoint(n))
            self.assertGreaterEqual(
                d.estimate.logical_state_bits,
                (
                    c.execute_exact(ScalePoint(n))["fibonacci"].bit_length()
                    + c.execute_exact(ScalePoint(n))["lucas"].bit_length()
                ),
            )

    def test_physical_budget_rejects_large_state(self):
        c = ScaleController(ScaleBudget(max_index=10000, max_physical_bytes=300))
        d = c.authorize(ScalePoint(1000))
        self.assertFalse(d.accepted)
        self.assertEqual(d.reason, "physical_budget_exceeded")

    def test_work_budget_rejects_large_scale(self):
        c = ScaleController(ScaleBudget(max_index=100, max_work_units=100))
        d = c.authorize(ScalePoint(50))
        self.assertFalse(d.accepted)
        self.assertEqual(d.reason, "work_budget_exceeded")

    def test_step_limit(self):
        c = ScaleController(ScaleBudget(max_steps=2))
        with self.assertRaises(ValueError):
            c.plan([ScalePoint(1), ScalePoint(2), ScalePoint(3)])

    def test_power_descriptor_and_nested_rejection(self):
        p = parse_scale_token("10^12")
        self.assertEqual((p.base, p.exponent, p.index), (10, 12, 12))
        with self.assertRaises(ValueError):
            parse_scale_token("10^12^15")


if __name__ == "__main__":
    unittest.main(verbosity=2)
