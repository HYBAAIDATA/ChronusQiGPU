"""Executes scripts/ci/triad_cross_checks.py and asserts no cross-triad check FAILs.

GAP results are reported findings (missing capability), not failures; this test only
guards against regressions in behaviour that currently PASSes.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.real

ROOT = Path(__file__).resolve().parents[1]


def test_triad_cross_checks_have_no_failures(tmp_path: Path) -> None:
    out = tmp_path / "cross.json"
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    env.pop("CHRONUS_EXECUTION_BASE_URL", None)
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "ci" / "triad_cross_checks.py"), "--out", str(out)],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=600,
    )
    assert proc.returncode == 0, proc.stderr
    doc = json.loads(out.read_text())
    failures = [r for r in doc["results"] if r["status"] == "FAIL"]
    assert not failures, failures
    ids = {r["id"] for r in doc["results"]}
    assert {"X1", "X2a", "X2d", "X3", "X4", "X5a", "X5b", "X8", "X8b"} <= ids
    assert doc["environment"]["physical_device_evidence"] is False
