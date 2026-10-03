"""
Unit Tests: Semantic Equivalence & Behavioral Regression v16.0
==============================================================
Verifies that AST transformations preserve program arithmetic and behavioral correctness.
"""

import unittest
from euclid.core.primitives import ASTPrimitives
from euclid.validation.process_sandbox import IsolatedProcessEvaluator

class TestSemanticEquivalence(unittest.TestCase):
    def setUp(self):
        self.evaluator = IsolatedProcessEvaluator(timeout_sec=1.0)

    def test_type_annotation_preserves_semantics(self):
        code = "def calc(x):\n    y = x * 2.0\n    return y\nres = calc(5.0)"
        mutated, op = ASTPrimitives.apply_type_annotations(code)
        
        # Verify mutated AST is valid and runs to same result
        p_v, c_v, r_v, msg = self.evaluator.evaluate_validity(mutated)
        self.assertTrue(r_v, f"Failed execution: {msg}")
        self.assertTrue("-> float" in mutated or "y: float" in mutated)

    def test_operator_swap_alters_semantics_detected_by_tests(self):
        code = "def add(a, b):\n    return a + b"
        mutated, op = ASTPrimitives.swap_operators(code)
        
        # Unit test verifying addition
        test_code = f"{mutated}\nassert add(2, 3) == 5"
        p_v, c_v, r_v, msg = self.evaluator.evaluate_validity(test_code)
        
        # Operator swap (Add -> Sub) must fail the behavioral assertion!
        self.assertFalse(r_v)
        self.assertIn("AssertionError", msg)

    def test_list_comp_optimization_preserves_semantics(self):
        code = "items = [1, 2, 3]\nres = []\nfor i in items:\n    res.append(i * 2)\nassert res == [2, 4, 6]"
        mutated, op = ASTPrimitives.list_comp_optimization(code)
        
        p_v, c_v, r_v, msg = self.evaluator.evaluate_validity(mutated)
        self.assertTrue(r_v, f"Failed execution: {msg}")

if __name__ == "__main__":
    unittest.main()
