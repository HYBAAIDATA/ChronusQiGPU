from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_every_supplied_lhras_blueprint_module_and_invariant():
    result = subprocess.run(
        [sys.executable, "experiments/run_lhras_blueprint.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"module_fail": 0' in result.stdout
    assert '"test_fail": 0' in result.stdout
