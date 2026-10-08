"""EUCLID v17 φ/Fibonacci machinery and evidence-gated skill discovery."""
from __future__ import annotations

import random
import statistics
import unittest

from euclid.cognition.integrated.phi_mechanisms import (
    EVIDENCE_CLASS,
    difference_bisection,
    explore_then_refine,
    fibonacci_numbers,
    fibonacci_schedule,
    fibonacci_search,
    golden_weyl_points,
    grid_points,
    iterative_deepening,
    linear_schedule,
    ternary_search,
    unimodal_violation,
)
from euclid.cognition.integrated.skills import (
    SkillLibrary,
    TaskModel,
    abstract_window,
    anti_unify,
    semantic_digest,
)
from euclid.cognition.worlds import Mechanism, generate_task


def _unimodal(rng: random.Random, size: int) -> list[float]:
    peak = rng.randrange(size)
    left = sorted(rng.random() for _ in range(peak + 1))
    right = sorted((rng.random() * left[-1] * 0.999 for _ in range(size - peak - 1)),
                   reverse=True)
    return left + right


class FibonacciSearch(unittest.TestCase):
    def test_exact_on_strictly_unimodal_sequences(self) -> None:
        rng = random.Random(7)
        for _ in range(800):
            values = _unimodal(rng, rng.randint(1, 200))
            best = max(range(len(values)), key=values.__getitem__)
            for method in (fibonacci_search, ternary_search, difference_bisection):
                self.assertEqual(method(values.__getitem__, len(values), 10 ** 6).best, best)

    def test_uses_fewer_evaluations_than_neutral_twins(self) -> None:
        rng = random.Random(11)
        counts = {"fib": [], "ternary": [], "bisection": []}
        for _ in range(300):
            values = _unimodal(rng, rng.randint(30, 300))
            counts["fib"].append(fibonacci_search(values.__getitem__, len(values), 999).evaluations)
            counts["ternary"].append(ternary_search(values.__getitem__, len(values), 999).evaluations)
            counts["bisection"].append(
                difference_bisection(values.__getitem__, len(values), 999).evaluations)
        self.assertLess(statistics.fmean(counts["fib"]), statistics.fmean(counts["bisection"]))
        self.assertLess(statistics.fmean(counts["bisection"]), statistics.fmean(counts["ternary"]))
        self.assertEqual(EVIDENCE_CLASS["fibonacci_search"], "known-theorem-operationalised")

    def test_fibonacci_numbers_cross_check_lucas_kernel(self) -> None:
        from lucas.core import fibonacci

        numbers = fibonacci_numbers(10 ** 40)
        self.assertEqual(numbers, [fibonacci(i) for i in range(len(numbers))])

    def test_budget_exhaustion_returns_best_observed(self) -> None:
        values = _unimodal(random.Random(3), 200)
        trace = fibonacci_search(values.__getitem__, 200, 3)
        self.assertTrue(trace.exhausted)
        self.assertEqual(trace.evaluations, 3)
        self.assertIn(trace.best, trace.evaluated)

    def test_unimodality_violation_detection(self) -> None:
        self.assertFalse(unimodal_violation({0: 1.0, 5: 3.0, 9: 2.0}))
        self.assertTrue(unimodal_violation({0: 3.0, 5: 1.0, 9: 2.0}))

    def test_explore_then_refine_handles_bimodality(self) -> None:
        size = 120
        values = [max(10 - abs(i - 20) * 0.4, 12 - abs(i - 95) * 0.5) for i in range(size)]
        trace = explore_then_refine(values.__getitem__, size, 20, exploration=8)
        self.assertEqual(trace.best, 95)

    def test_golden_weyl_and_grid_coverage(self) -> None:
        points = golden_weyl_points(13, 1000)
        self.assertEqual(len(set(points)), 13)
        gaps = sorted(points)
        widest = max([b - a for a, b in zip(gaps, gaps[1:])] + [gaps[0] + 1000 - gaps[-1]])
        self.assertLess(widest, 1000 * 0.2)
        self.assertEqual(len(grid_points(10, 100)), 10)

    def test_deepening_schedules_find_valid_plans(self) -> None:
        spec, truth = generate_task("program-transformation", seed=5, partition="evaluation")
        for schedule in (linear_schedule, fibonacci_schedule):
            result = iterative_deepening(truth.mechanisms, spec.operators, spec.initial_state,
                                         spec.goal, spec.domains,
                                         schedule=schedule(spec.max_program_length),
                                         node_budget=10 ** 6)
            self.assertIsNotNone(result["program"])
            state = spec.initial_state
            for op in result["program"]:
                state = truth.mechanisms[op].apply(state, spec.domains)
            self.assertTrue(spec.goal_met(state))
        linear = iterative_deepening(truth.mechanisms, spec.operators, spec.initial_state,
                                     spec.goal, spec.domains,
                                     schedule=linear_schedule(spec.max_program_length),
                                     node_budget=10 ** 6)
        self.assertEqual(linear["length"], truth.optimal_length)


class SkillLifecycle(unittest.TestCase):
    def test_abstraction_is_vocabulary_free_and_anti_unifies(self) -> None:
        a = abstract_window([Mechanism("add", (3, 1)), Mechanism("copy", (3, 0))])
        b = abstract_window([Mechanism("add", (1, 1)), Mechanism("copy", (1, 2))])
        self.assertEqual(a, b)
        c = abstract_window([Mechanism("add", (0, 2)), Mechanism("copy", (0, 1))])
        self.assertEqual(anti_unify([a, c]), (("add", "r0", "*"), ("copy", "r0", "r1")))

    def _model(self, task_id: str, start, goal, table) -> TaskModel:
        return TaskModel(task_id, "unit", (6, 6), tuple(table), table, start, goal, 12)

    def test_useful_macro_promoted_and_semantics_survive_restart(self) -> None:
        library = SkillLibrary(min_support=2, trial_budget=400)
        step = {"inc": Mechanism("add", (0, 1)), "copy": Mechanism("copy", (0, 1)),
                "noise_a": Mechanism("set", (1, 5)), "noise_b": Mechanism("swap", (0, 1))}
        for index, start in enumerate([(0, 0), (1, 3), (2, 0)]):
            goal = ((0, (start[0] + 2) % 6),)
            model = self._model(f"t{index}", start, goal, step)
            library.observe_solution(model, ["inc", "inc"])
        first = library.lifecycle()
        self.assertFalse([r for r in library.records.values() if r.status == "promoted"],
                         "no promotion without held-out generalisation evidence")
        self.assertTrue(any(e["event"] == "awaiting-generalisation-evidence"
                            for r in library.records.values() for e in r.events), first)
        # verified task models the macro was NOT mined from (held-out evidence)
        for index, start in enumerate([(0, 1), (1, 1)]):
            goal = ((0, (start[0] + 4) % 6),)
            library.corpus[f"h{index}"] = self._model(f"h{index}", start, goal, step)
        report = library.lifecycle()
        promoted = [r for r in library.records.values() if r.status == "promoted"]
        self.assertTrue(promoted, report)
        self.assertTrue(all(r.held_out_utility and r.held_out_utility > 0 for r in promoted))
        payload = library.to_payload()
        restored = SkillLibrary.from_payload(payload)
        for record in promoted:
            self.assertEqual(restored.records[record.skill_id].semantic,
                             semantic_digest(record.pattern))
        tampered = dict(payload)
        rows = [dict(row) for row in payload["skills"]]
        rows[0]["pattern_json"] = [["set", "r0", 0]]
        tampered["skills"] = rows
        with self.assertRaises(ValueError):
            SkillLibrary.from_payload(tampered)

    def test_capacity_deprecates_without_erasing_history(self) -> None:
        library = SkillLibrary(capacity=0)
        library.records["skill-x"] = __import__(
            "euclid.cognition.integrated.skills", fromlist=["SkillRecord"]
        ).SkillRecord("skill-x", (("add", "r0", 1),), "skill", "unit", status="promoted")
        library._enforce_capacity([])
        record = library.records["skill-x"]
        self.assertEqual(record.status, "deprecated")
        self.assertEqual(record.events[-1]["event"], "deprecated")

    def test_binding_respects_role_structure(self) -> None:
        library = SkillLibrary()
        table = {"a": Mechanism("add", (0, 1)), "b": Mechanism("copy", (0, 1)),
                 "c": Mechanism("copy", (1, 0))}
        bound = library.bind_pattern((("add", "r0", "*"), ("copy", "r0", "r1")), table, list(table))
        self.assertIn(("a", "b"), bound)
        self.assertNotIn(("a", "c"), bound)


if __name__ == "__main__":
    unittest.main()
