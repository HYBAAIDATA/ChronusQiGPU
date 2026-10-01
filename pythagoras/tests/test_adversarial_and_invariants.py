"""
Adversarial tests (syntax attacks, runtime bombs, host-touching code) and
property invariants over fuzzed ASTs.
"""
import math
import os
import random
import tempfile
import time
import unittest

from pythagoras.adapter import PythagorasEngineAdapter
from pythagoras.core import sandbox
from pythagoras.core.euclid_intelligence import EuclidIntelligenceEngine


class TestAdversarialAttacks(unittest.TestCase):
    def setUp(self):
        self.adapter = PythagorasEngineAdapter(sandbox_config=sandbox.SandboxConfig(timeout_sec=2.0))

    def test_syntax_attack_malformed_ast(self):
        for code in ["def foo( x y z ", "for i in range(10) print i", "class ((((BadClass",
                     "import $$$invalid_module$$$", "\x00\x00\x01\x02\x03\xff",
                     "def f():\n  return 1\n def g():\nreturn 2"]:
            res = self.adapter.evaluate_candidate(code)
            self.assertFalse(res["parse_valid"], repr(code))
            self.assertEqual(res["phi_score"], 0.1000)
            self.assertEqual(res["euclid_intelligence_score"], 0.0)

    def test_runtime_bombs_fail_in_isolation(self):
        for code in ["raise ZeroDivisionError('boom')", "x = 1 / 0",
                     "def recurse(): return recurse()\nrecurse()", "import module_that_does_not_exist_xyz123"]:
            res = self.adapter.evaluate_candidate(code)
            self.assertTrue(res["parse_valid"])
            self.assertFalse(res["runtime_valid"], repr(code))
            self.assertEqual(res["runtime_mode"], "isolated_module_execution")

    def test_infinite_loop_is_terminated(self):
        t = time.time()
        res = self.adapter.evaluate_candidate("while True:\n    pass\n")
        self.assertFalse(res["runtime_valid"])
        self.assertIn("timeout", res["reason"])
        self.assertLess(time.time() - t, 10)

    def test_host_write_is_blocked_and_never_executed(self):
        target = os.path.join(tempfile.gettempdir(), "pythagoras_adversarial_probe")
        if os.path.exists(target):
            os.remove(target)
        res = self.adapter.evaluate_candidate(f"open({target!r}, 'w').write('x')")
        self.assertEqual(res["runtime_mode"], "blocked_by_al_haras")
        self.assertFalse(res["runtime_valid"])
        self.assertFalse(os.path.exists(target))

    def test_process_spawn_blocked(self):
        res = self.adapter.evaluate_candidate("import subprocess as sp\nsp.run(['echo', 'hi'])\n")
        self.assertEqual(res["runtime_mode"], "blocked_by_al_haras")

    def test_deferred_findings_reported_not_blocking(self):
        code = "import os\ndef wipe(p):\n    os.remove(p)\n"
        res = self.adapter.evaluate_candidate(code)
        self.assertTrue(res["runtime_valid"])
        self.assertEqual(res["al_haras_audit"]["violations"][0]["scope"], "deferred")

    def test_candidate_never_runs_in_host_process(self):
        marker = "PYTHAGORAS_HOST_MARKER"
        os.environ.pop(marker, None)
        self.adapter.evaluate_candidate(f"import os\nos.environ[{marker!r}] = '1'\n")
        self.assertNotIn(marker, os.environ)

    def test_topological_time_boundaries(self):
        engine = EuclidIntelligenceEngine()
        self.assertGreater(engine.compute_intelligence_scale("def foo(): pass", -100.0)["intelligence_score"], 0.0)
        self.assertTrue(math.isfinite(engine.compute_intelligence_scale("def foo(): pass", 10000.0)["intelligence_score"]))


class TestPropertyInvariantsFuzzing(unittest.TestCase):
    def setUp(self):
        self.adapter = PythagorasEngineAdapter()

    def _snippet(self, seed: int) -> str:
        rnd = random.Random(seed)
        lines = []
        for i in range(rnd.randint(1, 5)):
            t = rnd.choice(["int", "str", "float", "list"])
            lines += [f"def {rnd.choice(['alpha', 'beta', 'gamma'])}_{i}(x: {t}) -> {t}:",
                      f"    var_{i}: int = {rnd.randint(1, 100)}", "    return x"]
        return "\n".join(lines) + "\n"

    def test_invariants_across_fuzzed_asts(self):
        for seed in range(30):
            orig = self._snippet(seed)
            mutated, _ = self.adapter.engine.non_local_operators[0][1](orig, seed)  # real transform (may be no-op)
            inv = self.adapter.verify_property_invariants(orig, mutated, topological_time=1.0)
            self.assertTrue(inv["non_degeneracy_invariant"], seed)
            self.assertTrue(inv["lucas_recurrence_invariant"], seed)
            self.assertTrue(inv["syntax_compilation_invariant"], seed)

    def test_monotonicity_is_an_implication(self):
        """If φ does not rise, the invariant is vacuously satisfied regardless of intelligence."""
        hi = "def f(a: int, b: int) -> int:\n    c: int = a + b\n    return c\n"
        lo = "x = 1\n"
        inv = self.adapter.verify_property_invariants(hi, lo)
        self.assertTrue(inv["monotonicity_invariant"])

    def test_behaviour_invariant_uses_host_runner(self):
        orig = "def double(x):\n    return x * 2\n"
        broken = "def double(x):\n    return x / 2\n"

        def runner(code):
            ns = {}
            exec(code, ns)  # host-owned test runner, trusted host code
            return ns["double"](3) == 6

        self.assertTrue(self.adapter.verify_property_invariants(orig, orig, external_test_runner=runner)["behaviour_preservation_invariant"])
        res = self.adapter.verify_property_invariants(orig, broken, external_test_runner=runner)
        self.assertFalse(res["behaviour_preservation_invariant"])
        self.assertFalse(res["invariants_pass"])


if __name__ == "__main__":
    unittest.main()
