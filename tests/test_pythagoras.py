"""Repository contracts for the wholesale PYTHAGORAS v12.2 implementation."""
import pythagoras
from pythagoras.engine.v6_5_manifold_escape import V65ManifoldEscapeEngine


from __future__ import annotations

import ast
import math
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
import numpy as np

from pythagoras import (
    PHI,
    PhiResonanceCalculator,
    CGP,
    PythagorasMutator,
    SurrogateFitnessModel,
    MetaEvolutionController,
    AutoPrimitiveDiscovery,
    GeometryEvolution,
    Pythagoras,
    normalize_future_imports,
    read_source_utf8,
    write_source_utf8,
    safe_git_lock_recovery,
    run_isolated_execution,
    rolling_window_normalize,
)

SAMPLE_CODE_1 = '''"""Sample module for testing."""
from __future__ import annotations

def compute_square(x):
    res = x * x
    return res

def process_items(items):
    total = 0
    for item in items:
        if item > 0:
            total += compute_square(item)
    return total
'''

SAMPLE_CODE_DEGENERATE = '''"""Sample degenerate flat basin code."""
def f():
    pass
'''

SAMPLE_HIGH_COMPLEXITY = '''"""Sample function with high statement count."""
def monolithic_engine(a, b, c):
    v1 = a + b
    v2 = b * c
    v3 = v1 - v2
    v4 = v3 * 2
    v5 = v4 + a
    v6 = v5 - b
    v7 = v6 * c
    v8 = v7 + 42
    return v8
'''


class TestPhiResonance(unittest.TestCase):
    def setUp(self):
        self.calc = PhiResonanceCalculator()

    def test_phi_constant(self):
        expected = (math.sqrt(5.0) - 1.0) / 2.0
        self.assertAlmostEqual(PHI, expected, places=7)
        self.assertAlmostEqual(self.calc.phi_target, expected, places=7)

    def test_compute_range(self):
        score = self.calc.compute(SAMPLE_CODE_1)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_compute_components(self):
        comps = self.calc.compute_components(SAMPLE_CODE_1)
        self.assertIn("abstraction", comps)
        self.assertIn("depth_balance", comps)
        self.assertIn("density", comps)
        self.assertIn("composite", comps)
        self.assertAlmostEqual(
            comps["composite"],
            (comps["abstraction"] + comps["depth_balance"] + comps["density"]) / 3.0,
            places=5,
        )

    def test_syntax_error_resilience(self):
        invalid_code = "def invalid_syntax(:"
        score = self.calc.compute(invalid_code)
        self.assertEqual(score, 0.0)

    def test_enh02_manifold_diagnosis(self):
        diag = self.calc.diagnose_manifold(SAMPLE_CODE_1)
        self.assertIn("base_phi", diag)
        self.assertIn("components", diag)
        self.assertIn("max_abs_gradient", diag)
        self.assertIn("is_degenerate_manifold", diag)
        self.assertIn("recommended_escape", diag)


class TestCGP(unittest.TestCase):
    def setUp(self):
        self.cgp = CGP(n_cols=6, levels_back=2, pop_size=10)

    def test_initialization(self):
        self.cgp.initialize()
        self.assertEqual(len(self.cgp.population), 10)
        self.assertEqual(len(self.cgp.population[0]), 6)

    def test_crossover_and_mutation(self):
        self.cgp.initialize()
        p1 = self.cgp.population[0]
        p2 = self.cgp.population[1]
        child = self.cgp._crossover(p1, p2)
        self.assertEqual(len(child), 6)
        mutated = self.cgp._mutate(child, rate=0.5)
        self.assertEqual(len(mutated), 6)

    def test_primitive_add_annotation(self):
        code = "def foo(x):\n    return x + 1"
        transformed = self.cgp._add_annotation(code, 1.0)
        # Should be valid python
        tree = ast.parse(transformed)
        fn = tree.body[0]
        self.assertIsInstance(fn, ast.FunctionDef)
        self.assertIsNotNone(fn.args.args[0].annotation)

    def test_primitive_rename_var(self):
        code = "def bar(x):\n    y = x * 2\n    return y"
        transformed = self.cgp._rename_var(code, 1.0)
        ast.parse(transformed)
        self.assertIn("target_val", transformed)

    def test_primitive_extract_constant(self):
        code = "def calc(val):\n    return val * 3.14159"
        transformed = self.cgp._extract_constant(code, 1.0)
        ast.parse(transformed)
        self.assertIn("PHI_CONST_", transformed)

    def test_primitive_inline_function(self):
        code = "def identity(val):\n    return val\ndef runner(item):\n    return identity(item)"
        transformed = self.cgp._inline_function(code, 1.0)
        ast.parse(transformed)

    def test_primitive_split_function_enh01(self):
        transformed = self.cgp._split_function(SAMPLE_HIGH_COMPLEXITY, 1.0)
        ast.parse(transformed)
        self.assertIn("_sub_monolithic_engine_partition", transformed)

    def test_cgp_evolve_step(self):
        best_genome, fitness, evolved_source = self.cgp.evolve(SAMPLE_CODE_1, generations=2)
        self.assertGreater(fitness, 0.0)
        self.assertTrue(len(evolved_source) > 0)
        ast.parse(evolved_source)


class TestPythagorasMutation(unittest.TestCase):
    def setUp(self):
        self.mutator = PythagorasMutator()

    def test_surrogate_feature_extraction(self):
        features = self.mutator.surrogate.extract_features(SAMPLE_CODE_1, self.mutator.phi_calc)
        self.assertEqual(len(features), 8)
        self.assertGreater(features[0], 0.0)  # log node count > 0

    def test_surrogate_online_learning(self):
        features = np.ones(8)
        initial_pred = self.mutator.surrogate.predict(features)
        self.mutator.surrogate.update(features, actual_gain=0.1)
        new_pred = self.mutator.surrogate.predict(features)
        self.assertGreater(new_pred, initial_pred)

    def test_surrogate_transfer_learning_enh11(self):
        prior = SurrogateFitnessModel(8)
        prior.weights = np.full(8, 0.42)
        prior.bias = 0.15
        prior.sample_count = 10

        target = SurrogateFitnessModel(8)
        target.transfer_from(prior)
        np.testing.assert_allclose(target.weights, prior.weights)
        self.assertEqual(target.bias, 0.15)
        self.assertEqual(target.sample_count, 10)

    def test_primitives_add_return_and_docstring(self):
        code = "def simple_func(x):\n    x = x + 1"
        res = self.mutator._add_return(code)
        self.assertIn("return None", res)

        with_doc = self.mutator._add_docstring(res)
        self.assertIn("Structural unit: simple_func", with_doc)

    def test_adversarial_perturb_enh12(self):
        code = "def worker():\n    return 1"
        perturbed = self.mutator._adversarial_perturb(code)
        ast.parse(perturbed)
        self.assertIn("if False:", perturbed)

    def test_mutate_returns_gains(self):
        mutated, gains = self.mutator.mutate(SAMPLE_CODE_1, n_mutations=2)
        ast.parse(mutated)
        self.assertIsInstance(gains, dict)


class TestMetaEvolution(unittest.TestCase):
    def setUp(self):
        self.meta = MetaEvolutionController(
            initial_mutation_rate=0.15,
            phase_transition_threshold=0.05,
            stall_threshold=2,
        )

    def test_adaptive_mutation_rate(self):
        # Progress: exploit
        self.meta.update(
            generation=1,
            fitness_history=[0.50, 0.55],
            primitive_gains={"ADD:AnnAssign": 0.05},
        )
        self.assertLess(self.meta.mutation_rate, 0.15)

        # Stall: explore
        self.meta.update(
            generation=2,
            fitness_history=[0.55, 0.55],
            primitive_gains={},
        )
        self.meta.update(
            generation=3,
            fitness_history=[0.55, 0.55],
            primitive_gains={},
        )
        self.assertTrue(self.meta.in_annealing_mode)

    def test_seeded_annealing_is_reproducible(self):
        left = MetaEvolutionController(random_seed=7)
        right = MetaEvolutionController(random_seed=7)
        for controller in (left, right):
            controller.in_annealing_mode = True
            controller.temperature = 0.1
        left_decisions = [left.should_accept(-0.05) for _ in range(20)]
        right_decisions = [right.should_accept(-0.05) for _ in range(20)]
        self.assertEqual(left_decisions, right_decisions)

    def test_simulated_annealing_enh04(self):
        # When not in annealing mode, negative delta rejected
        self.assertFalse(self.meta.should_accept(-0.05))

        # Force annealing mode
        self.meta.in_annealing_mode = True
        self.meta.temperature = 10.0  # high temp accepts almost everything
        accepted = any(self.meta.should_accept(-0.01) for _ in range(20))
        self.assertTrue(accepted)

    def test_phase_transition_tagging_enh09(self):
        # Jump of +0.0899
        self.meta.update(
            generation=1,
            fitness_history=[0.5905, 0.6804],
            primitive_gains={"ADD:AnnAssign": 0.0899},
            file_id="search_engine.py",
        )
        self.assertEqual(len(self.meta.phase_transitions), 1)
        pt = self.meta.phase_transitions[0]
        self.assertAlmostEqual(pt["delta_phi"], 0.0899, places=3)
        self.assertEqual(pt["triggering_primitive"], "ADD:AnnAssign")

    def test_provenance_tracking_enh10(self):
        self.meta.update(
            generation=1,
            fitness_history=[0.50, 0.52],
            primitive_gains={"REFACTOR:Split": 0.02},
            file_id="target.py",
        )
        self.assertTrue(len(self.meta.provenance_log) > 0)
        self.assertEqual(self.meta.provenance_log[0]["primitive"], "REFACTOR:Split")


class TestAutoPrimitiveDiscovery(unittest.TestCase):
    def setUp(self):
        self.discovery = AutoPrimitiveDiscovery(gain_threshold=0.05, consistency_threshold=3)

    def test_discovery_promotion(self):
        for _ in range(3):
            self.discovery.observe("STRUCTURAL_FLATTEN", 0.06)

        discovered = self.discovery.discover()
        self.assertEqual(len(discovered), 1)
        prim = discovered[0]
        self.assertEqual(prim["name"], "STRUCTURAL_FLATTEN")
        self.assertAlmostEqual(prim["avg_gain"], 0.06, places=4)
        self.assertGreater(prim["weight"], 0.0)


class TestGeometryEvolution(unittest.TestCase):
    def setUp(self):
        self.geom = GeometryEvolution(n_cols=12, levels_back=3, pop_size=50)

    def test_curvature_computation(self):
        # Accelerating trajectory
        history = [0.50, 0.52, 0.56]
        c = self.geom._compute_curvature(history)
        # d1 = 0.04, d2 = 0.02, curvature = 0.02
        self.assertAlmostEqual(c, 0.02, places=4)

    def test_enh06_trigger_decoupling(self):
        # Positive curvature and positive surrogate velocity -> expand
        history = [0.50, 0.52, 0.56]
        rec = self.geom.evolve(history, surrogate_velocity=0.1)
        self.assertEqual(rec["action"], "expand")
        self.assertEqual(self.geom.n_cols, 14)
        self.assertEqual(self.geom.levels_back, 4)  # ENH-07
        self.assertEqual(self.geom.pop_size, 60)

    def test_enh14_collective_geometry(self):
        geoms = [
            {"n_cols": 12, "levels_back": 3, "pop_size": 50},
            {"n_cols": 14, "levels_back": 4, "pop_size": 60},
            {"n_cols": 14, "levels_back": 4, "pop_size": 70},
        ]
        consensus = GeometryEvolution.compute_consensus(geoms)
        self.assertEqual(consensus["n_cols"], 14)
        self.assertEqual(consensus["levels_back"], 4)
        self.assertEqual(consensus["pop_size"], 60)


class TestOrchestrator(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_fix01_future_import_normalization(self):
        misplaced_code = """def dummy():
    pass
from __future__ import annotations
import os
"""
        normalized = normalize_future_imports(misplaced_code)
        lines = [line.strip() for line in normalized.splitlines() if line.strip()]
        self.assertTrue(lines[0].startswith("from __future__ import"))

    def test_fix02_utf8_uniformity(self):
        test_file = self.temp_dir / "utf8_test.py"
        src = '# coding: utf-8\nmsg = "Resonance φ = 0.618034"\n'
        write_source_utf8(test_file, src)
        read_back = read_source_utf8(test_file)
        self.assertEqual(src, read_back)

    def test_fix03_git_lock_recovery(self):
        git_dir = self.temp_dir / ".git"
        git_dir.mkdir(parents=True)
        lock = git_dir / "index.lock"
        lock.write_text("locked")
        # Backdate lock file to simulate stale lock
        past_time = os.path.getmtime(lock) - 20.0
        os.utime(lock, (past_time, past_time))

        recovered = safe_git_lock_recovery(self.temp_dir, retries=2, backoff=0.01)
        self.assertTrue(recovered)
        self.assertFalse(lock.exists())

    def test_fix04_timeout_isolation(self):
        safe_code = "a = 2 + 2\n"
        ok, msg = run_isolated_execution(safe_code)
        self.assertTrue(ok)

    def test_fix04_timeout_actually_terminates_child(self):
        started = time.monotonic()
        ok, msg = run_isolated_execution("while True:\n    pass\n", timeout_seconds=0.2)
        elapsed = time.monotonic() - started
        self.assertFalse(ok)
        self.assertIn("timed out", msg.lower())
        self.assertLess(elapsed, 2.0)

    def test_invalid_high_fitness_candidates_are_not_committed(self):
        orch = Pythagoras(condition="B")
        initial = orch.domain.normalize(SAMPLE_CODE_1)
        orch.domain.tests = lambda source: source == initial
        result = orch.evolve_file(SAMPLE_CODE_1, generations=2)
        self.assertTrue(orch.domain.tests(result["final_source"]))
        self.assertTrue(orch.domain.is_valid(result["final_source"]))

    def test_enh08_rolling_window_normalize(self):
        raw = [1.0, 2.0, 3.0, 4.0, 5.0]
        smoothed = rolling_window_normalize(raw, window=3)
        self.assertEqual(len(smoothed), 5)
        self.assertAlmostEqual(smoothed[2], 2.0)  # (1+2+3)/3

    def test_enh05_condition_a_vs_b(self):
        orch_a = Pythagoras(condition="A")
        res_a = orch_a.evolve_file(SAMPLE_CODE_1, generations=3)
        self.assertEqual(res_a["condition"], "A")

        orch_b = Pythagoras(condition="B")
        res_b = orch_b.evolve_file(SAMPLE_CODE_1, generations=3)
        self.assertEqual(res_b["condition"], "B")

    def test_enh03_cross_file_seeding(self):
        orch = Pythagoras(condition="B")
        corpus = {
            "file_1.py": SAMPLE_CODE_1,
            "file_2.py": SAMPLE_HIGH_COMPLEXITY,
        }
        corpus_results = orch.evolve_corpus(corpus, generations=2)
        self.assertIn("file_1.py", corpus_results["files"])
        self.assertIn("file_2.py", corpus_results["files"])
        self.assertIn("consensus_geometry", corpus_results)

    def test_enh13_multi_session_memory(self):
        orch = Pythagoras(condition="B")
        orch.evolve_file(SAMPLE_CODE_1, generations=2)

        mem_file = self.temp_dir / "memory.json"
        orch.save_session(mem_file)
        self.assertTrue(mem_file.exists())

        orch_new = Pythagoras(condition="B")
        orch_new.load_session(mem_file)
        self.assertGreater(orch_new.mutator.surrogate.sample_count, 0)

    def test_kellogg_quantum_reflection_alignment(self):
        orch = Pythagoras()
        reflection = orch.kellogg_quantum_reflection(
            SAMPLE_CODE_1, marked_solutions=["target_function"]
        )
        self.assertIn("manifold_phi", reflection)
        self.assertIn("metric_tensor_diagonal", reflection)
        self.assertIn("reflection_phase", reflection)
        self.assertIn("kellogg_operator", reflection)
        self.assertIn("coherence_status", reflection)


if __name__ == "__main__":
    unittest.main()
