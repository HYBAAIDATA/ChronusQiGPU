"""Unit and integration tests for ARC-AGI-1 EUCLID adapter and evaluation suite."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from euclid.benchmarks.arc_agi_1.arc_euclid_adapter import (
    encode_grid_to_features,
    encode_task_arc_to_euclid,
    features_to_grid,
)
from euclid.benchmarks.arc_agi_1.arc_world import (
    ArcDemonstrationWorld,
    build_spec,
    execute_program,
)
from euclid.benchmarks.arc_agi_1.grid_primitives import (
    apply_unary,
    fit_colour_map,
    fit_constant_output,
    flip_h,
    rot90,
)
from euclid.benchmarks.arc_agi_1.output_validation import public_task, score_grid
from euclid.benchmarks.arc_agi_1.score_arc import score
from euclid.cognition.worlds.world import BudgetExhausted


class TestArcEuclidAdapter(unittest.TestCase):
    def setUp(self) -> None:
        self.sample_grid = [
            [1, 2, 0],
            [0, 1, 0],
            [0, 0, 3],
        ]
        self.sample_task = {
            "id": "test_sample_01",
            "train": [
                {
                    "input": [[1, 0], [0, 2]],
                    "output": [[2, 0], [0, 1]],
                }
            ],
            "test": [
                {
                    "input": [[3, 0], [0, 4]],
                    "output": [[4, 0], [0, 3]],
                }
            ],
        }

    def test_encode_grid_to_features(self) -> None:
        features = encode_grid_to_features(self.sample_grid)
        self.assertIsInstance(features, dict)
        self.assertEqual(features["grid_rows"], 3)
        self.assertEqual(features["grid_cols"], 3)
        self.assertEqual(features["grid_total_cells"], 9)
        self.assertIn("phi_resonance", features)
        self.assertIn("color_ratio_1", features)
        self.assertIn("color_ratio_2", features)
        self.assertIn("color_ratio_3", features)

    def test_features_to_grid(self) -> None:
        features = encode_grid_to_features(self.sample_grid)
        grid = features_to_grid(features, grid_shape=(3, 3))
        self.assertIsInstance(grid, list)
        self.assertEqual(len(grid), 3)
        self.assertEqual(len(grid[0]), 3)
        for row in grid:
            for cell in row:
                self.assertIsInstance(cell, int)
                self.assertTrue(0 <= cell <= 9)

    def test_grid_primitives(self) -> None:
        g = [[1, 2], [3, 4]]
        r = rot90(g)
        self.assertEqual(r, [[3, 1], [4, 2]])
        f = flip_h(g)
        self.assertEqual(f, [[2, 1], [4, 3]])
        u = apply_unary("rot90", g)
        self.assertEqual(u, [[3, 1], [4, 2]])

    def test_fitted_primitives(self) -> None:
        train_pairs = [
            ([[1, 2], [3, 4]], [[5, 6], [7, 8]])
        ]
        cmap = fit_colour_map(train_pairs)
        self.assertEqual(cmap[1], 5)
        self.assertEqual(cmap[2], 6)

        const = fit_constant_output(train_pairs)
        self.assertEqual(const, [[5, 6], [7, 8]])

    def test_answer_isolation_public_task(self) -> None:
        pub = public_task(self.sample_task, "test_sample_01")
        self.assertEqual(pub["task_id"], "test_sample_01")
        self.assertEqual(len(pub["train"]), 1)
        self.assertIn("input", pub["train"][0])
        self.assertIn("output", pub["train"][0])
        self.assertEqual(len(pub["test"]), 1)
        self.assertIn("input", pub["test"][0])
        self.assertNotIn("output", pub["test"][0])

    def test_arc_demonstration_world_budgets(self) -> None:
        pairs = [([[1, 0], [0, 2]], [[2, 0], [0, 1]])]
        spec = build_spec("task_test", pairs, probe_budget=2, submission_budget=1)
        world = ArcDemonstrationWorld(spec, pairs)

        p1 = world.probe(["rot90"])
        self.assertEqual(p1["probes_remaining"], 1)
        p2 = world.probe(["flip_h"])
        self.assertEqual(p2["probes_remaining"], 0)

        with self.assertRaises(BudgetExhausted):
            world.probe(["rot90"])

        s1 = world.submit(["rot90"])
        self.assertEqual(s1["submissions_remaining"], 0)
        with self.assertRaises(BudgetExhausted):
            world.submit(["rot90"])

    def test_scorer_with_perfect_and_wrong_submissions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            t1 = {
                "train": [{"input": [[0]], "output": [[1]]}],
                "test": [{"input": [[2]], "output": [[3]]}],
            }
            (tmp / "t1.json").write_text(json.dumps(t1), encoding="utf-8")

            # Perfect submission
            sub_correct = {"t1": [{"attempt_1": [[3]], "attempt_2": [[0]]}]}
            res = score(sub_correct, tmp)
            self.assertEqual(res["tasks_in_split"], 1)
            self.assertEqual(res["strict_tasks_solved"], 1)
            self.assertEqual(res["arc_prize_score"], 1.0)

            # Wrong submission
            sub_wrong = {"t1": [{"attempt_1": [[0]], "attempt_2": [[1]]}]}
            res_wrong = score(sub_wrong, tmp)
            self.assertEqual(res_wrong["tasks_in_split"], 1)
            self.assertEqual(res_wrong["strict_tasks_solved"], 0)
            self.assertEqual(res_wrong["arc_prize_score"], 0.0)

            # Missing submission
            res_missing = score({}, tmp)
            self.assertEqual(res_missing["tasks_in_split"], 1)
            self.assertEqual(res_missing["strict_tasks_solved"], 0)
            self.assertEqual(res_missing["denominator"], "all tasks in split")


if __name__ == "__main__":
    unittest.main()
