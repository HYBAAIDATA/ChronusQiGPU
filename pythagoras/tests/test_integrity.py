"""
Integrity tests: the metric cannot be raised by unused code, evolution preserves behaviour,
and SALAMANDER (HEAL) repairs v12.0 output.
"""
import ast
import glob
import os
import unittest

from pythagoras.adapter import PythagorasEngineAdapter
from pythagoras.core.phi_metric import PhiResonanceCalculator
from pythagoras.core.primitives import ASTPrimitives, OPERATOR_REGISTRY

BENCH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "benchmarks")

# Output produced by v12.0 on its own runner sample (kept verbatim as a regression fixture).
V12_OUTPUT = '''# Non-Local AST Refactoring: Extracted helper function for manifold escape
def _decomposed_subroutine(val: float) -> float:
    return val * 0.618034

# Non-Local AST Refactoring: Extracted helper function for manifold escape
def _decomposed_subroutine(val: float) -> float:
    return val * 0.618034

class _DecomposedHelperModule:
    @staticmethod
    def execute_helper(x: float) -> float:
        return x * 0.618034


class DataPipeline:
    def process(self, items: list) -> list:
        res: list = []
        for i in items:
            res.append(i * 0.618034)
        return res
# Type annotations verified
x_var: float = 1.0
# Type annotations verified
x_var: float = 1.0

# Type annotations verified
x_var: float = 1.0
'''

V12_ORIGINAL = '''
class DataPipeline:
    def process(self, items: list) -> list:
        res: list = []
        for i in items:
            res.append(i * 0.618034)
        return res
'''

EXERCISES = {
    "data_processor.py": "DataProcessor().process_records([1, 2, 3])",
    "http_router.py": "(lambda r: (r.add_route('/a', lambda d: d), r.handle_request('/a', {'x': 1}), r.handle_request('/b', {}))[1:])(HTTPRouter())",
    "json_parser.py": "(SimpleJSONParser().parse_number(' 3.5 '), SimpleJSONParser().parse_string(' \"hi\" '))",
    "matrix_math.py": "multiply_matrices([[1, 2], [3, 4]], [[5, 6], [7, 8]])",
    "phi_resonance.py": "calculate_resonance(1.0, 2.0, 3.0)",
    "search_engine.py": "(lambda s: (s.add_document(1, 'hello world'), s.add_document(2, 'bye'), s.query('hello'))[2])(SearchEngine('idx'))",
}


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def _run(code: str, expr: str):
    ns = {"__name__": "bench"}
    exec(compile(code, "<bench>", "exec"), ns)  # trusted benchmark code
    return eval(expr, ns)


class TestMetricIntegrity(unittest.TestCase):
    def setUp(self):
        self.calc = PhiResonanceCalculator()

    def test_v12_junk_patterns_do_not_raise_phi(self):
        for path in sorted(glob.glob(os.path.join(BENCH, "*.py"))):
            src = _read(path)
            base = self.calc.compute_phi(src)
            junk = [
                src + "\n# Type annotations verified\nx_var: float = 1.0\n" * 4,
                src + "\nif False:\n    _unreachable_debug_flag = 0.618034\n",
                "def _decomposed_subroutine(val: float) -> float:\n    return val * 0.618034\n\n" * 3 + src,
                "class _DecomposedHelperModule:\n    @staticmethod\n    def execute_helper(x: float) -> float:\n        return x * 0.618034\n\n" + src,
                '"""Module Coherence Documented via PYTHAGORAS"""\n' + src,
            ]
            for j in junk:
                self.assertLessEqual(self.calc.compute_phi(j), base, os.path.basename(path))

    def test_contradictory_annotation_lowers_coherence(self):
        ok = "def f():\n    out: list = []\n    return out\n"
        bad = "def f():\n    out: float = []\n    return out\n"
        self.assertLess(self.calc.components(bad)["annotation_coherence"], self.calc.components(ok)["annotation_coherence"])

    def test_target_phi_is_used(self):
        src = _read(os.path.join(BENCH, "matrix_math.py"))
        self.assertNotEqual(PhiResonanceCalculator(0.618033988749895).compute_phi(src),
                            PhiResonanceCalculator(0.5).compute_phi(src))


class TestEvolutionPreservesBehaviour(unittest.TestCase):
    def test_benchmarks_behave_identically_after_evolution(self):
        for fname, expr in EXERCISES.items():
            src = _read(os.path.join(BENCH, fname))
            for seed in (1, 42):
                res = PythagorasEngineAdapter().evolve(fname, src, generations=10, seed=seed)
                self.assertEqual(_run(src, expr), _run(res["final_code"], expr), f"{fname} seed={seed}")
                self.assertGreaterEqual(res["final_phi"], res["initial_phi"])

    def test_behaviour_changing_operators_need_a_runner(self):
        names = [n for n, _ in ASTPrimitives.get_all_operators()]
        self.assertNotIn("MUTATE:swap_binary_operator", names)
        self.assertNotIn("MUTATE:rename_variable", names)
        r = PythagorasEngineAdapter().evolve("x.py", "def f(a, b):\n    return a + b\n", generations=3)
        self.assertFalse(r["behaviour_changing_operators_enabled"])

    def test_extract_method_preserves_results(self):
        src = (
            "class Stats:\n"
            "    def summarise(self, data):\n"
            "        total = 0\n"
            "        count = 0\n"
            "        for d in data:\n"
            "            total += d\n"
            "            count += 1\n"
            "        mean = total / count if count else 0.0\n"
            "        spread = max(data) - min(data) if data else 0.0\n"
            "        return {'mean': mean, 'spread': spread}\n"
        )
        out, _ = OPERATOR_REGISTRY["NON_LOCAL:function_split_refactor"](src, 0)
        self.assertNotEqual(out, src)
        for data in ([1, 2, 3, 10], [], [5]):
            self.assertEqual(_run(src, f"Stats().summarise({data})"), _run(out, f"Stats().summarise({data})"))


class TestSalamanderHealsV12Output(unittest.TestCase):
    def test_heal_removes_v12_artifacts_and_keeps_behaviour(self):
        healed, _ = OPERATOR_REGISTRY["HEAL:dead_code_elimination"](V12_OUTPUT, 0)
        self.assertEqual(healed.count("def _decomposed_subroutine"), 1)
        self.assertEqual(healed.count("x_var: float = 1.0"), 1)
        self.assertNotIn("Type annotations verified\nx_var: float = 1.0\n# Type", healed)
        self.assertEqual(_run(V12_OUTPUT, "DataPipeline().process([1, 2])"), _run(healed, "DataPipeline().process([1, 2])"))
        calc = PhiResonanceCalculator()
        self.assertGreater(calc.compute_phi(healed), calc.compute_phi(V12_OUTPUT))

    def test_v12_output_scores_below_its_input(self):
        calc = PhiResonanceCalculator()
        self.assertLess(calc.compute_phi(V12_OUTPUT), calc.compute_phi(V12_ORIGINAL))


if __name__ == "__main__":
    unittest.main()
