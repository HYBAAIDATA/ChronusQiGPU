"""Exercise the partial runner's process exit status with isolated test trees."""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RUNNER = Path("docs/qualification/non-mining-enterprise-audit/run_partial.py")
SOURCE = Path(__file__).resolve().parents[1] / RUNNER


class PartialRunnerTests(unittest.TestCase):
    def run_fixture(self, source, optimize):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = root / RUNNER
            runner.parent.mkdir(parents=True)
            shutil.copyfile(SOURCE, runner)
            tests = root / "tests"
            tests.mkdir()
            if source is not None:
                (tests / "test_enterprise_audit_guardrails.py").write_text(source)
            return subprocess.run(
                [sys.executable, *(["-O"] if optimize else []), str(runner)],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=15,
            )

    def test_empty_discovery_fails_before_running(self):
        for source in (None, "import unittest\n"):
            for optimize in (False, True):
                with self.subTest(source=source, optimize=optimize):
                    result = self.run_fixture(source, optimize)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("No tests discovered", result.stderr)
                    self.assertNotIn("Ran 0 tests", result.stderr)

    def test_nonempty_suite_preserves_success_and_failure(self):
        for passed in (False, True):
            source = (
                "import unittest\n"
                "class Fixture(unittest.TestCase):\n"
                "    def test_result(self):\n"
                f"        self.assertTrue({passed})\n"
            )
            for optimize in (False, True):
                with self.subTest(passed=passed, optimize=optimize):
                    result = self.run_fixture(source, optimize)
                    self.assertEqual(result.returncode, 0 if passed else 1)
                    self.assertIn("Ran 1 test", result.stderr)
                    self.assertNotIn("No tests discovered", result.stderr)

    def test_import_errors_remain_failures(self):
        for optimize in (False, True):
            with self.subTest(optimize=optimize):
                result = self.run_fixture("raise ImportError('fixture error')\n", optimize)
                self.assertEqual(result.returncode, 1)
                self.assertIn("fixture error", result.stderr)
                self.assertIn("FAILED (errors=1)", result.stderr)


if __name__ == "__main__":
    unittest.main()
