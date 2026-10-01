"""Regression tests for the roadmap gaps closed in v12.2."""
import json
import os
import tempfile
import unittest

from pythagoras.adapter import PythagorasEngineAdapter
from pythagoras.core.primitives import inject_docstring
from pythagoras.engine.v6_1_surrogate import NeuralSurrogateEvaluator
from pythagoras.engine.v6_2_geometry import CGPGeometryState, CollectiveGeometryCoordinator
from pythagoras.engine.v6_4_cross_file_reuse import CrossFilePrimitiveRepository
from pythagoras.engine.v6_5_manifold_escape import AnnealingConfig, V65ManifoldEscapeEngine
from pythagoras.experiments.replicate_march_2026 import replicate
from pythagoras.integration.repo_runner import _read_source, _write_source


SAMPLE = """\
def f(values):
    out = []
    for value in values:
        out.append(value * 2)
    return out
"""


class TestSourcePreambleAndEncoding(unittest.TestCase):
    def test_docstring_preserves_shebang_cookie_and_future(self):
        src = "#!/usr/bin/env python3\n# -*- coding: latin-1 -*-\nfrom __future__ import annotations\nx = 1\n"
        out, _ = inject_docstring(src)
        self.assertTrue(out.startswith("#!/usr/bin/env python3\n# -*- coding: latin-1 -*-\n\"\"\""))
        self.assertLess(out.index('"""'), out.index("from __future__"))
        compile(out, "<test>", "exec")

    def test_pep263_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "latin.py")
            raw = "# -*- coding: latin-1 -*-\nname = 'caf\xe9'\n".encode("latin-1")
            with open(path, "wb") as fh:
                fh.write(raw)
            text, enc = _read_source(path)
            self.assertIn("café", text)
            _write_source(path, text, enc)
            with open(path, "rb") as fh:
                self.assertEqual(fh.read(), raw)


class TestAdaptiveState(unittest.TestCase):
    def test_adversarial_catalog_and_state_round_trip(self):
        s = NeuralSurrogateEvaluator()
        features = {"node_count": 10, "depth": 2, "annotation_density": 0,
                    "function_count": 1, "statement_count": 3}
        for _ in range(3):
            s.update(features, "BAD:operator", -0.2, True, True)
        self.assertIn("ANTI:BAD:operator", s.adversarial_catalog)
        restored = NeuralSurrogateEvaluator()
        restored.import_state(s.export_state())
        self.assertTrue(restored.is_anti_primitive("BAD:operator"))
        self.assertEqual(restored.adversarial_catalog, s.adversarial_catalog)

    def test_persistent_adaptive_state_and_hashed_provenance(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "state.json")
            repo = CrossFilePrimitiveRepository(path)
            from pythagoras.core.primitives import compose
            op = compose(["ADD:AnnAssign", "HEAL:dead_code_elimination"], "HOST:test")
            repo.register_promoted_primitive("HOST:test", op, "a.py", 0.1)
            repo.record_cross_file_use("HOST:test", "b.py", 0.2)
            repo.save_adaptive_state({"surrogate": {"operator_weights": {"x": [1, 2, 3, 4, 5]}}})
            loaded = CrossFilePrimitiveRepository(path)
            self.assertEqual(len(loaded.provenance_events), 2)
            self.assertEqual(loaded.provenance_events[1]["previous_hash"],
                             loaded.provenance_events[0]["event_hash"])
            self.assertIn("surrogate", loaded.get_adaptive_state())

    def test_adapter_restores_surrogate_and_collective_geometry(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "state.json")
            adapter = PythagorasEngineAdapter(path and 0.618033988749895, persistent_repo_path=path)
            adapter.evolve("sample.py", SAMPLE, generations=2)
            restored = PythagorasEngineAdapter(persistent_repo_path=path)
            self.assertTrue(restored.snapshot()["adaptive_state"]["collective_geometry"]["observations"])


class TestSearchGapClosures(unittest.TestCase):
    def test_collective_geometry_uses_consensus(self):
        c = CollectiveGeometryCoordinator()
        for i, cols in enumerate((10, 18, 14)):
            g = CGPGeometryState(cols, 3 + i, 10)
            c.observe(f"f{i}.py", g, 0.1)
        self.assertEqual(c.initial_state().n_cols, 14)

    def test_annealing_and_surrogate_geometry_are_configurable(self):
        eng = V65ManifoldEscapeEngine(
            annealing=AnnealingConfig(enabled=True, initial_temperature=1.0),
            geometry_signal="surrogate_velocity",
        )
        result = eng.run_optimization("sample.py", SAMPLE, 2)
        self.assertTrue(result["annealing_enabled"])
        self.assertEqual(result["geometry_signal"], "surrogate_velocity")
        self.assertIn("collective_geometry_state", result)

    def test_rolling_normalization_is_reported(self):
        result = replicate(seeds=1, generations=1, budget_matched=False)
        summary = result["conditions"]["B_meta_on"]
        self.assertIn("gain_per_100_evaluations", summary)
        self.assertIn("rolling_3_win_gain", summary)


if __name__ == "__main__":
    unittest.main()