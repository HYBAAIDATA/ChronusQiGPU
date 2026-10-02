#!/usr/bin/env python3
"""Authoritative acceptance command for the post-#108 mutation."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts" / "euclid-genesis-kairos-qualification-evidence.json"


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
            "inherited-108",
            [sys.executable, "scripts/check_salamander_autonomic.py"],
        ),
        run(
            "genesis-kairos-focused",
            [
                sys.executable,
                "-m",
                "unittest",
                "-v",
                "tests.test_euclid_genesis_kairos_qualification",
            ],
        ),
    ]
    payload = {
        "schema": "euclid.genesis-kairos.acceptance/1",
        "base_sha": "d3eef9a71bccac5a59b27aff7283c4d98f06cc21",
        "passed": all(check["passed"] for check in checks),
        "checks": checks,
        "claim_boundary": {
            "kairos_is_rehearsal_not_production": True,
            "production_ready": False,
            "external_validation": False,
            "general_intelligence": False,
        },
        "remaining_gates": [
            "#104-#108 inherited acceptance",
            "CI/check runs",
            "physical OpenCL/device evidence",
            "authorized live-pool evidence",
            "independent external validation",
            "enterprise compatibility execution and controlled merge",
        ],
    }
    ARTIFACT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())