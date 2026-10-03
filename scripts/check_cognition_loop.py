#!/usr/bin/env python3
"""Authoritative acceptance command for the cognition-loop mutation (#117)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts" / "cognition-loop-evidence.json"


def run(label: str, command: list[str]) -> dict[str, object]:
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "label": label,
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout[-8000:],
        "stderr": completed.stderr[-8000:],
        "passed": completed.returncode == 0,
    }


def main() -> int:
    checks = [
        run(
            "cognition-compile",
            [sys.executable, "-m", "compileall", "-q", "euclid/cognition"],
        ),
        run(
            "cognition-loop-focused",
            [sys.executable, "-m", "unittest", "-v", "tests.test_cognition_loop"],
        ),
    ]
    payload = {
        "schema": "euclid.cognition-loop.acceptance/1",
        "base_sha": "73cc188746162c2060f155e2d856dfad6d559e1c",
        "passed": all(check["passed"] for check in checks),
        "checks": checks,
        "claim_boundary": {
            "integrated_loop_is_executable_architecture_not_general_intelligence": True,
            "cognition_evidence_is_rehearsal_class": True,
            "imagined_rollouts_are_never_observed_evidence": True,
            "phi_schedule_is_exploratory_parametric_only": True,
            "production_authority": False,
            "general_intelligence": False,
            "external_validation": False,
            "production_ready": False,
        },
        "remaining_gates": [
            "#104-#110 inherited acceptance",
            "CI/check runs",
            "held-out cross-domain benchmark programme",
            "ablation comparison against full architecture",
            "v16.4 baseline comparison",
            "independent external validation",
        ],
    }
    ARTIFACT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))
    print("COGNITION_LOOP=PASS" if payload["passed"] else "COGNITION_LOOP=FAIL")
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
