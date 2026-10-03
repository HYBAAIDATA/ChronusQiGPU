"""
Unit Tests: AST Delta Extraction & Primitive Discovery v16.0
=============================================================
Verifies structural AST diff extraction, AST NodeTransformer rule generation, and generalization promotion gates.
"""

import unittest
from euclid.discovery.ast_delta_discovery import ASTDeltaDiscoveryEngine

class TestASTDeltaDiscovery(unittest.TestCase):
    def setUp(self):
        self.engine = ASTDeltaDiscoveryEngine()

    def test_ast_diff_extraction(self):
        before = "x = 10"
        after = "x: float = 10"
        diff = self.engine.extract_ast_diff(before, after)
        
        self.assertIn("AnnAssign", diff["added_nodes"])
        self.assertIn("pattern_hash", diff)

    def test_discover_primitive_and_promotion_gate(self):
        before = "x = 10"
        after = "x: float = 10"
        
        cand = self.engine.discover_from_transformation(before, after, "ADD:AnnAssign", gen=1, target_name="test.py")
        self.assertIsNotNone(cand)
        self.assertFalse(cand.is_promoted)

        # Trial 1: Success
        cand.record_trial(delta_phi=0.010, parse_v=True, test_v=True)
        self.assertFalse(cand.check_promotion_eligibility())

        # Trial 2: Success -> Eligible for promotion!
        cand.record_trial(delta_phi=0.005, parse_v=True, test_v=True)
        self.assertTrue(cand.check_promotion_eligibility())

if __name__ == "__main__":
    unittest.main()
