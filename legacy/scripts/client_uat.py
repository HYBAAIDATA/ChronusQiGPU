#!/usr/bin/env python3
"""Run the offline client UAT gates and emit a redacted evidence report.

This command never opens a pool connection and never submits a share. The
OpenCL gate is opt-in because it must run on the client host with the real
hardware attached.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
_SECRET = re.compile(r"(?i)(password|passwd|secret|token|api[_-]?key)\s*[:=|]\s*[^\s,;]+")


def redact(text: str) -> str:
    return _SECRET.sub(r"\1=<redacted>", text)


def run_gate(gate_id: str, command: list[str], timeout: int) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
            env={**os.environ, "PYTHIA_LIVE_SUBMIT": "0"},
        )
    except FileNotFoundError as exc:
        return {
            "id": gate_id,
            "status": "not_run",
            "reason": f"executable unavailable: {exc.filename}",
            "duration_seconds": round(time.perf_counter() - started, 3),
        }
    except subprocess.TimeoutExpired:
        return {
            "id": gate_id,
            "status": "failed",
            "reason": f"timed out after {timeout}s",
            "duration_seconds": round(time.perf_counter() - started, 3),
        }
    output = redact(result.stdout or "")
    return {
        "id": gate_id,
        "status": "passed" if result.returncode == 0 else "failed",
        "exit_code": result.returncode,
        "duration_seconds": round(time.perf_counter() - started, 3),
        "output_tail": output[-2000:],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--hardware", action="store_true", help="run the real OpenCL gate")
    parser.add_argument("--skip-docker", action="store_true")
    args = parser.parse_args(argv)

    gates: list[dict[str, Any]] = [
        run_gate("repository_guard", [sys.executable, "scripts/ci_repo_guard.py"], 60),
        run_gate("production_contract_audit", [sys.executable, "scripts/audit_production_contracts.py"], 120),
        run_gate(
            "focused_production_tests",
            [sys.executable, "-m", "pytest", "-q", "tests/test_production_miner.py", "tests/test_device_identity_contract.py"],
            300,
        ),
    ]
    if not args.skip_docker:
        gates.append(run_gate("compose_contract", ["docker", "compose", "config", "--quiet"], 120))
    if args.hardware:
        gates.append(
            run_gate(
                "opencl_hardware_benchmark",
                [sys.executable, "scripts/benchmark_hashrate.py", "--backend", "opencl", "--batch", "1048576", "--iterations", "5"],
                900,
            )
        )
    else:
        gates.append({"id": "opencl_hardware_benchmark", "status": "not_run", "reason": "requires client host; pass --hardware"})

    required = [gate for gate in gates if gate["id"] != "opencl_hardware_benchmark"]
    failed = [gate for gate in required if gate["status"] == "failed"]
    not_run = [gate for gate in required if gate["status"] == "not_run"]
    report = {
        "uat_status": "failed" if failed else ("conditional" if not_run else "implementation_green"),
        "claim_boundary": "offline implementation validated; live pool acceptance not proven",
        "network_calls": 0,
        "live_share_submission": False,
        "gates": gates,
    }
    if args.json:
        print(json.dumps(report, sort_keys=True))
    else:
        print("PYTHIA CLIENT UAT")
        print(f"Status: {report['uat_status']}")
        print(f"Claim: {report['claim_boundary']}")
        for gate in gates:
            print(f"{gate['status'].upper():9} {gate['id']}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
