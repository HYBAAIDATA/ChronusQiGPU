"""The admission gate requires fresh behavioral results, not test-file presence."""

from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from scripts.euclid_v17_integration_gate import run_qualification


def _run(tmp_path: Path, body: str, name: str = "test_required", timeout: float = 30):
    (tmp_path / "test_qualification.py").write_text(body, encoding="utf-8")
    return run_qualification(tmp_path, [f"test_qualification.py::{name}"], timeout=timeout)


def test_gate_accepts_fresh_named_pass(tmp_path):
    result = _run(tmp_path, "def test_required():\n    assert True\n")
    assert result["passed"] and result["tests"] == 1
    assert result["junit_sha256"]


@pytest.mark.parametrize(
    "body",
    [
        "def test_required():\n    assert False\n",
        "import pytest\n@pytest.mark.skip(reason='unavailable')\ndef test_required():\n    pass\n",
        "def test_other():\n    pass\n",
        "raise RuntimeError('collection failure')\n",
        "def test_required(:\n",
    ],
)
def test_gate_rejects_failed_skipped_missing_or_broken_test(tmp_path, body):
    assert not _run(tmp_path, body)["passed"]


def test_gate_rejects_timeout(tmp_path):
    result = _run(
        tmp_path, "def test_required():\n    import time\n    time.sleep(5)\n", timeout=0.1
    )
    assert not result["passed"] and result["error"] == "TimeoutExpired"


def test_gate_rejects_empty_qualification(tmp_path):
    assert not run_qualification(tmp_path, [], timeout=1)["passed"]


@pytest.mark.parametrize("xml", ["<broken", "<testsuites/>", "<unrelated/>"])
def test_gate_rejects_missing_or_malformed_results(tmp_path, monkeypatch, xml):
    def fake_run(command, **kwargs):
        report = Path(
            next(arg.split("=", 1)[1] for arg in command if arg.startswith("--junitxml="))
        )
        report.write_text(xml, encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("scripts.euclid_v17_integration_gate.subprocess.run", fake_run)
    assert not run_qualification(tmp_path, ["test_missing.py::test_required"], timeout=1)["passed"]
