#!/usr/bin/env python3
"""Deterministic release gate for the MLA1517 reference distribution.

This gate is intentionally toolchain-light.  It verifies the contracts that
can be checked in any CI runner and records unavailable external toolchains
as explicit evidence rather than silently treating them as passes.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


def _run(command: list[str]) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "UNAVAILABLE", "detail": str(exc)}
    return {
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-2000:],
        "stderr_tail": completed.stderr[-2000:],
    }


def _contract_check() -> dict[str, Any]:
    contract = json.loads((ROOT / "hardware/mla1517_igpu_v1.json").read_text())
    topology = contract["topology"]
    state = contract["state_model"]
    required = {
        "warp_width": 32,
        "logical_partitions": 32,
        "icosahedral_execution_nodes": 12,
        "dodecahedral_memory_nodes": 20,
    }
    observed = {key: topology.get(key) for key in required}
    checks = {
        **{key: observed[key] == value for key, value in required.items()},
        "state_dimensions": state.get("dimensions") == 11,
        "hot_descriptor_bytes": state.get("hot_transport_descriptor_bytes") == 64,
        "route_control_slot": state.get("route_control_slot") is True,
        "supervision_contract": contract.get("supervision", {}).get(
            "enabled_by_explicit_deployment_flag"
        )
        is True,
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "observed": observed,
    }


def _policy_check() -> dict[str, Any]:
    behavior = json.loads((ROOT / "behavior.json").read_text())
    source = (ROOT / "python/manifold_pool_coordinator.py").read_text()
    checks = {
        "unlimited_claim_disabled": behavior.get("unlimited_speed_or_capacity_claim") is False,
        "measured_only": behavior.get("performance_claim_policy") == "measured_only",
        "submission_fail_closed": "negotiated MLA1517-to-Stratum algorithm adapter" in source,
        "no_dev_mem_implicit_open": "/dev/mem" not in (ROOT / "host/mla1517_mmio.c").read_text(),
        "headless_requires_device": "MLA1517_MMIO_DEVICE"
        in (ROOT / "docker/headless-miner-entrypoint.sh").read_text(),
    }
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks}


def _release_status(checks: dict[str, Any]) -> str:
    statuses = [
        value["status"]
        for value in checks.values()
        if isinstance(value, dict) and "status" in value
    ]
    if not statuses or any(status not in {"PASS", "NOT_RUN"} for status in statuses):
        return "FAIL"
    if any(status == "NOT_RUN" for status in statuses):
        return "BLOCKED"
    return "PASS"


def main() -> int:
    RESULTS.mkdir(exist_ok=True)
    checks: dict[str, Any] = {
        "python_compile": _run([sys.executable, "-m", "compileall", "-q", "python", "scripts"]),
        "python_unittest": _run(
            [sys.executable, "-m", "unittest", "discover", "-s", "python", "-p", "test*.py"]
        ),
        "native_contract_tests": _run(
            [
                "make",
                "-C",
                "host",
                "aethel-test",
                "primedb-storage-test",
                "primedb-boundary-test",
                "behavioral-gap-test",
                "primedb-ingest-daemon",
                "mla1517-producer",
            ]
        ),
        "contract": _contract_check(),
        "policy": _policy_check(),
        "requirements_audit": _run([sys.executable, "scripts/session_requirements_audit.py"]),
        "telemetry_abi": _run([sys.executable, "scripts/abi_check.py"]),
        "docker_shm_contract": _run([sys.executable, "scripts/docker_shm_smoke.py"]),
        "behavioral_gap_audit": _run([sys.executable, "scripts/behavioral_gap_audit.py"]),
        "no_float_in_math_core": _run([sys.executable, "scripts/no_float_in_math_core.py"]),
        "toolchains": {
            name: bool(shutil.which(name))
            for name in ("g++", "rustc", "cargo", "iverilog", "verilator", "docker")
        },
    }
    if os.getenv("MLA1517_STRICT_HARDWARE_CI") == "1":
        checks["strict_hardware"] = _run([sys.executable, "scripts/strict_hardware_gate.py"])
    else:
        checks["strict_hardware"] = {
            "status": "NOT_RUN",
            "detail": "set MLA1517_STRICT_HARDWARE_CI=1 to require a real exact OpenCL device",
        }
    checks["status"] = _release_status(checks)
    checks["unavailable_toolchains_are_evidence"] = True
    output = RESULTS / "release_gate.json"
    output.write_text(json.dumps(checks, indent=2, sort_keys=True) + "\n")
    print(json.dumps(checks, indent=2, sort_keys=True))
    return 0 if checks["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
