"""Regression: legacy local checks must never promote production claims.

All runner results below are mocked, intentionally testing the *negative*
qualification boundary. They are not release or runtime evidence.
"""
import importlib.util
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.simulated


def _load_manifest():
    path = Path(__file__).resolve().parents[1] / "scripts" / "ci" / "manifest.py"
    spec = importlib.util.spec_from_file_location("chronus_legacy_manifest_truth", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("local_checks_pass,exit_code", [(True, 0), (False, 1)])
def test_local_gates_do_not_issue_production_qualification(
    monkeypatch, tmp_path, local_checks_pass, exit_code
):
    module = _load_manifest()
    monkeypatch.setattr(module, "REPO_ROOT", str(tmp_path))
    monkeypatch.setattr(module, "run_cmd", lambda _command: local_checks_pass)
    monkeypatch.setattr(module.shutil, "which", lambda _name: None)
    monkeypatch.setattr(module.subprocess, "check_output", lambda *args, **kwargs: "a" * 40)

    with pytest.raises(SystemExit) as outcome:
        module.main()

    assert outcome.value.code == exit_code
    data = json.loads((tmp_path / "PRODUCTION_QUALIFIED.json").read_text(encoding="utf-8"))
    assert data["status"] == "NOT_QUALIFIED"
    assert data["local_ci_checks"] == ("PASS" if local_checks_pass else "FAIL")
    assert data["signature"] is None
    assert data["verification_procedure"]["algorithm"] is None
    assert data["gates"]["mypy_strict"] is None
    assert data["measurements"]["submit_rate_achieved_sec"] is None
    assert data["measurements"]["shares_local_dropped"] is None
