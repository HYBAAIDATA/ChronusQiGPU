"""Evidence tests for substrate/hardware independence of the exact model.

These tests establish representation/backend invariance. They do not prove a
physical claim that quantum mechanics is reducible to this software model.
"""
import ast
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))
from chronos.lucas_engine import binet_exact, fibonacci_pair, lucas, lucas_recurrence
from chronos.lucas_datapath import DatapathConfig, SpatialLucasPipeline
from chronos.lucas_runtime import LucasRuntime, ReferenceLucasBackend
from chronos.sparse import lucas_sparse

ROOT = Path(__file__).resolve().parent.parent

class SubstrateAgnosticTests(unittest.TestCase):
    def test_exact_algorithm_is_representation_invariant(self):
        for n in range(0, 1001):
            self.assertEqual(lucas(n), binet_exact(n))
            self.assertEqual(lucas(n), lucas_sparse(n))
            f, f1 = fibonacci_pair(n)
            self.assertEqual(lucas(n), 2 * f1 - f)

    def test_hardware_label_does_not_change_exact_record(self):
        a = SpatialLucasPipeline(DatapathConfig(32, 6, 1000, 'substrate-a'))
        b = SpatialLucasPipeline(DatapathConfig(32, 6, 1000, 'substrate-b'))
        for left, right in zip(a.process_batch(range(64)), b.process_batch(range(64))):
            self.assertEqual(left.canonical_payload() | {'backend': 'normalized'},
                             right.canonical_payload() | {'backend': 'normalized'})

    def test_runtime_and_datapath_agree(self):
        runtime = LucasRuntime(ReferenceLucasBackend())
        runtime_records = runtime.evaluate(range(32))
        pipeline_records = SpatialLucasPipeline(DatapathConfig(256, 6, 1000)).process_batch(range(32))
        self.assertEqual([r.index for r in runtime_records], [r.rung for r in pipeline_records])
        self.assertEqual([r.lucas_value for r in runtime_records], [r.value for r in pipeline_records])

    def test_exact_path_has_no_float_or_numpy_dependency(self):
        for name in ('lucas_engine.py', 'lucas_datapath.py', 'sparse.py'):
            tree = ast.parse((ROOT / 'src' / 'chronos' / name).read_text())
            imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
            imports += [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names]
            self.assertNotIn('numpy', imports, name)
            self.assertNotIn('math', imports, name)

if __name__ == '__main__': unittest.main()
