"""Evidence collection must remain truthful without conflating evaluation and release."""
from __future__ import annotations

import json
import subprocess
import sys
from types import SimpleNamespace

from scripts.ci import build_evidence, evaluate_attested


def test_skipped_tests_are_recorded_but_do_not_qualify(tmp_path, monkeypatch):
    junit = tmp_path / "junit.xml"
    junit.write_text(
        '<testsuite><testcase name="passed" />'
        '<testcase name="optional"><skipped /></testcase></testsuite>',
        encoding="utf-8",
    )
    target = tmp_path / "test-evidence.json"
    monkeypatch.setenv("GITHUB_SHA", "expected-commit")
    monkeypatch.setenv("GITHUB_RUN_ID", "1234")
    assert build_evidence.build(junit, target) == 1
    result = json.loads(target.read_text(encoding="utf-8"))
    assert result["status"] == "UNQUALIFIED"
    assert result["tests"] == {"total": 2, "passed": 1, "failed": 0, "skipped": 1}


def test_verified_but_unqualified_evidence_is_evaluated_not_promoted(
    tmp_path, monkeypatch
):
    evidence = tmp_path / "evidence.json"
    evidence.write_text(
        json.dumps({
            "schema": "chronus-ci-test-evidence-v1",
            "commit": "expected-commit",
            "run_id": "1234",
            "status": "UNQUALIFIED",
            "tests": {"total": 2, "failed": 0, "skipped": 1},
        }), encoding="utf-8"
    )
    verdict = tmp_path / "verdict.json"
    monkeypatch.setattr(
        evaluate_attested.subprocess, "run", lambda *args, **kwargs:
        SimpleNamespace(returncode=0)
    )
    monkeypatch.setattr(sys, "argv", [
        "evaluate_attested.py", "--evidence", str(evidence),
        "--expected-commit", "expected-commit",
        "--expected-run-id", "1234",
        "--repository", "HYBAAIDATA/ChronusQiGPU",
        "--output", str(verdict),
    ])
    assert evaluate_attested.main() == 0
    output = json.loads(verdict.read_text(encoding="utf-8"))
    assert output["status"] == "UNQUALIFIED"
    assert output["attestation_verified"] is True
    assert output["test_suite_pass"] is False
    assert set(output["claims"].values()) == {"held"}


def test_failed_attestation_does_not_pass_evaluation(tmp_path, monkeypatch):
    evidence = tmp_path / "evidence.json"
    evidence.write_text(
        json.dumps({
            "schema": "chronus-ci-test-evidence-v1",
            "commit": "expected-commit", "run_id": "1234",
            "status": "PASS",
            "tests": {"total": 1, "failed": 0, "skipped": 0},
        }), encoding="utf-8"
    )
    verdict = tmp_path / "verdict.json"
    monkeypatch.setattr(
        evaluate_attested.subprocess, "run", lambda *args, **kwargs:
        SimpleNamespace(returncode=1)
    )
    monkeypatch.setattr(sys, "argv", [
        "evaluate_attested.py", "--evidence", str(evidence),
        "--expected-commit", "expected-commit", "--expected-run-id", "1234",
        "--repository", "HYBAAIDATA/ChronusQiGPU", "--output", str(verdict),
    ])
    assert evaluate_attested.main() == 1
    output = json.loads(verdict.read_text(encoding="utf-8"))
    assert output["attestation_verified"] is False
    assert set(output["claims"].values()) == {"held"}


def test_facade_module_emits_unqualified_manifest(tmp_path):
    """Executing the module actually emits local diagnostics and fails closed."""
    completed = subprocess.run(
        [sys.executable, "-m", "chronus.core.facade"],
        cwd=tmp_path, capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 1
    output = json.loads(
        (tmp_path / "manifests" / "qualification_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert output["posture"] == "not_qualified"
    assert output["gates_total"] == len(output["gates"])
    assert output["blockers"]
