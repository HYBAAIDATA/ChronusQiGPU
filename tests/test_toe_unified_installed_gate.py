"""Verifier orchestration fixtures; not evidence that the real wheels passed.

The real installed artifact verdict is issued only by build_and_verify.py in
its clean venv. These tests exercise the gate's fail-closed evidence handling.
"""

import importlib.util
import json
from pathlib import Path
import sys

import pytest


@pytest.fixture
def verifier(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[1] / "packaging/toe/build_and_verify.py"
    spec = importlib.util.spec_from_file_location("unified_artifact_verifier", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    repo = tmp_path / "source"
    (repo / "tests").mkdir(parents=True)
    work = tmp_path / "check-0"
    work.mkdir()
    monkeypatch.setattr(module, "REPO", repo)
    monkeypatch.setattr(module, "DIST", tmp_path / "dist")
    monkeypatch.setattr(module, "git_sha", lambda: "fixture-commit")
    # Explicit fixture probe: never presented as actual installed import proof.
    monkeypatch.setattr(module, "INSTALLED_UNIFIED_PROBE", 'print("{}")')
    for name in module.UNIFIED_TESTS:
        (repo / "tests" / name).write_text("def test_fixture():\n    assert True\n")
    return module, work


@pytest.mark.parametrize(
    "source,passes,expected_count",
    [
        ("def test_ok():\n    assert True\n", True, 4),
        ("def test_fail():\n    assert False\n", False, 4),
        ("import pytest\ndef test_skip():\n    pytest.skip('not proof')\n", False, 4),
        ("# intentionally empty\n", False, 0),
        ("import nonexistent_unified_fixture_dependency\n", False, 4),
    ],
)
def test_installed_gate_requires_executed_passes(
    verifier, source, passes, expected_count
):
    module, work = verifier
    for name in module.UNIFIED_TESTS:
        (module.REPO / "tests" / name).write_text(source)
    if passes:
        module.installed_unified_check(Path(sys.executable), work, "fixture")
    else:
        with pytest.raises(RuntimeError, match="installed unified verification failed"):
            module.installed_unified_check(Path(sys.executable), work, "fixture")
    output = module.DIST / "installed-unified" / work.name
    evidence = json.loads((output / "evidence.json").read_text())
    assert evidence["test_verdict"] == ("passed" if passes else "failed_or_incomplete")
    assert evidence["production_certification"] == "not_assessed"
    assert evidence["counts"]["tests"] == expected_count
    assert evidence["test_files"] == list(module.UNIFIED_TESTS)
    assert len(evidence["source_tests"]) == 4
    assert evidence["artifacts"]["pytest.log"] == module.sha256(output / "pytest.log")
    assert evidence["command"][1:4] == ["-I", "-m", "pytest"]
    assert "--noconftest" in evidence["command"]
    assert "--import-mode=importlib" in evidence["command"]


def test_installed_gate_rejects_bad_probe_without_reusing_passing_artifacts(
    verifier, monkeypatch
):
    module, work = verifier
    module.installed_unified_check(Path(sys.executable), work, "fixture")
    monkeypatch.setattr(
        module, "INSTALLED_UNIFIED_PROBE", "raise RuntimeError('bad import origin')"
    )
    with pytest.raises(RuntimeError, match="installed unified verification failed"):
        module.installed_unified_check(Path(sys.executable), work, "fixture")
    output = module.DIST / "installed-unified" / work.name
    evidence = json.loads((output / "evidence.json").read_text())
    assert evidence["test_verdict"] == "failed_or_incomplete"
    assert evidence["counts"]["tests"] == 0
    assert "bad import origin" in (output / "import-probe.log").read_text()
    assert not (output / "junit.xml").exists()
    assert "pytest.log" not in evidence["artifacts"]


def test_installed_gate_fails_when_a_required_suite_is_missing(verifier):
    module, work = verifier
    (module.REPO / "tests" / module.UNIFIED_TESTS[-1]).unlink()
    with pytest.raises(RuntimeError, match="installed unified verification failed"):
        module.installed_unified_check(Path(sys.executable), work, "fixture")
    evidence = json.loads(
        (module.DIST / "installed-unified" / work.name / "evidence.json").read_text()
    )
    assert evidence["test_verdict"] == "failed_or_incomplete"
    assert "FileNotFoundError" in evidence["error"]


def test_installed_gate_ignores_host_python_and_pytest_injection(verifier, monkeypatch):
    module, work = verifier
    module._NO_CACHE.update(
        {
            "PYTHONPATH": str(module.REPO),
            "PYTHONHOME": "/nonexistent_fixture_python_home",
            "PYTEST_ADDOPTS": "--invalid-fixture-argument",
            "PYTEST_PLUGINS": "nonexistent_fixture_plugin",
        }
    )
    source = (
        "import os, sys\ndef test_clean_runtime():\n"
        "    assert sys.flags.isolated == 1\n"
        "    assert not any(k in os.environ for k in "
        "('PYTHONPATH', 'PYTHONHOME', 'PYTEST_ADDOPTS', 'PYTEST_PLUGINS'))\n"
        "    assert os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] == '1'\n"
    )
    for name in module.UNIFIED_TESTS:
        (module.REPO / "tests" / name).write_text(source)
    record = module.installed_unified_check(Path(sys.executable), work, "fixture")
    assert record["counts"]["tests"] == 4
    assert record["test_verdict"] == "passed"
