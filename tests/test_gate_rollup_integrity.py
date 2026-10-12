"""Hermetic protocol fixtures, not backend or operational readiness evidence."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts import assert_gate_rollup as rollup
from scripts.gate_runner import Outcome, Status, run

GATES = ["probe", "conformance-vectors"]


def _root(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config/assurance-gates.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "mandatory_gates": GATES,
            }
        )
    )
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.name=RollupFixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        check=True,
    )
    return tmp_path


def _write(root, gate, status, *, duplicate=False):
    run(gate, lambda _: Outcome(Status(status), "isolated protocol fixture"), root)
    if duplicate:
        (root / "results/duplicate-gate.json").write_bytes(
            (root / f"results/{gate}.json").read_bytes()
        )


def _report(root):
    return rollup.evaluate(root / "results", repo_root=root)


def test_empty_results_fail_closed(tmp_path: Path):
    report = _report(_root(tmp_path))
    assert not report["passed"]
    assert set(report["missing"]) == set(GATES)


def test_complete_commit_bound_pass_set_is_green_within_fixture_scope(tmp_path: Path):
    root = _root(tmp_path)
    for gate in GATES:
        _write(root, gate, "PASS")
    report = _report(root)
    assert report["passed"]
    assert report["missing"] == []
    assert report["failed"] == []


def test_failure_and_missing_gate_cannot_be_hidden_by_other_json(tmp_path: Path):
    root = _root(tmp_path)
    _write(root, GATES[0], "FAIL", duplicate=True)
    (root / "results/unrelated.json").write_text('{"status":"PASS"}')
    report = _report(root)
    assert not report["passed"]
    assert GATES[-1] in report["missing"]
    assert report["duplicates"] == [GATES[0]]


def test_skip_is_visible_and_always_blocks_mandatory_rollup(tmp_path: Path):
    root = _root(tmp_path)
    for gate in GATES:
        _write(root, gate, "PASS")
    _write(root, "conformance-vectors", "SKIP")
    report = _report(root)
    assert not report["passed"]
    assert report["skipped"] == ["conformance-vectors"]


def test_not_run_is_not_skip_or_pass(tmp_path: Path):
    root = _root(tmp_path)
    for gate in GATES:
        _write(root, gate, "PASS")
    _write(root, "conformance-vectors", "NOT_RUN")
    report = _report(root)
    assert not report["passed"]
    assert report["not_run"] == ["conformance-vectors"]
    assert report["skipped"] == []
