"""EUCLID v17 task worlds: exact semantics, public/hidden split, fail-closed budgets."""
from __future__ import annotations

import json
import unittest

from euclid.cognition.integrated.agent import build_problem
from euclid.cognition.worlds import (
    FAMILIES,
    HELD_OUT,
    IN_DISTRIBUTION,
    Mechanism,
    MechanismWorld,
    TaskSpec,
    WorldExecutor,
    generate_suite,
    generate_task,
    hypothesis_space,
    isomorph,
    resample_mechanisms,
)
from euclid.cognition.worlds.families import bfs_distances, optimal_program, relational_overlap
from euclid.cognition.worlds.world import HiddenTruth


class MechanismSemantics(unittest.TestCase):
    def test_kinds_are_exact(self) -> None:
        domains = (5, 4, 4)
        state = (3, 1, 2)
        self.assertEqual(Mechanism("add", (0, 4)).apply(state, domains), (2, 1, 2))
        self.assertEqual(Mechanism("set", (1, 0)).apply(state, domains), (3, 0, 2))
        self.assertEqual(Mechanism("copy", (0, 2)).apply(state, domains), (3, 1, 3))
        self.assertEqual(Mechanism("swap", (1, 2)).apply(state, domains), (3, 2, 1))
        guarded = Mechanism("guard", (1, 1), Mechanism("add", (0, 1)))
        self.assertEqual(guarded.apply(state, domains), (4, 1, 2))
        self.assertEqual(guarded.apply((3, 0, 2), domains), (3, 0, 2))
        pair = Mechanism("pair", (), Mechanism("add", (0, 1)), Mechanism("add", (2, 1)))
        self.assertEqual(pair.apply(state, domains), (4, 1, 3))

    def test_invalid_mechanisms_fail_closed(self) -> None:
        with self.assertRaises(ValueError):
            Mechanism("teleport", ())
        with self.assertRaises(ValueError):
            Mechanism("copy", (1, 1))
        with self.assertRaises(ValueError):
            Mechanism("guard", (0, 1), Mechanism("guard", (1, 0), Mechanism("noop")))

    def test_hypothesis_space_is_deterministic_and_valid(self) -> None:
        domains = (3, 4, 3)
        first = hypothesis_space(domains)
        self.assertEqual(first, hypothesis_space(domains))
        self.assertEqual(len(first), len(set(first)))
        self.assertTrue(all(m.valid_for(domains) for m in first))

    def test_json_round_trip_and_remap(self) -> None:
        mechanism = Mechanism("guard", (2, 1), Mechanism("copy", (0, 1)))
        self.assertEqual(Mechanism.from_json(mechanism.to_json()), mechanism)
        remapped = mechanism.remap({0: 2, 1: 0, 2: 1})
        self.assertEqual(remapped, Mechanism("guard", (1, 1), Mechanism("copy", (2, 0))))


class WorldBoundary(unittest.TestCase):
    def setUp(self) -> None:
        self.spec, self.truth = generate_task("program-transformation", seed=11,
                                              partition="evaluation")

    def test_problem_envelope_reveals_no_hidden_truth(self) -> None:
        envelope = json.dumps(build_problem(self.spec), sort_keys=True)
        for op, mechanism in self.truth.mechanisms.items():
            self.assertNotIn(json.dumps(mechanism.to_json()), envelope)
        self.assertNotIn("optimal", envelope)
        self.assertNotIn(self.truth.family, json.dumps(build_problem(self.spec)["structure"]))

    def test_probe_hides_goal_verdict_and_submission_judges_true_state(self) -> None:
        world = MechanismWorld(self.spec, self.truth)
        probe = world.probe([self.spec.operators[0]])
        self.assertNotIn("goal_met", probe)
        result = world.submit(list(self.truth.optimal_program))
        self.assertTrue(result["goal_met"])
        self.assertTrue(world.solved)

    def test_budgets_fail_closed(self) -> None:
        world = MechanismWorld(self.spec, self.truth)
        executor = WorldExecutor(world)
        for _ in range(self.spec.probe_budget):
            executor.execute("p", {"kind": "intervention", "program": [self.spec.operators[0]]})
        exhausted = executor.execute("p", {"kind": "intervention",
                                           "program": [self.spec.operators[0]]})
        self.assertTrue(exhausted["budget_exhausted"])
        self.assertFalse(exhausted["goal_met"])
        with self.assertRaises(ValueError):
            executor.execute("x", {"kind": "plan"})
        with self.assertRaises(ValueError):
            executor.execute("x", {"kind": "teleport", "program": []})
        with self.assertRaises(ValueError):
            world.submit(["no-such-operator"])

    def test_noise_shift_and_proxy_variants(self) -> None:
        spec, truth = generate_task("causal-circuit", seed=5, partition="evaluation",
                                    tags=("proxy-reward",))
        proxy = next(iter(truth.proxy_operators))
        result = MechanismWorld(spec, truth).submit([proxy, proxy])
        self.assertEqual(result["trajectory"][0], list(spec.initial_state))
        self.assertGreater(result["scores"][-1], result["scores"][0] - 1)
        spec, truth = generate_task("program-transformation", seed=7, partition="evaluation",
                                    tags=("mechanism-shift",))
        world = MechanismWorld(spec, truth)
        after, op, replacement = truth.shift
        for _ in range(after):
            world.probe([spec.operators[0]])
        self.assertTrue(world.shift_applied)
        self.assertEqual(world._mechanisms[op], replacement)


class Suites(unittest.TestCase):
    def test_partitions_disjoint_and_solvable(self) -> None:
        suite = generate_suite(4242, train_per_family=2, development_per_family=1,
                               evaluation_per_family=1, held_out_per_family=1,
                               adversarial_per_tag=1, analogy_pairs=1)
        seen = {}
        for bucket, tasks in suite.items():
            for task in tasks:
                self.assertNotIn(task.spec.task_id, seen)
                seen[task.spec.task_id] = bucket
                if task.spec.objective == "assign":
                    tree = bfs_distances(task.truth.mechanisms, task.spec.operators,
                                         task.spec.initial_state, task.spec.domains)
                    program = optimal_program(tree, task.spec.goal)
                    self.assertIsNotNone(program)
                    self.assertEqual(len(program), task.truth.optimal_length)
        families = {t.truth.family for t in suite["held-out"]}
        self.assertEqual(families, set(HELD_OUT))
        self.assertFalse(families & {t.truth.family for t in suite["train"]})
        self.assertEqual({t.truth.family for t in suite["train"]}, set(IN_DISTRIBUTION))

    def test_generation_is_seed_deterministic(self) -> None:
        a = generate_task("planning-logistics", seed=3, partition="evaluation")
        b = generate_task("planning-logistics", seed=3, partition="evaluation")
        self.assertEqual(a[0], b[0])
        self.assertEqual(a[1].to_json(), b[1].to_json())

    def test_isomorph_is_exact_and_superficial_twin_is_structurally_disjoint(self) -> None:
        spec, truth = generate_task("program-transformation", seed=21, partition="train")
        twin_spec, twin_truth = isomorph(spec, truth, seed=3, target_family="graph-navigation",
                                         partition="evaluation")
        self.assertNotEqual(twin_spec.operators, spec.operators)
        self.assertEqual(sorted(twin_spec.domains), sorted(spec.domains))
        self.assertEqual(relational_overlap(truth.mechanisms, twin_truth.mechanisms,
                                            twin_spec.domains, spec.domains),
                         len(spec.operators))
        fake_spec, fake_truth = resample_mechanisms(spec, truth, seed=4,
                                                    partition="evaluation", tag="superficial")
        self.assertEqual(fake_spec.operators, spec.operators)
        self.assertLess(relational_overlap(truth.mechanisms, fake_truth.mechanisms,
                                           spec.domains), 2)
        replay = spec.initial_state
        for op in truth.optimal_program:
            replay = fake_truth.mechanisms[op].apply(replay, spec.domains)
        self.assertFalse(spec.goal_met(replay))

    def test_response_tasks_have_declared_shape(self) -> None:
        spec, truth = generate_task("parameter-optimisation", seed=8, partition="evaluation")
        self.assertEqual(len(truth.response), spec.parametric[1])
        best = max(range(len(truth.response)), key=truth.response.__getitem__)
        world = MechanismWorld(spec, truth)
        self.assertTrue(world.submit([["tune", best]])["goal_met"])
        self.assertEqual(FAMILIES["dose-response"].held_out, True)

    def test_task_spec_round_trip(self) -> None:
        spec, _ = generate_task("symbolic-rewriting", seed=2, partition="evaluation")
        self.assertEqual(TaskSpec.from_json(spec.to_json()), spec)
        self.assertEqual(TaskSpec.from_json(spec.to_json()).digest, spec.digest)
        with self.assertRaises(ValueError):
            HiddenTruth(family="x")  # constructible; worlds must still reject mismatches
            MechanismWorld(spec, HiddenTruth(family="x"))


if __name__ == "__main__":
    unittest.main()
