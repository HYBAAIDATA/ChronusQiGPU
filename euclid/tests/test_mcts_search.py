"""
Unit Tests: Monte Carlo Tree Search (MCTS) Engine & PUCT Dynamics v16.0
"""

import unittest
from euclid.search.mcts_search import MCTSSearchEngine, MCTSNode
from euclid.adapter import EuclidEngineAdapter

class TestMCTSSearchEngine(unittest.TestCase):
    def setUp(self):
        self.engine = MCTSSearchEngine(seed=42, c_puct=1.5)
        self.adapter = EuclidEngineAdapter()

    def test_mcts_node_puct_calculation(self):
        parent = MCTSNode(state_code="x = 1")
        parent.visit_count = 10
        
        child = MCTSNode(state_code="x = 1\ny = 2", parent=parent, action_taken="ADD:AnnAssign", prior_prob=0.8)
        child.visit_count = 2
        child.total_value = 0.10
        child.mean_value = 0.05
        
        puct = child.puct_score(c_puct=1.5)
        # Q = 0.05, U = 1.5 * 0.8 * sqrt(10) / (1 + 2) = 1.2 * 3.16227 / 3 = 1.2649
        self.assertGreater(puct, 1.0)

    def test_policy_priors_probability_distribution(self):
        code = "def f(x):\n    return x + 1"
        priors = self.engine._compute_policy_priors(code, self.engine.base_operators)
        
        self.assertIn("ADD:AnnAssign", priors)
        self.assertIn("NON_LOCAL:function_split_refactor", priors)
        # Verify probability distribution sums to ~1.0
        total_prob = sum(priors.values())
        self.assertAlmostEqual(total_prob, 1.0, places=4)

    def test_mcts_search_execution(self):
        code = "class Search:\n    def query(self, term):\n        return term in 'content'"
        res = self.engine.run_mcts_search(
            target_name="search.py",
            initial_code=code,
            max_generations=5,
            num_simulations_per_gen=3
        )
        
        self.assertEqual(res["search_mode"], "MCTS_PUCT_POLICY_PRIORS")
        self.assertGreaterEqual(res["final_phi"], res["initial_phi"])
        self.assertIn("final_code", res)

    def test_adapter_mcts_mode_integration(self):
        code = "def calc(x):\n    return x * 2.0"
        res = self.adapter.evolve(
            file_path="calc.py",
            code_content=code,
            generations=5,
            seed=42,
            mode="mcts"
        )
        self.assertIn("euclid_intelligence_telemetry", res)
        self.assertIn("search_mode", res)
        self.assertEqual(res["search_mode"], "MCTS_PUCT_POLICY_PRIORS")

if __name__ == "__main__":
    unittest.main()
