"""The CI test-execution gate must not count skipped or missing tests as passing."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.real

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("test_execution_gate", ROOT / "scripts/ci/test_execution_gate.py")
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


def _junit(tmp_path: Path, cases: list[str]) -> Path:
    path = tmp_path / "junit.xml"
    path.write_text('<?xml version="1.0"?><testsuites><testsuite name="pytest">' + "".join(cases) + "</testsuite></testsuites>")
    return path


def _policy(tmp_path: Path, **suite) -> Path:
    path = tmp_path / "policy.json"
    path.write_text(json.dumps({"suites": {"s": {"min_passed": 2, "max_skipped": 5, "allowed_skip_reasons": ["No physical OpenCL runtime"], **suite}}}))
    return path


PASS = '<testcase classname="t" name="p{}" />'


def _run(tmp_path, cases, **suite) -> int:
    return gate.main(["--suite", "s", "--junit", str(_junit(tmp_path, cases)), "--policy", str(_policy(tmp_path, **suite))])


def test_all_executed_passes(tmp_path):
    assert _run(tmp_path, [PASS.format(1), PASS.format(2)]) == 0


def test_floor_catches_vanished_tests(tmp_path):
    assert _run(tmp_path, [PASS.format(1)]) == 1


def test_failure_and_error_fail(tmp_path):
    assert _run(tmp_path, [PASS.format(1), PASS.format(2), '<testcase classname="t" name="f"><failure message="x"/></testcase>']) == 1
    assert _run(tmp_path, [PASS.format(1), PASS.format(2), '<testcase classname="t" name="e"><error message="x"/></testcase>']) == 1


def test_only_allowed_skip_reasons_pass(tmp_path):
    allowed = '<testcase classname="t" name="s"><skipped type="pytest.skip" message="No physical OpenCL runtime"/></testcase>'
    other = '<testcase classname="t" name="s2"><skipped type="pytest.skip" message="database unavailable"/></testcase>'
    assert _run(tmp_path, [PASS.format(1), PASS.format(2), allowed]) == 0
    assert _run(tmp_path, [PASS.format(1), PASS.format(2), other]) == 1
    assert _run(tmp_path, [PASS.format(1), PASS.format(2), allowed], max_skipped=0) == 1


def test_module_level_skip_reason_is_read_from_text(tmp_path):
    module = '<testcase classname="" name="tests.m"><skipped message="collection skipped">No physical OpenCL runtime</skipped></testcase>'
    assert _run(tmp_path, [PASS.format(1), PASS.format(2), module]) == 0


def test_xfail_must_be_recorded_in_known_failures(tmp_path):
    known = '<testcase classname="t" name="x"><skipped type="pytest.xfail" message="known failure recorded in tests/known-failures.txt"/></testcase>'
    unknown = '<testcase classname="t" name="y"><skipped type="pytest.xfail" message="flaky"/></testcase>'
    assert _run(tmp_path, [PASS.format(1), PASS.format(2), known]) == 0
    assert _run(tmp_path, [PASS.format(1), PASS.format(2), unknown]) == 1


def test_unreadable_input_is_exit_2(tmp_path):
    assert gate.main(["--suite", "s", "--junit", str(tmp_path / "missing.xml"), "--policy", str(_policy(tmp_path))]) == 2


def test_policy_floors_match_the_ci_suites():
    policy = json.loads((ROOT / "scripts/ci/test_execution_policy.json").read_text())["suites"]
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    for suite in policy:
        assert f"--suite {suite} " in workflow
    assert policy["main"]["min_passed"] >= 2500
    assert "ci-required:" in workflow
