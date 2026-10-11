#!/usr/bin/env python3
"""#108 acceptance: inherited #107 first, then focused deterministic tests."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts" / "salamander108-evidence.json"


def run(command: list[str]) -> dict[str, object]:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
        "state": "PASS" if proc.returncode == 0 else "FAIL",
    }


def main() -> int:
    inherited = run([sys.executable, "chronus/scripts/check_chronus107.py"])
    focused = run([sys.executable, "-m", "pytest", "-q", "tests/test_salamander_autonomic.py"])
    payload = {
        "schema": "salamander.autonomic.acceptance.v1",
        "base_sha": "83c187e2cf9a6ef60271c3c6bfcb1b5669e0321e",
        "chronus104_corpus_sha256": "0b4035e138256cfed08ba5d9e1b0058dc8e7c0dbce2e0ccb50039254de4e1712",
        "inherited_chronus107": inherited,
        "focused": focused,
        "preserved_truth": {
            "physical_opencl": "PHYSICAL_EVIDENCE_REQUIRED",
            "authorized_live_pool": "NOT_RUN",
            "f64": "UNSUPPORTED",
            "opencl.BINET_EXACT": "UNSUPPORTED",
            "FOLDED_NATIVE": "OPEN",
            "ci": "NOT_REPORTED",
        },
    }
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["evidence_sha256"] = hashlib.sha256(body).hexdigest()
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print("INHERITED_CHRONUS107=" + str(inherited["state"]))
    print("SALAMANDER108_FOCUSED=" + str(focused["state"]))
    print("PHYSICAL_OPENCL=PHYSICAL_EVIDENCE_REQUIRED")
    print("AUTHORIZED_LIVE_POOL=NOT_RUN")
    print("F64=UNSUPPORTED")
    print("OPENCL_BINET_EXACT=UNSUPPORTED")
    print("FOLDED_NATIVE=OPEN")
    print("CI=NOT_REPORTED")
    return 0 if inherited["returncode"] == 0 and focused["returncode"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())