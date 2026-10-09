#!/usr/bin/env python3
"""Fail-closed Apple M5 handover preflight; no network mining or mutations.

Use: .venv/bin/python scripts/m5_transfer_preflight.py --execute
This checks the *running interpreter*, source provenance, isolated package
imports and real designated integration tests. It does not start workers or
claim physical GPU execution, CI results or external pool acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MODULES = (
    "euclid", "toe", "kellogg", "turing_universal_quantum_computer",
    "chronus", "hyba_db", "salamander", "al_haras",
)
TEST_SUITES = {
    "mining_custody_restart": (
        "tests/test_m3_storage_voyage.py",
        "tests/test_m3_runtime_closure.py",
    ),
    "euclid_cognition": (
        "tests/test_euclid_v17_production_integration.py",
        "tests/test_euclid_cognition_production.py",
        "chronus/mla1517_platform/python/test_euclid_cognition_entrypoint.py",
    ),
    "mining_intelligence": (
        "tests/test_resident_hendrix.py",
        "chronus/mla1517_platform/python/test_euclid_mining_support.py",
    ),
}
# A historically named test that has been renamed must be resolved, never skipped.


def run(argv, cwd=ROOT, timeout=600):
    try:
        cp = subprocess.run(
            list(map(str, argv)), cwd=cwd, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=timeout, check=False,
            env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"},
        )
        return {"passed": cp.returncode == 0, "exit_code": cp.returncode,
                "output_tail": cp.stdout[-3500:]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"passed": False, "error": type(exc).__name__}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Run integration suites")
    parser.add_argument("--output", type=Path, help="Write non-secret JSON verdict")
    parser.add_argument("--allow-non-m5", action="store_true",
                        help="For CI only; never certifies Apple M5 platform")
    args = parser.parse_args()
    checks = {}
    checks["platform"] = {
        "system": platform.system(), "machine": platform.machine(),
        "python": sys.version.split()[0], "interpreter": sys.executable,
        "passed": platform.system() == "Darwin" and platform.machine() == "arm64",
    }
    checks["venv"] = {"passed": sys.prefix != sys.base_prefix}
    checks["source_revision"] = run(["git", "rev-parse", "HEAD"])
    checks["clean_checkout"] = run(["git", "status", "--porcelain"])
    if checks["clean_checkout"]["passed"]:
        checks["clean_checkout"]["passed"] = (
            checks["clean_checkout"].get("output_tail", "").strip() == ""
        )
    checks["dependency_consistency"] = run([sys.executable, "-m", "pip", "check"])
    # -I and a disposable working directory detect silent source tree shadowing.
    code = (
        "import importlib, json; "
        "names=" + repr(MODULES) + "; "
        "modules={n:importlib.import_module(n).__file__ for n in names}; "
        "print(json.dumps(modules,sort_keys=True))"
    )
    with tempfile.TemporaryDirectory(prefix="m5-isolated-import-") as tmp:
        checks["isolated_installed_imports"] = run(
            [sys.executable, "-I", "-c", code], cwd=tmp
        )
    checks["service_process_conflict"] = {
        "passed": False,
        "reason": "Operator must inspect processes and canonical lock before launch; no PID is killed automatically.",
    }
    checks["credentials_and_authorisation"] = {
        "passed": False, "reason": "Must be resolved through AL HARAS; no secrets are printed."
    }
    checks["external_pool"] = {"passed": False, "reason": "NOT_RUN: deliberate shadow-mode transfer"}
    checks["physical_gpu"] = {"passed": False, "reason": "NOT_RUN: device-bound evidence required"}
    checks["frontend"] = {"passed": False, "reason": "NOT_RUN: Node build and served UI required"}
    checks["full_suite_and_wheels"] = {
        "passed": False, "reason": "NOT_RUN: clean wheel/sdist and full matrix evidence required"
    }
    if args.execute:
        for name, suite in TEST_SUITES.items():
            missing = [item for item in suite if not (ROOT / item).is_file()]
            checks[name] = (
                {"passed": False, "reason": "Missing declared test paths: " + ", ".join(missing)}
                if missing else run([sys.executable, "-m", "pytest", "-q", *suite], timeout=1200)
            )
        checks["euclid_v17_gate"] = run(
            [sys.executable, "scripts/euclid_v17_integration_gate.py"], timeout=1800
        )
        checks["storage_registry"] = run(
            [sys.executable, "scripts/check_storage_registry.py"]
        )
    else:
        checks["integration_execution"] = {
            "passed": False, "reason": "NOT_RUN: invoke --execute"
        }
    mandatory = [
        "venv", "source_revision", "clean_checkout", "dependency_consistency",
        "isolated_installed_imports",
    ]
    if not args.allow_non_m5:
        mandatory.append("platform")
    mandatory += (
        ["mining_custody_restart", "euclid_cognition", "mining_intelligence",
         "euclid_v17_gate", "storage_registry"] if args.execute
        else ["integration_execution"]
    )
    result = {
        "schema": "hyba.m5-migration-preflight/1",
        "passed": all(checks[key]["passed"] for key in mandatory),
        "platform_verified": checks["platform"]["passed"],
        "scope": "LOCAL_SOFTWARE_PREFLIGHT_ONLY",
        "mandatory": mandatory,
        "checks": checks,
        "source_manifest_sha256": hashlib.sha256(
            json.dumps(TEST_SUITES, sort_keys=True).encode()
        ).hexdigest(),
        "claim_boundaries": {
            "intelligence_fully_operational": "UNVERIFIED_UNTIL_LIVE_PATH",
            "full_product_production": "NOT_CERTIFIED",
            "M5_physical_acceleration": "UNAVAILABLE",
            "external_pool_accepted_shares": "UNAVAILABLE",
        },
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
