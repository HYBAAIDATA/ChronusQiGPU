#!/usr/bin/env python3
"""Generate local software-verification evidence.

The historical filename PRODUCTION_QUALIFIED.json is retained for compatibility,
but this script cannot award production qualification. Production admission is
performed by the attested gate evaluator for the exact release commit.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def run_cmd(args: list[str]) -> bool:
    result = subprocess.run(args, capture_output=True, text=True, cwd=REPO_ROOT, check=False)
    if result.returncode != 0:
        print(f"[CMD FAIL] {' '.join(args)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    return result.returncode == 0


def main() -> int:
    py = sys.executable
    checks = {
        "pytest": run_cmd([py, "scripts/ci/run_tests.py"]),
        "purity": run_cmd([py, "scripts/ci/purity_gate.py"]),
        "determinism": run_cmd([py, "scripts/ci/determinism_check.py"]),
        "endian_fuzz": run_cmd([py, "scripts/ci/endian_fuzz.py", "--iters", "100000"]),
        "replay": run_cmd([py, "-m", "pytest", "tests/test_stratum_replay.py", "-q"]),
        "meta_test_mutation": run_cmd([py, "scripts/ci/test_the_tests.py"]),
        "sovereign_difc_attestation": run_cmd([py, "scripts/ci/sovereign_attestation.py"]),
    }
    software_ok = all(checks.values())

    verilator = shutil.which("verilator")
    sv_lint = (
        "PASS"
        if verilator and run_cmd([verilator, "--lint-only", "hw/zeckendorf_alu_32lane.sv"])
        else ("FAIL" if verilator else "NOT_RUN")
    )

    try:
        git_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip()
    except Exception:
        git_sha = None

    lock_hash = None
    for name in ("uv.lock", "poetry.lock", "Pipfile.lock", "requirements.lock", "pyproject.toml"):
        path = os.path.join(REPO_ROOT, name)
        if os.path.exists(path):
            with open(path, "rb") as handle:
                lock_hash = hashlib.sha256(handle.read()).hexdigest()
            break

    manifest_data = {
        "schema": "chronus-local-software-evidence/v2",
        "status": "SOFTWARE_VERIFIED" if software_ok else "SOFTWARE_CHECK_FAILED",
        "production_qualified": False,
        "production_admission": "REQUIRES_ATTESTED_PRODUCT_GATES",
        "legacy_filename_notice": (
            "PRODUCTION_QUALIFIED.json is retained for compatibility; status is evidence-scoped."
        ),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "gates": {name: ("PASS" if passed else "FAIL") for name, passed in checks.items()},
        "supplemental": {"sv_lint": sv_lint, "mypy_strict": "NOT_RUN"},
        "measurements": {
            "gatekeeper_p99_us": None,
            "submit_rate_achieved_sec": None,
            "shares_local_dropped": None,
            "blocks_found": None,
            "stale_share_rate": None,
        },
        "provenance": {
            "git_sha": git_sha,
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "lock_hash": lock_hash,
        },
        "attestation": {
            "artifact_attestation_verified": False,
            "product_gate_evidence_verified": False,
            "external_evaluator_required": True,
        },
        "signature": None,
    }

    target = os.path.join(REPO_ROOT, "PRODUCTION_QUALIFIED.json")
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(manifest_data, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps(manifest_data, sort_keys=True))
    return 0 if software_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
