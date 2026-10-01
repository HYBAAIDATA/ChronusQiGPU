"""
Tests for the machinery used to replicate the 21 March 2026 A/B experiment:
meta-evolution switch, ENH-09 phase-transition tagging, ENH-02 sensitivity diagnostic.
"""
import os
import unittest

from pythagoras.core.diagnostics import phi_sensitivity
from pythagoras.core.phi_metric import PhiResonanceCalculator
from pythagoras.engine.v6_4_cross_file_reuse import CrossFilePrimitiveRepository
from pythagoras.engine.v6_5_manifold_escape import (PHASE_TRANSITION_RATIO, V65ManifoldEscapeEngine,
                                                    phase_transition_ratio)
from pythagoras.experiments.reference_metrics import phi_v12_0
from pythagoras.experiments.replicate_march_2026 import replicate

BENCH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "benchmarks")


def _read(name):
    with open(os.path.join(BENCH, name)) as fh:
        return fh.read()


class TestMetaSwitch(unittest.TestCase):
    def test_meta_off_freezes_adaptive_layers(self):
        eng = V65ManifoldEscapeEngine(repository=CrossFilePrimitiveRepository(), meta_evolution=False)
        before = {k: list(v) for k, v in eng.surrogate.operator_weights.items()}
        r = eng.run_optimization("mm", _read("matrix_math.py"), 8)
        self.assertEqual(r["promoted_primitives"], [])
        self.assertEqual(r["discovery_events_count"], 0)
        self.assertEqual(r["geometry_evolution_steps"], [])
        self.assertEqual(r["meta_steps"], 0)
        self.assertEqual({k: v for k, v in eng.surrogate.operator_weights.items() if k in before}, before)
        self.assertGreater(len(eng.surrogate.prediction_history), 0)  # RMSE still measured

    def test_meta_on_runs_adaptive_layers(self):
        r = V65ManifoldEscapeEngine(repository=CrossFilePrimitiveRepository(), meta_evolution=True) \
            .run_optimization("mm", _read("matrix_math.py"), 8)
        self.assertGreater(len(r["geometry_evolution_steps"]), 0)
        self.assertGreater(r["discovery_events_count"], 0)


class TestPhaseTransitionTagging(unittest.TestCase):
    def test_report_trajectory_would_be_tagged(self):
        """The report's search_engine.py steps: +0.0248, +0.0109, +0.0106, then +0.0899."""
        ratio = phase_transition_ratio(0.0899, [0.0248, 0.0109, 0.0106])
        self.assertGreaterEqual(ratio, PHASE_TRANSITION_RATIO)

    def test_ordinary_steps_are_not_tagged(self):
        self.assertLess(phase_transition_ratio(0.0175, [0.0172, 0.0178]), PHASE_TRANSITION_RATIO)
        self.assertIsNone(phase_transition_ratio(0.09, [0.01]))


class TestSensitivityDiagnostic(unittest.TestCase):
    def test_flat_metric_is_identified_as_plateau(self):
        d = phi_sensitivity(_read("matrix_math.py"), lambda code: 0.5976)
        self.assertEqual(d["verdict"], "metric_plateau")
        self.assertEqual(d["plateau_fraction"], 1.0)

    def test_v12_0_metric_is_flat_on_phi_resonance(self):
        """Reproduces the report's degenerate manifold as a property of the measurement."""
        self.assertEqual(phi_sensitivity(_read("phi_resonance.py"), phi_v12_0)["verdict"], "metric_plateau")
        self.assertNotEqual(phi_sensitivity(_read("phi_resonance.py"), PhiResonanceCalculator().compute_phi)["verdict"],
                            "metric_plateau")

    def test_neighbourhood_variants_preserve_behaviour(self):
        from pythagoras.core.diagnostics import neighbourhood
        src = _read("phi_resonance.py")
        ref = {}
        exec(src, ref)
        for name, code in neighbourhood(src).items():
            ns = {}
            exec(code, ns)
            self.assertAlmostEqual(ns["calculate_resonance"](1.0, 2.0, 3.0), ref["calculate_resonance"](1.0, 2.0, 3.0),
                                   places=12, msg=name)


class TestReplicationHarness(unittest.TestCase):
    def test_smoke(self):
        r = replicate(seeds=1, generations=2, budget_matched=False)
        self.assertIn("A_meta_off", r["conditions"])
        self.assertIn("B_meta_on", r["conditions"])
        self.assertEqual(r["conditions"]["A_meta_off"]["auto_discovered_primitives"]["mean"], 0)


if __name__ == "__main__":
    unittest.main()
