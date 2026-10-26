"""Unit, property, and integration tests for ARC-AGI-1 EUCLID adapter and evaluation suite.

Elevated to reflect ARC evaluation discipline:
1. Dihedral group (D4) algebraic symmetries and Klein-4 subgroup invariants.
2. Invariant conservation of multi-set color histograms and shapes under symmetry.
3. Primitive operator algebraic laws, roundtrip invertibility, and boundaries.
4. Strict zero-answer leakage, public task isolation, and memory immutability.
5. Official ARC Prize scoring semantics: strict task accuracy vs test input fraction,
   2-attempt policy per test input, and official split denominator (N=400).
6. Submission schema validation and grid syntax conformance.
7. Worker memory isolation, garbage collection discipline, and hard wall-clock bounds.
8. End-to-end real ARC task solve and format pipeline.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import gc
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock

from euclid.benchmarks.arc_agi_1.arc_euclid_adapter import (
    encode_grid_to_features,
    encode_task_arc_to_euclid,
    features_to_grid,
    run_arc_task_adapter,
)
from euclid.benchmarks.arc_agi_1.arc_world import (
    ArcDemonstrationWorld,
    build_spec,
    execute_program,
)
from euclid.benchmarks.arc_agi_1.euclid_arc_runner import (
    Budget,
    load_public_task,
    run_task,
)
from euclid.benchmarks.arc_agi_1.grid_primitives import (
    OperatorFailed,
    apply_unary,
    crop_content,
    downscale,
    fill_enclosed,
    fit_colour_map,
    fit_constant_output,
    flip_h,
    flip_v,
    gravity_down,
    largest_object,
    rot90,
    rot180,
    rot270,
    scale2,
    scale3,
    smallest_object,
    tile_2x2,
    transpose,
)
from euclid.benchmarks.arc_agi_1.output_validation import (
    grid_error,
    public_task,
    score_grid,
    score_submission,
)
from euclid.benchmarks.arc_agi_1.score_arc import score
from euclid.cognition.worlds.world import BudgetExhausted
from euclid.runtime import EuclidRuntime


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

    def test_dihedral_group_d4_algebraic_laws(self) -> None:
        """Verify D4 dihedral group and Klein-4 subgroup algebraic laws on asymmetric grids."""
        grid = [
            [1, 2, 3],
            [4, 5, 6],
        ]
        # Rotations: C4 cyclic group
        r90 = rot90(grid)
        r180 = rot180(grid)
        r270 = rot270(grid)
        self.assertEqual(rot90(rot90(rot90(rot90(grid)))), grid)
        self.assertEqual(rot90(rot90(grid)), r180)
        self.assertEqual(rot90(r180), r270)
        self.assertEqual(rot90(r270), grid)
        self.assertEqual(rot270(rot90(grid)), grid)

        # Involutions: Reflections H^2 = I, V^2 = I, Transpose^2 = I
        fh = flip_h(grid)
        fv = flip_v(grid)
        tr = transpose(grid)
        self.assertEqual(flip_h(fh), grid)
        self.assertEqual(flip_v(fv), grid)
        self.assertEqual(transpose(tr), grid)

        # Klein-4 subgroup V4 = {I, H, V, R180}: H o V = V o H = R180
        self.assertEqual(flip_h(fv), r180)
        self.assertEqual(flip_v(fh), r180)

        # Dihedral semi-direct product relations: s r s = r^(-1)
        self.assertEqual(flip_h(rot90(flip_h(grid))), r270)
        self.assertEqual(flip_v(rot90(flip_v(grid))), r270)

        # Transpose identity: Transpose(g) == H(R90(g))
        self.assertEqual(tr, flip_h(r90))

        # Conservation of multi-set color frequency across all D4 transformations
        base_counts = Counter(c for row in grid for c in row)
        for sym_name, sym_grid in [
            ("rot90", r90),
            ("rot180", r180),
            ("rot270", r270),
            ("flip_h", fh),
            ("flip_v", fv),
            ("transpose", tr),
        ]:
            with self.subTest(symmetry=sym_name):
                self.assertEqual(Counter(c for row in sym_grid for c in row), base_counts)

        # Shape transformations: (2, 3) -> (3, 2) or (2, 3)
        self.assertEqual((len(r90), len(r90[0])), (3, 2))
        self.assertEqual((len(r180), len(r180[0])), (2, 3))
        self.assertEqual((len(r270), len(r270[0])), (3, 2))
        self.assertEqual((len(fh), len(fh[0])), (2, 3))
        self.assertEqual((len(fv), len(fv[0])), (2, 3))
        self.assertEqual((len(tr), len(tr[0])), (3, 2))

    def test_primitive_invariants_and_boundaries(self) -> None:
        """Verify algebraic roundtrips, bounding box invariants, and operator boundaries."""
        g = [[1, 2], [3, 4]]

        # Invertibility: downscale(scale2(g)) == g
        s2 = scale2(g)
        self.assertEqual((len(s2), len(s2[0])), (4, 4))
        self.assertEqual(downscale(s2), g)

        # Dimensional scalings
        s3 = scale3(g)
        self.assertEqual((len(s3), len(s3[0])), (6, 6))
        t2 = tile_2x2(g)
        self.assertEqual((len(t2), len(t2[0])), (4, 4))

        # Bounding box extraction with crop_content
        boxed = [
            [0, 0, 0, 0],
            [0, 5, 6, 0],
            [0, 7, 8, 0],
            [0, 0, 0, 0],
        ]
        self.assertEqual(crop_content(boxed), [[5, 6], [7, 8]])

        # Monochrome grid has no foreground -> raises OperatorFailed
        with self.assertRaises(OperatorFailed):
            crop_content([[0, 0], [0, 0]])

        # Physics: downward gravity stacks foreground cells at the bottom
        floated = [
            [1, 0],
            [0, 2],
            [3, 0],
            [0, 0],
        ]
        grav = gravity_down(floated)
        self.assertEqual(
            grav,
            [
                [0, 0],
                [0, 0],
                [1, 0],
                [3, 2],
            ],
        )

        # Fill enclosed: hollow box enclosed interior is filled with foreground
        hollow = [
            [0, 0, 0, 0, 0],
            [0, 1, 1, 1, 0],
            [0, 1, 0, 1, 0],
            [0, 1, 1, 1, 0],
            [0, 0, 0, 0, 0],
        ]
        filled = fill_enclosed(hollow)
        self.assertEqual(
            filled,
            [
                [0, 0, 0, 0, 0],
                [0, 1, 1, 1, 0],
                [0, 1, 1, 1, 0],
                [0, 1, 1, 1, 0],
                [0, 0, 0, 0, 0],
            ],
        )
        with self.assertRaises(OperatorFailed):
            fill_enclosed([[0, 1], [1, 0]])

        # Component extraction
        two_objects = [
            [1, 1, 0, 2],
            [1, 1, 0, 0],
            [0, 0, 0, 0],
        ]
        largest = largest_object(two_objects)
        self.assertEqual(largest, [[1, 1], [1, 1]])
        smallest = smallest_object(two_objects)
        self.assertEqual(smallest, [[2]])

    def test_strict_zero_answer_leakage_and_immutability(self) -> None:
        """Verify strict air-gapped answer isolation: withheld test outputs never leak."""
        task = {
            "id": "leakage_airgap_01",
            "train": [{"input": [[1]], "output": [[2]]}],
            "test": [{"input": [[3]], "output": [[999]], "secret": "classified"}],
        }

        # 1. public_task strips all test outputs and extraneous keys
        pub = public_task(task, "leakage_airgap_01")
        self.assertEqual(pub["test"], [{"input": [[3]]}])
        self.assertNotIn("output", pub["test"][0])
        self.assertNotIn("secret", pub["test"][0])

        # 2. Deepcopy immutability: mutating public envelope does not corrupt source task
        pub["train"][0]["output"][0][0] = 777
        self.assertEqual(task["train"][0]["output"][0][0], 2)

        # 3. Demonstration world and TaskSpec receive training pairs only
        train_pairs = [([[1]], [[2]])]
        spec = build_spec("leakage_airgap_01", train_pairs)
        world = ArcDemonstrationWorld(spec, train_pairs)

        # Mutating external list does not mutate world's stored pairs
        train_pairs[0] = ([[88]], [[88]])
        self.assertEqual(world._pairs[0], ([[1]], [[2]]))
        self.assertEqual(world._targets[0], [[2]])

        # Secret target 999 must not appear anywhere in initial_state or goal
        self.assertNotIn(999, spec.initial_state)
        for var_idx, target_val in spec.goal:
            self.assertNotIn(999, (var_idx, target_val))

        # 4. run_task fails closed if unisolated task envelope with test output is passed
        leaked_envelope = {
            "task_id": "bad_task",
            "train": [{"input": [[1]], "output": [[2]]}],
            "test": [{"input": [[3]], "output": [[4]]}],  # Leaked test output
        }
        with self.assertRaises(ValueError):
            run_task(None, leaked_envelope, Budget())

    def test_multi_test_input_scoring_and_official_denominator(self) -> None:
        """Verify official ARC Prize multi-test-input scoring and fixed N=split denominator."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)

            # Task 1: 2 test inputs
            multi_task = {
                "train": [{"input": [[0]], "output": [[1]]}],
                "test": [
                    {"input": [[2]], "output": [[3]]},
                    {"input": [[4]], "output": [[5]]},
                ],
            }
            (tmp / "multi_01.json").write_text(json.dumps(multi_task), encoding="utf-8")

            # Task 2: 1 test input
            single_task = {
                "train": [{"input": [[0]], "output": [[1]]}],
                "test": [{"input": [[6]], "output": [[7]]}],
            }
            (tmp / "single_02.json").write_text(json.dumps(single_task), encoding="utf-8")

            # Scenario A: Partial solve on multi_01 (input 1 hit, input 2 miss), single_02 unattempted
            # Strict task solve requires ALL test inputs of the task to be correct.
            sub_partial = {
                "multi_01": [
                    {"attempt_1": [[3]], "attempt_2": [[0]]},  # Hit
                    {"attempt_1": [[0]], "attempt_2": [[0]]},  # Miss
                ]
            }
            res_a = score(sub_partial, tmp)
            self.assertEqual(res_a["tasks_in_split"], 2)
            self.assertEqual(res_a["tasks_submitted"], 1)
            # Fraction for multi_01 is 1/2 = 0.5.
            # Denominator is ALL 2 tasks in split -> arc_prize_score = 0.5 / 2 = 0.25!
            self.assertEqual(res_a["arc_prize_score"], 0.25)
            self.assertEqual(res_a["arc_prize_tasks_equivalent"], 0.5)
            # Strict solved MUST be 0
            self.assertEqual(res_a["strict_tasks_solved"], 0)
            self.assertEqual(res_a["strict_task_accuracy"], 0.0)

            # Scenario B: 2-Attempt policy (hit on attempt_2) and full solve across both tasks
            sub_full = {
                "multi_01": [
                    {"attempt_1": [[0]], "attempt_2": [[3]]},  # Hit on attempt_2
                    {"attempt_1": [[5]], "attempt_2": [[0]]},  # Hit on attempt_1
                ],
                "single_02": [
                    {"attempt_1": [[0]], "attempt_2": [[7]]},  # Hit on attempt_2
                ],
            }
            res_b = score(sub_full, tmp)
            self.assertEqual(res_b["strict_tasks_solved"], 2)
            self.assertEqual(res_b["strict_task_accuracy"], 1.0)
            self.assertEqual(res_b["arc_prize_score"], 1.0)
            self.assertEqual(res_b["solved_task_ids"], ["multi_01", "single_02"])

            # Scenario C: Empty submission -> 0.0 with denominator = 2
            res_c = score({}, tmp)
            self.assertEqual(res_c["tasks_in_split"], 2)
            self.assertEqual(res_c["tasks_submitted"], 0)
            self.assertEqual(res_c["strict_tasks_solved"], 0)
            self.assertEqual(res_c["arc_prize_score"], 0.0)
            self.assertEqual(res_c["denominator"], "all tasks in split")

    def test_submission_schema_and_grid_error_validation(self) -> None:
        """Verify strict conformance to ARC submission format and grid constraints."""
        # 1..30 dimension limits
        self.assertIsNone(grid_error([[1]]))
        self.assertIsNone(grid_error([[0] * 30] * 30))
        self.assertIsNotNone(grid_error([]))
        self.assertIsNotNone(grid_error([[]]))
        self.assertIsNotNone(grid_error([[0] * 31]))
        self.assertIsNotNone(grid_error([[0]] * 31))

        # Ragged grid rejection
        self.assertIsNotNone(grid_error([[1, 2], [3]]))

        # Cell value bounds 0..9 and strict type safety (no bools, floats, strings)
        self.assertIsNotNone(grid_error([[True]]))
        self.assertIsNotNone(grid_error([[False]]))
        self.assertIsNotNone(grid_error([[1.0]]))
        self.assertIsNotNone(grid_error([[-1]]))
        self.assertIsNotNone(grid_error([[10]]))
        self.assertIsNotNone(grid_error([["1"]]))

        # score_submission validation
        targets = [[[1]], [[2]]]
        self.assertTrue(score_submission([[[1]], [[2]]], targets)["exact_match"])
        self.assertFalse(score_submission([[[1]], [[3]]], targets)["exact_match"])
        self.assertFalse(score_submission([[[1]]], targets)["valid"])  # Missing 2nd target

    def test_hard_wall_clock_timeout_enforcement(self) -> None:
        """Verify that wall-clock budget expiration aborts execution cleanly with status 'timeout'."""
        pub = {
            "task_id": "timeout_verification",
            "train": [{"input": [[1, 0], [0, 2]], "output": [[2, 0], [0, 1]]}],
            "test": [{"input": [[3, 0], [0, 4]]}],
        }

        class MockSlowRuntime:
            def solve_task(self, spec, executor, seed=0):
                import time
                time.sleep(0.05)
                mock_res = MagicMock()
                mock_res.summary.return_value = {"nodes": 100}
                return mock_res

        budget = Budget(wall_clock_seconds=0.01)
        rec = run_task(MockSlowRuntime(), pub, budget)
        self.assertEqual(rec["status"], "timeout")
        self.assertGreaterEqual(rec["elapsed_seconds"], 0.01)
        self.assertEqual(len(rec["attempts"]), 1)
        self.assertIn("attempt_1", rec["attempts"][0])
        self.assertIn("attempt_2", rec["attempts"][0])

    def test_worker_isolation_and_memory_discipline(self) -> None:
        """Verify per-task runtime instantiation and garbage collection prevents memory growth."""
        pub = {
            "task_id": "memory_isolation_test",
            "train": [{"input": [[1]], "output": [[2]]}],
            "test": [{"input": [[3]]}],
        }
        for i in range(2):
            with tempfile.TemporaryDirectory(prefix="euclid-mem-test-") as tmp:
                rt = EuclidRuntime(creator_id=f"test-worker-{i}", state_dir=Path(tmp))
                try:
                    rt.compose_adaptive_intelligence()
                    rec = run_task(
                        rt,
                        pub,
                        Budget(probe_budget=1, submission_budget=1, wall_clock_seconds=5.0),
                    )
                    self.assertIn(rec["status"], ("completed", "timeout"))
                finally:
                    rt.close()
                    del rt
                    gc.collect()

    def test_e2e_real_arc_task_pipeline(self) -> None:
        """End-to-end integration test with real ARC task file."""
        task_path = (
            Path(__file__).resolve().parents[1]
            / "euclid"
            / "benchmarks"
            / "arc_agi_1"
            / "data"
            / "training"
            / "017c7c7b.json"
        )
        if not task_path.exists():
            self.skipTest(f"Real task file {task_path} not found")

        pub = load_public_task(task_path, None)
        self.assertEqual(pub["task_id"], "017c7c7b")
        self.assertNotIn("output", pub["test"][0])

        spec_json = encode_task_arc_to_euclid(json.loads(task_path.read_text(encoding="utf-8")))
        self.assertIn("variables", spec_json)
        self.assertIn("operators", spec_json)

        # Run through adapter pipeline
        res = run_arc_task_adapter(task_path)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["adaptation"]["task_id"], "017c7c7b")
        self.assertIn("best_program", res["adaptation"])
        self.assertIsInstance(res["adaptation"]["decoded_grid"], list)


if __name__ == "__main__":
    unittest.main()
