"""
Integration tests for PythagorasEngineAdapter: analyze, evolve, persistence, orchestration.
"""
import os
import shutil
import tempfile
import unittest

from pythagoras.adapter import PythagorasEngineAdapter


SAMPLE = (
    "class DataEngine:\n"
    "    def __init__(self, name: str):\n"
    "        self.name = name\n"
    "        self.data = []\n\n"
    "    def process(self, val: int) -> int:\n"
    "        self.data.append(val)\n"
    "        return val * 2\n"
)


class TestPythagorasAdapterIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.repo_path = os.path.join(self.temp_dir, "test_primitive_repo.json")
        self.adapter = PythagorasEngineAdapter(persistent_repo_path=self.repo_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_analyze_contract(self):
        a = self.adapter.analyze("data_engine.py", SAMPLE, topological_time=1.0)
        self.assertEqual(a["file_path"], "data_engine.py")
        self.assertEqual(a["euclid_intelligence"]["owner"], "EUCLID_REPO_INTELLIGENCE")
        self.assertEqual(len(a["11d_projection"]), 11)
        self.assertEqual(a["11d_projection"], list(a["11d_state"].values()))
        self.assertTrue(all(0.0 <= v <= 1.0 for v in a["11d_projection"]))

    def test_evolve_telemetry_uses_same_t_p(self):
        r = self.adapter.evolve("data_engine.py", SAMPLE, generations=5, seed=42, topological_time=2.0)
        tel = r["euclid_intelligence_telemetry"]
        self.assertEqual(tel["initial_intelligence"]["topological_time_t_p"], 2.0)
        self.assertEqual(tel["final_intelligence"]["topological_time_t_p"], 2.0)
        self.assertEqual(r["final_code_sample"], r["final_code"])
        # EUCLID co-gate: intelligence never decreases across accepted steps
        self.assertGreaterEqual(tel["intelligence_gain_ratio"], 1.0)
        # ratio is bounded by the code change, not by the number of steps
        self.assertLess(tel["intelligence_gain_ratio"], 10.0)

    def test_commit_primitive_recipe_persists_and_works(self):
        self.adapter.commit_primitive("HOST:AnnotateThenHeal", "ADD:AnnAssign + HEAL:dead_code_elimination", "repo_A")
        self.assertIn("HOST:AnnotateThenHeal", self.adapter.snapshot()["repository_summary"]["primitives_detail"])

        restored = PythagorasEngineAdapter(persistent_repo_path=self.repo_path)
        meta = restored.snapshot()["repository_summary"]["primitives_detail"]["HOST:AnnotateThenHeal"]
        self.assertTrue(meta["restorable"])
        op = restored.repository.primitive_functions["HOST:AnnotateThenHeal"]
        out, name = op("def f():\n    n = len([1])\n    return n\n\nif False:\n    z = 1\n", 0)
        self.assertIn("n: int = len([1])", out)
        self.assertNotIn("if False", out)

    def test_commit_primitive_rejects_unknown_operators(self):
        with self.assertRaises(ValueError):
            self.adapter.commit_primitive("HOST:Bad", "dummy_code", "repo_A")

    def test_orchestration_shares_adapter_manifold(self):
        res = self.adapter.orchestrate([{"name": "data_engine.py", "code_str": SAMPLE}], generations=3)
        snap = self.adapter.snapshot()["manifold_snapshot"]
        self.assertEqual(snap["total_entanglement_events"], 4)
        self.assertEqual(snap["security_audits_count"], 1)
        self.assertIsNotNone(snap["dual_symmetry_coherence"])
        self.assertIn("data_engine.py", res["session_results"])


if __name__ == "__main__":
    unittest.main()
