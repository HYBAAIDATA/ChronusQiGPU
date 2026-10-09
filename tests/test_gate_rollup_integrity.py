from __future__ import annotations

import json
from pathlib import Path

from scripts import assert_gate_rollup as rollup


def _write_gate(results: Path, gate: str, status: str, *, filename: str | None = None) -> None:
    results.mkdir(parents=True, exist_ok=True)
    target = results / (filename or f"{gate}.json")
    target.write_text(
        json.dumps({"gate": gate, "status": status, "reason": "test"}),
        encoding="utf-8",
    )


def test_empty_results_fail_closed(tmp_path: Path):
    report = rollup.evaluate(tmp_path / "results")
    assert not report["passed"]
    assert set(report["missing"]) == set(rollup.REQUIRED_GATES)


def test_complete_pass_set_is_green(tmp_path: Path):
    results = tmp_path / "results"
    for gate in rollup.REQUIRED_GATES:
        _write_gate(results, gate, "PASS")
    report = rollup.evaluate(results)
    assert report["passed"]
    assert report["missing"] == []
    assert report["failed"] == []


def test_failure_and_missing_gate_cannot_be_hidden_by_other_json(tmp_path: Path):
    results = tmp_path / "results"
    for gate in rollup.REQUIRED_GATES[:-1]:
        _write_gate(results, gate, "PASS")
    _write_gate(results, rollup.REQUIRED_GATES[0], "FAIL", filename="duplicate-gate.json")
    (results / "unrelated.json").write_text('{"status":"PASS"}', encoding="utf-8")
    report = rollup.evaluate(results)
    assert not report["passed"]
    assert rollup.REQUIRED_GATES[-1] in report["missing"]
    assert report["duplicates"] == [rollup.REQUIRED_GATES[0]]


def test_skip_is_visible_and_release_strict_mode_blocks_it(tmp_path: Path):
    results = tmp_path / "results"
    for gate in rollup.REQUIRED_GATES:
        _write_gate(results, gate, "PASS")
    _write_gate(results, "conformance-vectors", "SKIP")
    normal = rollup.evaluate(results)
    strict = rollup.evaluate(results, require_no_skip=True)
    assert normal["passed"]
    assert normal["skipped"] == ["conformance-vectors"]
    assert not strict["passed"]
    assert strict["fatal_skips"] == ["conformance-vectors"]
