"""Release command/CLI compatibility only, not a release-gate PASS claim."""
import json
from pathlib import Path
import shlex
import subprocess
import sys


def test_make_release_rollup_invokes_supported_fail_closed_cli():
    root = Path(__file__).resolve().parents[1]
    recipe = (root / "make/gates.mk").read_text().split("release-gate: gates\n", 1)[1]
    recipe = recipe.split("\nrule7-no-float:", 1)[0]
    command = next(line.strip() for line in recipe.splitlines() if "scripts/assert_gate_rollup.py" in line)
    args = shlex.split(command)
    result = subprocess.run(
        [sys.executable, *args[1:]], cwd=root, capture_output=True, text=True, timeout=30
    )
    # 0/1 are evidence verdicts; 2 is the original unsupported-argument failure.
    assert result.returncode in (0, 1), result.stderr
    report = json.loads(result.stdout)
    assert report["passed"] is (result.returncode == 0)
