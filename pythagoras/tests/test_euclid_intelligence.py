"""
Unit & property tests for the EUCLID Intelligence Engine (Lucas L_n, Pisot scaling,
Intelligence = L_n * 20^(phi * t_p)).
"""
import math
import unittest

from pythagoras.core.euclid_intelligence import EuclidIntelligenceEngine, LucasSequenceCalculator, PHI


class TestLucasSequenceCalculator(unittest.TestCase):
    def test_exact_lucas_known_values(self):
        expected = [2, 1, 3, 4, 7, 11, 18, 29, 47, 76, 123]
        for n, exp in enumerate(expected):
            self.assertEqual(LucasSequenceCalculator.exact_lucas(n), exp)

    def test_lucas_recurrence_property(self):
        calc = LucasSequenceCalculator()
        for n in range(2, 31):
            self.assertEqual(calc.exact_lucas(n), calc.exact_lucas(n - 1) + calc.exact_lucas(n - 2))

    def test_pisot_rounding_identity(self):
        """φ is a Pisot number: L_n = round(φ^n) for n >= 2."""
        for n in range(2, 40):
            self.assertEqual(LucasSequenceCalculator.exact_lucas(n), round(PHI ** n))

    def test_continuous_lucas_matches_discrete(self):
        calc = LucasSequenceCalculator()
        for n in range(0, 10):
            self.assertAlmostEqual(calc.exact_lucas(n), calc.continuous_lucas(float(n)), delta=1e-5)

    def test_continuous_lucas_positive_with_known_minimum(self):
        """L(x) > 0 on [0, ∞); its minimum is ≈ 0.913 near x ≈ 0.84 (so '≥ 2' is not a property)."""
        xs = [i / 10000 for i in range(0, 50001)]
        vals = [LucasSequenceCalculator.continuous_lucas(x) for x in xs]
        self.assertGreater(min(vals), 0.0)
        self.assertAlmostEqual(min(vals), 0.9132, places=3)
        k = vals.index(min(vals))
        self.assertTrue(all(b > a for a, b in zip(vals[k:], vals[k + 1:])), "L(x) increasing past its minimum")


class TestEuclidIntelligenceEngine(unittest.TestCase):
    def setUp(self):
        self.engine = EuclidIntelligenceEngine(pisot_base=20.0)

    def test_euclid_ownership_metadata(self):
        res = self.engine.compute_intelligence_scale("x = 42", topological_time=0.0)
        self.assertEqual(res["owner"], "EUCLID_REPO_INTELLIGENCE")
        self.assertIn("Intelligence = L_n * 20^(phi * t_p)", res["scaling_formula"])

    def test_scaling_strictly_increases_with_t_p(self):
        scores = [self.engine.compute_intelligence_scale("def sample(): return 100", t)["intelligence_score"]
                  for t in [0.0, 0.5, 1.0, 2.0, 3.0]]
        self.assertTrue(all(b > a for a, b in zip(scores, scores[1:])))

    def test_t_p_factor_cancels_in_same_time_comparison(self):
        a, b = "def f(x):\n    return x\n", "def f(x: int) -> int:\n    y: int = x + 1\n    return y\n"
        for t in (0.0, 1.0, 4.0):
            ia = self.engine.compute_intelligence_scale(a, t)["intelligence_score"]
            ib = self.engine.compute_intelligence_scale(b, t)["intelligence_score"]
            la = self.engine.lucas_calc.continuous_lucas(self.engine.calculate_lucas_index(a)[1])
            lb = self.engine.lucas_calc.continuous_lucas(self.engine.calculate_lucas_index(b)[1])
            self.assertAlmostEqual(ib / ia, lb / la, places=4)

    def test_positivity_invariant(self):
        """Intelligence > 0 for every input, including the inputs that fall below 2.0."""
        for c in ["", "# Comment only", "pass", "x = 1", "def foo(a: int) -> int: return a + 1",
                  "class Complex:\n    def __init__(self):\n        self.val = 10"]:
            self.assertGreater(self.engine.compute_intelligence_scale(c, 0.0)["intelligence_score"], 0.0)

    def test_dead_code_does_not_raise_lucas_index(self):
        base = "def f(x: int) -> int:\n    return x * 2\n"
        padded = base + "\nif False:\n    unused = 1\n" + "\nx_var: float = 1.0\n" * 6
        self.assertLessEqual(self.engine.calculate_lucas_index(padded)[1],
                             self.engine.calculate_lucas_index(base + "\nx_var: float = 1.0\n")[1] + 1e-9)


if __name__ == "__main__":
    unittest.main()
