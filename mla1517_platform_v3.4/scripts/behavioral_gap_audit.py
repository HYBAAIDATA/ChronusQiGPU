#!/usr/bin/env python3
"""Behavioral (not grep-based) audit for the ten production gaps."""

from __future__ import annotations
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd):
    p = subprocess.run(
        cmd, cwd=ROOT, text=True, capture_output=True, env={**os.environ, "PYTHONPATH": "python"}
    )
    return {
        "status": "PASS" if p.returncode == 0 else "FAIL",
        "stdout_tail": p.stdout[-2000:],
        "stderr_tail": p.stderr[-1000:],
    }


checks = {
    "native_shared_cursor_growth_spill_query_seqlock_faults": run(
        ["make", "-C", "host", "behavioral-gap-test"]
    ),
    "native_16777216_boundary_remap": run(["make", "-C", "host", "primedb-boundary-test"]),
    "python_measured_agent_and_control": run(
        [sys.executable, "-m", "unittest", "discover", "-s", "python", "-p", "test*.py"]
    ),
    "telemetry_abi_offsets": run([sys.executable, "scripts/abi_check.py"]),
    "docker_shared_shm_contract": run([sys.executable, "scripts/docker_shm_smoke.py"]),
}
checks["docker_runtime"] = {
    "status": "UNAVAILABLE",
    "reason": "docker executable is unavailable in this sandbox; execute docker compose up and cross-container visibility check on the deployment host",
}
checks["status"] = (
    "PASS"
    if all(v["status"] == "PASS" for k, v in checks.items() if k != "docker_runtime")
    else "FAIL"
)
report = {
    "status": checks["status"],
    "kind": "behavioral_gap_audit",
    "traceability_audit_is_not_substitute": True,
    "checks": checks,
}
Path(ROOT / "results/behavioral_gap_audit.json").write_text(json.dumps(report, indent=2) + "\n")
print(
    json.dumps(
        {
            "status": report["status"],
            "behavioral_checks": 5,
            "docker_runtime": checks["docker_runtime"]["status"],
        },
        indent=2,
    )
)
raise SystemExit(0 if report["status"] == "PASS" else 1)
