"""Elevated deep-MCTS tests: multi-depth, transposition, budget, terminals."""
from __future__ import annotations

import unittest

from euclid.search.deep_mcts import DeepMCTSEngine, SearchBudget

CODE = """def compute(values):
    total = []
    for value in values:
        total.append(value * 2)
    return total
"""
PASSING_TEST = "assert compute([1, 2]) == [2, 4]"
FAILING_TEST = "assert compute([1, 2]) == [999]"


class TestDeepMCTS(unittest.TestCase):
    def test_multi_depth_traversal(self) -> None:
        engine = DeepMCTSEngine(seed=11)
        result = engine.search(
            "t.py", CODE,
            budget=SearchBudget(max_evaluations=24, max_depth=4, max_wall_seconds=25.0),
            external_test_code=PASSING_TEST,
        )
        self.assertGreaterEqual(result["max_depth_reached"], 2)
        self.assertGreaterEqual(result["transposition_table_size"], 2)
        self.assertLessEqual(result["evaluations_used"], 24)

    def test_determinism_same_seed(self) -> None:
        def run() -> dict:
            engine = DeepMCTSEngine(seed=11)
            result = engine.search(
                "t.py", CODE,
                budget=SearchBudget(max_evaluations=12, max_depth=3,
                                    max_wall_seconds=25.0),
                external_test_code=PASSING_TEST,
            )
            result.pop("wall_time_ms")
            return result

        self.assertEqual(run(), run())

    def test_failing_tests_are_terminal_never_promoted(self) -> None:
        engine = DeepMCTSEngine(seed=11)
        result = engine.search(
            "t.py", CODE,
            budget=SearchBudget(max_evaluations=10, max_depth=3, max_wall_seconds=25.0),
            external_test_code=FAILING_TEST,
        )
        self.assertEqual(result["best_code"], CODE)
        self.assertEqual(result["measured_improvement"], 0.0)

    def test_phi_is_diagnostic_not_objective(self) -> None:
        engine = DeepMCTSEngine(seed=11)
        result = engine.search(
            "t.py", CODE,
            budget=SearchBudget(max_evaluations=8, max_depth=3, max_wall_seconds=25.0),
            external_test_code=PASSING_TEST,
        )
        self.assertIn("separation_notice", result)
        for entry in result["phi_diagnostics"]:
            self.assertIn("phi_diagnostic", entry)
            self.assertIn("measured_reward", entry)

    def test_trajectory_replay_seeds_priors(self) -> None:
        engine = DeepMCTSEngine(seed=11)
        ingested = engine.ingest_trajectories([["ADD:AnnAssign", "MUTATE:list_comp"]])
        self.assertEqual(ingested, 2)
        self.assertTrue(engine._trajectory_priors)

    def test_budget_is_hard(self) -> None:
        engine = DeepMCTSEngine(seed=11)
        result = engine.search(
            "t.py", CODE,
            budget=SearchBudget(max_evaluations=3, max_depth=4, max_wall_seconds=25.0),
            external_test_code=PASSING_TEST,
        )
        self.assertLessEqual(result["evaluations_used"], 3)


if __name__ == "__main__":
    unittest.main()
