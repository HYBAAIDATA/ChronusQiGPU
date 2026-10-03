"""
Unit Tests: Structural Resonance, Dangerous Code Penalty & Anti-Goodhart Guards v16.0
=======================================================================================
Verifies safety penalties, anti-Goodhart dead-node bloat guards, and target phi alignment.
"""

import unittest
from euclid.core.phi_metric import PhiResonanceCalculator

class TestPhiMetricAndGoodhart(unittest.TestCase):
    def setUp(self):
        self.calculator = PhiResonanceCalculator(target_phi=0.618033988749895)

    def test_dangerous_code_receives_zero_fitness(self):
        dangerous_codes = [
            "import os\nos.system('ls')",
            "eval('1+1')",
            "open('/etc/passwd')",
            "exec('x = 1')",
            "import subprocess\nsubprocess.Popen(['ls'])"
        ]
        for code in dangerous_codes:
            score = self.calculator.compute_phi(code)
            self.assertEqual(score, 0.0000, f"Dangerous code received non-zero score: {code}")

    def test_target_phi_participation(self):
        code = "def f(x):\n    return x + 1"
        
        calc_0618 = PhiResonanceCalculator(target_phi=0.618033988749895)
        calc_0200 = PhiResonanceCalculator(target_phi=0.200000000000000)
        
        score_0618 = calc_0618.compute_phi(code)
        score_0200 = calc_0200.compute_phi(code)
        
        self.assertNotEqual(score_0618, score_0200)

    def test_anti_bloat_dead_node_penalty(self):
        small_code = "def f(x):\n    return x + 1"
        
        # Artificial bloat code with unreferenced dummy variables
        bloat_lines = ["def f(x):"] + [f"    dummy_{i}: float = {i}" for i in range(120)] + ["    return x + 1"]
        bloated_code = "\n".join(bloat_lines)
        
        small_score = self.calculator.compute_phi(small_code)
        bloated_score = self.calculator.compute_phi(bloated_code)
        
        # Bloated code must receive lower score due to dead-node penalty
        self.assertLess(bloated_score, small_score)

    def test_failed_tests_receive_zero_multi_objective_fitness(self):
        code = "def f(x):\n    return x + 1"
        fitness_failed = self.calculator.compute_multi_objective_fitness(code, tests_passed=False)
        fitness_passed = self.calculator.compute_multi_objective_fitness(code, tests_passed=True)
        
        self.assertEqual(fitness_failed, 0.0000)
        self.assertGreater(fitness_passed, 0.0)

if __name__ == "__main__":
    unittest.main()
