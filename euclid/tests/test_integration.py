"""
Integration Tests: EuclidEngineAdapter Façade & Platform Mechanics v16.0
=============================================================================
Verifies end-to-end adapter operations, property invariants, snapshot telemetry, and ROI governance metrics.
"""

import unittest
from euclid.adapter import EuclidEngineAdapter

class TestIntegrationAdapter(unittest.TestCase):
    def setUp(self):
        self.adapter = EuclidEngineAdapter()

    def test_adapter_analyze(self):
        code = "def process(x: float) -> float:\n    return x * 0.618034"
        res = self.adapter.analyze("test.py", code)
        self.assertEqual(res["file_path"], "test.py")
        self.assertIn("phi_score", res)
        self.assertIn("11d_projection", res)
        self.assertIn("euclid_intelligence", res)

    def test_adapter_evolve_and_verify_invariants(self):
        code = "class Search:\n    def query(self, term):\n        return term in 'content'"
        evolve_res = self.adapter.evolve(
            file_path="search.py",
            code_content=code,
            generations=5,
            seed=42
        )
        self.assertIn("final_code", evolve_res)
        self.assertIn("euclid_intelligence_telemetry", evolve_res)

        invariants_res = self.adapter.verify_property_invariants(
            code_before=code,
            code_after=evolve_res["final_code"],
            topological_time=evolve_res["accepted_steps_count"]
        )
        self.assertTrue(invariants_res["invariants_pass"])

    def test_snapshot_returns_unified_manifold_state(self):
        snap = self.adapter.snapshot()
        self.assertIn("manifold_snapshot", snap)
        self.assertIn("repository_summary", snap)

if __name__ == "__main__":
    unittest.main()
