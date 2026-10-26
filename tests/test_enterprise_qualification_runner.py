"""Qualification CLI units; every subprocess result is synthetic."""

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SOURCE = (
    Path(__file__).resolve().parents[1] / "docs/qualification/agent1-launch/qualify.py"
)


class EnterpriseQualificationRunnerUnits(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("_enterprise_qualification_units", SOURCE)
        self.runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.runner)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "checkout"
        self.runner.ROOT = self.root
        self.candidate = "a" * 40
        required = (
            "aethel/__init__.py", "aethel/triad.py", "aethel/theseus.py",
            "aethel/enterprise_bridge.py", "tests/test_enterprise_bridge_durable.py",
            "tests/test_enterprise_backup_no_clobber.py", *self.runner.REGRESSIONS,
        )
        for relative in required:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# synthetic source fixture\n")
        self.identities = {
            str(path.relative_to(self.root / "aethel")): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in (self.root / "aethel").rglob("*.py")
        }
        self.attempt = 0

    def invoke(self, *, override=None, xml='<testsuite tests="2"/>', candidate=None, output=None):
        self.attempt += 1
        self.output = output or self.root.parent / f"evidence-{self.attempt}"
        results = [
            (0, self.candidate + "\n", ""), (0, "", ""),
            (0, json.dumps({"aethel_files": self.identities}), ""),
            (0, "durable passed", ""), (0, "optimized passed", ""),
            (0, "backup passed", ""), (0, "source passed", ""),
        ]
        if override:
            for index, result in override.items():
                results[index] = result

        def run(command, **kwargs):
            index = self.process.call_count - 1
            result = results[index]
            if isinstance(result, Exception):
                raise result
            if index == 6 and xml is not None:
                (self.output / "source-regressions.xml").write_text(xml)
            return subprocess.CompletedProcess(command, *result)

        arguments = [
            "qualify.py", "--candidate", candidate if candidate is not None else self.candidate,
            "--python", sys.executable, "--evidence", str(self.output),
        ]
        with (
            patch.object(sys, "argv", arguments),
            patch.object(self.runner.subprocess, "run", side_effect=run) as process,
            patch("sys.stdout", new_callable=io.StringIO),
            patch("sys.stderr", new_callable=io.StringIO),
        ):
            self.process = process
            return self.runner.main()

    def summary(self):
        return json.loads((self.output / "summary.json").read_text())

    def test_invalid_candidate_is_rejected_before_any_command_or_output(self):
        for candidate in ("", "a" * 39, "A" * 40, "g" * 40):
            with self.subTest(candidate=candidate):
                with self.assertRaises(SystemExit) as caught:
                    self.invoke(candidate=candidate)
                self.assertEqual(caught.exception.code, 2)
                self.process.assert_not_called()
                self.assertFalse(self.output.exists())

    def test_evidence_inside_checkout_is_refused_before_creating_directories(self):
        for output in (self.root, self.root / "nested/evidence"):
            with self.subTest(output=output):
                with self.assertRaises(SystemExit) as caught:
                    self.invoke(output=output)
                self.assertEqual(caught.exception.code, 2)
                self.process.assert_not_called()
        self.assertFalse((self.root / "nested").exists())

    def test_existing_evidence_is_never_overwritten(self):
        output = self.root.parent / "existing"
        output.mkdir()
        (output / "summary.json").write_bytes(b"precious evidence")
        with self.assertRaises(FileExistsError):
            self.invoke(output=output)
        self.process.assert_not_called()
        self.assertEqual((output / "summary.json").read_bytes(), b"precious evidence")

    def test_wrong_candidate_or_failed_git_probe_blocks_further_commands(self):
        for result in ((0, "b" * 40, ""), (1, "", "git failed")):
            with self.subTest(result=result):
                self.assertEqual(self.invoke(override={0: result}), 2)
                self.assertEqual(self.process.call_count, 1)
                self.assertEqual(self.summary()["status"], "BLOCKED")
                self.assertEqual(self.summary()["launch_status"], "OPEN")
                self.assertIn("exact candidate", self.summary()["reason"])

    def test_untracked_files_block_installed_probe(self):
        self.assertEqual(self.invoke(override={1: (0, "?? unexpected.py\n", "")}), 2)
        self.assertEqual(self.process.call_count, 2)
        self.assertIn("clean", self.summary()["reason"])

    def test_missing_source_is_listed_and_blocks_installed_probe(self):
        missing = "aethel/triad.py"
        (self.root / missing).unlink()
        self.assertEqual(self.invoke(), 2)
        self.assertEqual(self.process.call_count, 2)
        self.assertEqual(self.summary()["missing"], [missing])

    def test_malformed_or_mismatched_installed_inventory_is_blocked(self):
        for stdout in ("not json", "{}", "null", '{"aethel_files": {}}'):
            with self.subTest(stdout=stdout):
                self.assertEqual(self.invoke(override={2: (0, stdout, "")}), 2)
                self.assertEqual(self.process.call_count, 3)
                self.assertEqual(self.summary()["status"], "BLOCKED")
                self.assertIn("installed", self.summary()["reason"])

    def test_failed_acceptance_stops_at_the_failed_stage(self):
        for index in range(2, 7):
            with self.subTest(index=index):
                self.assertEqual(self.invoke(override={index: (1, "partial", "failure")}), 2)
                self.assertEqual(self.process.call_count, index + 1)
                summary = self.summary()
                self.assertEqual(summary["status"], "BLOCKED" if index == 2 else "FAILED")
                self.assertEqual(summary["launch_status"], "OPEN")
                self.assertEqual(summary["checks"][-1]["status"], "FAIL")

    def test_process_errors_retain_partial_logs_and_block(self):
        for failure in (
            OSError("executable unavailable"),
            subprocess.TimeoutExpired(
                "synthetic", 1, output=b"partial output", stderr=b"partial error",
            ),
        ):
            with self.subTest(failure=failure):
                self.assertEqual(self.invoke(override={0: failure}), 2)
                self.assertEqual(self.process.call_count, 1)
                self.assertEqual(self.summary()["checks"][0]["status"], "BLOCKED")
                log = (self.output / "git-head.log").read_text()
                self.assertIn(str(failure), log)
                if isinstance(failure, subprocess.TimeoutExpired):
                    self.assertIn("partial output", log)
                    self.assertIn("partial error", log)

    def test_missing_junit_report_cannot_be_reported_as_success(self):
        self.assertEqual(self.invoke(xml=None), 2)
        self.assertEqual(self.summary()["status"], "FAILED")
        self.assertIn("JUnit", self.summary()["reason"])

    def test_zero_tests_failures_errors_or_skips_are_incomplete(self):
        for counts in (
            'tests="0"', 'tests="2" failures="1"',
            'tests="2" errors="1"', 'tests="2" skipped="1"',
        ):
            with self.subTest(counts=counts):
                xml = f"<testsuites><testsuite {counts}/></testsuites>"
                self.assertEqual(self.invoke(xml=xml), 2)
                self.assertEqual(self.summary()["status"], "INCOMPLETE")
                self.assertEqual(self.summary()["launch_status"], "OPEN")

    def test_success_aggregates_suites_hashes_artifacts_and_keeps_launch_open(self):
        xml = '<testsuites><testsuite tests="2"/><testsuite tests="3"/></testsuites>'
        self.assertEqual(self.invoke(xml=xml), 0)
        summary = self.summary()
        self.assertEqual(summary["status"], "SCOPED_PREREQUISITES_PASSED_LAUNCH_OPEN")
        self.assertEqual(summary["launch_status"], "OPEN")
        self.assertEqual(summary["source_regression_totals"], {
            "tests": 5, "failures": 0, "errors": 0, "skipped": 0,
        })
        self.assertEqual(len(summary["checks"]), 7)
        for check in summary["checks"]:
            self.assertEqual(check["status"], "PASS")
        self.assertNotIn("summary.json", summary["artifacts"])
        for filename, digest in summary["artifacts"].items():
            actual = hashlib.sha256((self.output / filename).read_bytes()).hexdigest()
            self.assertEqual(actual, digest)
        commands = [entry.args[0] for entry in self.process.call_args_list]
        self.assertEqual(commands[2][1:3], ["-I", "-c"])
        self.assertEqual(commands[4][1:3], ["-I", "-O"])
        self.assertEqual(self.process.call_args_list[2].kwargs["cwd"], self.output)


if __name__ == "__main__":
    unittest.main()
