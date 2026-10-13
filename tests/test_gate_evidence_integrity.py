"""Hermetic gate-protocol tests; never production-composition evidence."""

import json
import subprocess
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from scripts.assert_gate_rollup import evaluate, load_manifest
from scripts.gate_runner import Outcome, Status, canonical_digest, current_commit, run


def successful_gate(root):
    artifact = root / "results" / "execution.txt"
    artifact.parent.mkdir(exist_ok=True)
    artifact.write_text("gate protocol fixture, not a production voyage")
    return Outcome(Status.PASS, "fixture executed", (str(artifact),))


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "config").mkdir()
        self.manifest = self.root / "config/assurance-gates.json"
        self.manifest.write_text(json.dumps({"schema_version": 1, "mandatory_gates": ["probe"]}))
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.git("add", ".")
        self.git(
            "-c",
            "user.name=GateTest",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "fixture",
        )
        self.sha = current_commit(self.root)
        self.results = self.root / "results"
        self.path = self.results / "probe.json"

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.root), *args], check=True, capture_output=True, text=True
        )

    def report(self, **kwargs):
        return evaluate(self.results, repo_root=self.root, **kwargs)

    def evidence(self):
        result = run("probe", successful_gate, self.root)
        self.assertEqual(result.status, Status.PASS)
        return json.loads(self.path.read_text())

    def mutate(self, change, *, rehash=True):
        payload = self.evidence()
        change(payload)
        if rehash:
            payload["evidence_digest"] = canonical_digest(payload)
        self.path.write_text(json.dumps(payload))
        self.assertFalse(self.report()["passed"])

    def test_actual_runner_and_valid_rollup(self):
        payload = self.evidence()
        self.assertEqual(payload["source_commit"], self.sha)
        self.assertTrue(self.report()["passed"])
        self.assertEqual(self.report()["scope"], "assurance_only_not_api_production_certification")

    def test_api_release_obligations_fail_without_producers(self):
        manifest = Path(__file__).resolve().parents[1] / "config/api-release-gates.json"
        report = self.report(manifest_path=manifest)
        self.assertFalse(report["passed"])
        self.assertEqual(len(report["missing"]), 31)

    def test_empty_directory_fails(self):
        self.assertFalse(self.report()["passed"])
        self.assertEqual(self.report()["missing"], ["probe"])

    def test_missing_result_fails(self):
        self.evidence()
        self.path.unlink()
        self.assertFalse(self.report()["passed"])

    def test_corrupt_json_fails(self):
        self.results.mkdir()
        self.path.write_text("{")
        self.assertFalse(self.report()["passed"])

    def test_nonobject_fails(self):
        self.results.mkdir()
        self.path.write_text("[]")
        self.assertFalse(self.report()["passed"])

    def test_unknown_status_fails(self):
        self.mutate(lambda p: p.update(status="SUCCESS"))

    def test_skipped_mandatory_fails(self):
        self.mutate(lambda p: p.update(status="SKIP"))

    def test_not_run_is_distinct_and_blocks_promotion(self):
        payload = self.evidence()
        payload["status"] = "NOT_RUN"
        payload["evidence_digest"] = canonical_digest(payload)
        self.path.write_text(json.dumps(payload))
        report = self.report()
        self.assertFalse(report["passed"])
        self.assertEqual(report["not_run"], ["probe"])
        self.assertEqual(report["skipped"], [])
        self.assertEqual(report["failed"], [])

    def test_failed_mandatory_fails(self):
        self.mutate(lambda p: p.update(status="FAIL"))

    def test_crashed_gate_fails(self):
        def crash(root):
            raise RuntimeError("do-not-persist-this-secret")

        result = run("probe", crash, self.root)
        self.assertEqual(result.status, Status.ERROR)
        self.assertNotIn("do-not-persist-this-secret", self.path.read_text())
        self.assertFalse(self.report()["passed"])

    def test_stale_commit_fails(self):
        self.mutate(lambda p: p.update(source_commit="0" * 40))

    def test_missing_commit_fails(self):
        self.mutate(lambda p: p.pop("source_commit"))

    def test_commit_argument_cannot_override_checkout(self):
        self.evidence()
        self.assertFalse(self.report(expected_commit="0" * 40)["passed"])

    def test_missing_execution_fails(self):
        self.mutate(lambda p: p.pop("execution"))

    def test_missing_digest_fails(self):
        self.mutate(lambda p: p.pop("evidence_digest"), rehash=False)

    def test_tampered_receipt_fails(self):
        self.mutate(lambda p: p.update(reason="rewritten"), rehash=False)

    def test_tampered_artifact_fails(self):
        self.evidence()
        (self.results / "execution.txt").write_text("tampered")
        self.assertFalse(self.report()["passed"])

    def test_deleted_artifact_fails(self):
        self.evidence()
        (self.results / "execution.txt").unlink()
        self.assertFalse(self.report()["passed"])

    def test_artifact_coverage_fails(self):
        self.mutate(lambda p: p.update(artifact_digests={}))

    def test_path_escape_fails(self):
        self.mutate(
            lambda p: p.update(artifacts=["../private"], artifact_digests={"../private": "a" * 64})
        )

    def test_symlink_escape_fails(self):
        self.evidence()
        with tempfile.NamedTemporaryFile() as outside:
            (self.results / "execution.txt").unlink()
            try:
                (self.results / "execution.txt").symlink_to(outside.name)
            except OSError as exc:
                self.skipTest(f"symlinks require elevated privilege on Windows: {exc}")
            self.assertFalse(self.report()["passed"])

    def test_duplicate_result_fails(self):
        self.evidence()
        (self.results / "duplicate.json").write_text(self.path.read_text())
        self.assertFalse(self.report()["passed"])
        self.assertEqual(self.report()["duplicates"], ["probe"])

    def test_contradictory_result_fails(self):
        payload = self.evidence()
        payload["status"] = "FAIL"
        payload["evidence_digest"] = canonical_digest(payload)
        (self.results / "contradiction.json").write_text(json.dumps(payload))
        self.assertFalse(self.report()["passed"])

    def test_duplicate_json_key_fails(self):
        self.evidence()
        self.path.write_text(
            self.path.read_text().replace('"status": "PASS"', '"status": "FAIL", "status": "PASS"')
        )
        self.assertFalse(self.report()["passed"])

    def test_invalid_timestamp_fails(self):
        self.mutate(lambda p: p.update(finished_at=0))

    def test_boolean_timestamp_fails(self):
        self.mutate(lambda p: p.update(started_at=True))

    def test_legacy_result_fails(self):
        self.mutate(lambda p: p.update(schema_version=1))

    def test_undeclared_gate_fails(self):
        self.evidence()
        run("undeclared", successful_gate, self.root)
        self.assertFalse(self.report()["passed"])

    def test_missing_manifest_fails(self):
        self.evidence()
        self.manifest.unlink()
        self.assertFalse(self.report()["passed"])

    def test_empty_manifest_fails(self):
        self.evidence()
        self.manifest.write_text(json.dumps({"schema_version": 1, "mandatory_gates": []}))
        self.assertFalse(self.report()["passed"])

    def test_duplicate_manifest_gate_fails(self):
        self.manifest.write_text(
            json.dumps({"schema_version": 1, "mandatory_gates": ["probe", "probe"]})
        )
        with self.assertRaises(ValueError):
            load_manifest(self.manifest)

    def test_dirty_checkout_produces_error_not_pass(self):
        self.manifest.write_text(self.manifest.read_text() + " ")
        result = run("probe", successful_gate, self.root)
        self.assertEqual(result.status, Status.ERROR)
        self.assertFalse(self.report()["passed"])

    def test_wrong_outcome_type_produces_error(self):
        result = run("probe", lambda root: True, self.root)
        self.assertEqual(result.status, Status.ERROR)
        self.assertFalse(self.report()["passed"])

    def test_gate_name_cannot_escape_results(self):
        with self.assertRaises(ValueError):
            run("../escape", successful_gate, self.root)

    def test_file_evidence_readback(self):
        self.evidence()
        # Independent JSON readback; not a claim of subsystem restart/replay.
        payload = json.loads(self.path.read_text())
        self.assertEqual(payload["evidence_digest"], canonical_digest(payload))
        self.assertEqual(
            asdict(run("probe", successful_gate, self.root))["source_commit"], self.sha
        )


class ConsumerTests(unittest.TestCase):
    def test_publisher_never_reports_success_for_empty_evidence(self):
        from unittest.mock import patch
        from scripts import publish_check_runs

        env = {
            "GITHUB_TOKEN": "unit-fixture-not-a-credential",
            "GITHUB_REPOSITORY": "unit/fixture",
            "GITHUB_SHA": "0" * 40,
            "GITHUB_API_URL": "https://api.github.invalid",
        }
        with tempfile.TemporaryDirectory() as directory:
            import os

            old = os.getcwd()
            try:
                os.chdir(directory)
                with patch.dict(os.environ, env), patch.object(publish_check_runs, "post") as post:
                    code = publish_check_runs.main()
                self.assertEqual(code, 1)
                self.assertEqual(post.call_args.args[2]["state"], "failure")
            finally:
                os.chdir(old)

    def test_manifest_make_and_implementation_have_same_gate_set(self):
        import ast

        root = Path(__file__).resolve().parents[1]
        manifest = set(load_manifest(root / "config/assurance-gates.json"))
        line = (root / "make/gates.mk").read_text().splitlines()[0]
        self.assertEqual(set(line.split(":=", 1)[1].split()), manifest)
        tree = ast.parse((root / "scripts/gate_impl.py").read_text())
        assignment = next(
            node
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "GATES" for t in node.targets)
        )
        self.assertEqual({k.value for k in assignment.value.keys}, manifest)

    def test_workflow_does_not_swallow_gate_failure(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / ".github/workflows/promotion.yml").read_text()
        self.assertNotIn("make -k gates || true", text)
        self.assertIn("if-no-files-found: error", text)

    def test_resilience_gate_executes_instead_of_checking_only_files(self):
        # Static contract check, not a production-resilience result.
        import ast

        root = Path(__file__).resolve().parents[1]
        tree = ast.parse((root / "scripts/gate_impl.py").read_text())
        resilience = next(
            n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "resilience"
        )
        calls = [n for n in ast.walk(resilience) if isinstance(n, ast.Call)]
        self.assertTrue(
            any(
                isinstance(n.func, ast.Attribute)
                and n.func.attr == "run"
                and isinstance(n.func.value, ast.Name)
                and n.func.value.id == "subprocess"
                for n in calls
            )
        )


if __name__ == "__main__":
    unittest.main()
