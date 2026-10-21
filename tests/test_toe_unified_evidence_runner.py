"""Executed evidence must distinguish passing, failing, skipped and empty runs."""

import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    "source,expected_exit,expected_verdict",
    [
        ("def test_ok():\n    assert True\n", 0, "passed"),
        ("def test_bad():\n    assert False\n", 1, "failed_or_incomplete"),
        (
            "import pytest\ndef test_skip():\n    pytest.skip('unavailable evidence')\n",
            1,
            "failed_or_incomplete",
        ),
        ("# No tests were executed.\n", 1, "failed_or_incomplete"),
    ],
)
def test_runner_records_executed_outcome_and_discards_stale_evidence(
    tmp_path, source, expected_exit, expected_verdict
):
    root = tmp_path / "sandbox"
    (root / "scripts").mkdir(parents=True)
    (root / "tests").mkdir()
    script = root / "scripts/verify_unified_enterprise.py"
    shutil.copyfile(Path(__file__).resolve().parents[1] / "scripts" / script.name, script)
    (root / "tests/test_toe_unified_fixture.py").write_text(source)
    output = root / "artifacts/unified-enterprise"
    output.mkdir(parents=True)
    (output / "evidence.json").write_text('{"test_verdict": "stale_pass"}')
    (output / "junit.xml").write_text('<testsuite tests="9000" failures="0"/>')
    result = subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True, timeout=60
    )
    assert result.returncode == expected_exit, result.stdout + result.stderr
    evidence = json.loads((output / "evidence.json").read_text())
    assert evidence["test_verdict"] == expected_verdict
    assert evidence["production_certification"] == "not_assessed"
    assert evidence["counts"]["tests"] in (0, 1)
    assert set(evidence["artifacts"]) == {"source-manifest.json", "pytest.log", "junit.xml"}
    if "skip" in source:
        assert evidence["counts"]["skipped"] == 1
