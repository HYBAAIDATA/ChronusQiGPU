"""TURING release gates: the product registry and the quick benchmark suite."""

import unittest

from turing_universal_quantum_computer.benchmark import BENCHMARKS, run
from turing_universal_quantum_computer.product_registry import CARVED_OUT, MODULES, verify_registry


class ProductRegistryTests(unittest.TestCase):
    def test_every_module_is_registered_and_imports(self):
        report = verify_registry()
        self.assertTrue(report["ok"], report["problems"])
        self.assertEqual(report["modules"], len(MODULES))

    def test_application_modules_record_their_execution_paths(self):
        for entry in MODULES:
            if entry.role == "application" and entry.name not in ("phi_verification",):
                with self.subTest(module=entry.name):
                    self.assertTrue(entry.execution_paths)

    def test_carved_out_modules_name_their_owner(self):
        for name, home, reason in CARVED_OUT:
            with self.subTest(module=name):
                self.assertTrue(home and reason)


class QuickBenchmarkTests(unittest.TestCase):
    def test_correctness_and_meta_benchmarks_pass(self):
        for bench, (axis, _) in BENCHMARKS.items():
            if axis == "cost" or bench == "cross_version_digest":
                continue
            with self.subTest(benchmark=bench):
                artifact = run(bench, quick=True)
                self.assertIs(artifact["passed"], True, artifact.get("error") or artifact["result"])
                self.assertEqual(len(artifact["digest"]), 64)


if __name__ == "__main__":
    unittest.main()
