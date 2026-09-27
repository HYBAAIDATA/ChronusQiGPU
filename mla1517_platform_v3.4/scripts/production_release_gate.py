#!/usr/bin/env python3
"""Run production checks without converting unavailable tooling into PASS."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


def run_check(name: str, command: list[str], *, cwd: Path = ROOT) -> dict[str, object]:
    if shutil.which(command[0]) is None:
        return {"name": name, "status": "NOT_RUN", "reason": f"{command[0]} unavailable"}
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env={**os.environ, "PYTHONPATH": str(ROOT / "python")},
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"name": name, "status": "FAIL", "reason": "timeout"}
    return {
        "name": name,
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-2000:],
        "stderr_tail": completed.stderr[-2000:],
    }


def main() -> int:
    RESULTS.mkdir(exist_ok=True)
    checks = [
        run_check("python_unittest_discover", [sys.executable, "-m", "unittest", "discover", "-s", "python", "-p", "test*.py"]),
        run_check("python_compileall", [sys.executable, "-m", "compileall", "-q", "python"]),
        run_check("make_test", ["make", "test"]),
        run_check("make_release_target", ["make", "release"]),
        run_check("docker_build", ["docker", "build", "-f", "Dockerfile.production", "."], cwd=ROOT / "docker"),
    ]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "summary": {
            "PASS": sum(item["status"] == "PASS" for item in checks),
            "FAIL": sum(item["status"] == "FAIL" for item in checks),
            "NOT_RUN": sum(item["status"] == "NOT_RUN" for item in checks),
        },
        "hardware_claim": "not measured by this gate",
        "pool_acceptance": "not measured by this gate",
    }
    path = RESULTS / "production_release_gate.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 1 if report["summary"]["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
