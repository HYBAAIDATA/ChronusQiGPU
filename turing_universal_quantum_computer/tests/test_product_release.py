"""TURING release gates: the product registry and the quick benchmark suite."""

from contextlib import redirect_stdout
from importlib.metadata import version
from io import StringIO
import unittest
from unittest.mock import patch

from turing_universal_quantum_computer import benchmark
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
    def test_provenance_resolves_distribution_version(self):
        self.assertEqual(
            benchmark.provenance()["turing_version"],
            version("hyba-turing-vqc"),
        )

    def test_correctness_and_meta_benchmarks_pass(self):
        for bench, (axis, _) in BENCHMARKS.items():
            if axis == "cost" or bench == "cross_version_digest":
                continue
            with self.subTest(benchmark=bench):
                artifact = run(bench, quick=True)
                self.assertIs(artifact["passed"], True, artifact.get("error") or artifact["result"])
                self.assertEqual(len(artifact["digest"]), 64)

    def test_cli_fails_when_required_execution_evidence_is_incomplete(self):
        for required in ("pipeline_custody_replay", "ten_thousand_qubit_vqc_voyage"):
            summary = {
                "passed": [],
                "failed": [],
                "incomplete": [required],
                "digest": "0123456789abcdef",
            }
            with self.subTest(benchmark=required):
                with patch.object(
                    benchmark, "run_all", return_value=summary
                ), redirect_stdout(StringIO()):
                    self.assertEqual(benchmark.main(["--quick"]), 1)

    def test_cli_allows_unconfigured_cross_version_benchmark_to_remain_incomplete(self):
        summary = {
            "passed": [],
            "failed": [],
            "incomplete": ["cross_version_digest"],
            "digest": "0123456789abcdef",
        }
        with patch.object(benchmark, "run_all", return_value=summary), redirect_stdout(
            StringIO()
        ):
            self.assertEqual(benchmark.main(["--quick"]), 0)


if __name__ == "__main__":
    unittest.main()
