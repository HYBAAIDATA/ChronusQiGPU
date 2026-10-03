"""
Unit Tests: EUCLID Structural Complexity Metric & Lucas Scale v16.0
===================================================================
Verifies Lucas sequence calculation, Non-Degeneracy Invariant (L_n >= 2.0), and dimension separation.
"""

import unittest
from euclid.core.euclid_intelligence import EuclidIntelligenceEngine, LucasSequenceCalculator

class TestEuclidIntelligence(unittest.TestCase):
    def setUp(self):
        self.engine = EuclidIntelligenceEngine()

    def test_lucas_sequence_recurrence(self):
        # L_0=2, L_1=1, L_2=3, L_3=4, L_4=7, L_5=11, L_6=18, L_7=29
        expected = [2, 1, 3, 4, 7, 11, 18, 29]
        for idx, val in enumerate(expected):
            self.assertEqual(LucasSequenceCalculator.exact_lucas(idx), val)

    def test_non_degeneracy_invariant_minimalist_code(self):
        minimalist_codes = ["pass", "x = 1", "def f(): pass"]
        for code in minimalist_codes:
            metrics = self.engine.compute_intelligence_metrics(code)
            struct_intel = metrics["structural_complexity_L_n"]
            self.assertGreaterEqual(struct_intel, 2.0, f"Code '{code}' violated non-degeneracy invariant: {struct_intel}")

    def test_disentangled_dimensions(self):
        code = "def f(x: float) -> float:\n    return x * 2.0"
        metrics = self.engine.compute_intelligence_metrics(code, topological_time=3.0)
        
        self.assertIn("structural_complexity_L_n", metrics)
        self.assertIn("topological_time_t_p", metrics)
        self.assertIn("composite_time_projected_scale", metrics)
        
        self.assertEqual(metrics["topological_time_t_p"], 3.0)
        self.assertGreaterEqual(metrics["structural_complexity_L_n"], 2.0)

    def test_negative_topological_time_clamping(self):
        code = "x = 1"
        metrics = self.engine.compute_intelligence_metrics(code, topological_time=-5.0)
        self.assertEqual(metrics["topological_time_t_p"], 0.0)

if __name__ == "__main__":
    unittest.main()
