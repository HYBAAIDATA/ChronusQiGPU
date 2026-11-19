#!/usr/bin/env python3
"""
Chronus Production Qualification Manifest Generator (§5.3, F3.1-F3.18, H1).
Executes local verification gates and writes unsigned diagnostic results.
Release admission is owned by the separately verified release-evidence path.
"""

import hashlib
import json
import os
import shutil
import shlex
import subprocess
import sys
import time
from pathlib import Path
from collections.abc import Sequence

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)



def run_cmd(argv: Sequence[str]) -> bool:
    """Execute literal argv, never a command string interpreted by a shell."""
    if isinstance(argv, (str, bytes)) or not argv:
        raise TypeError("run_cmd requires a nonempty argument sequence")
    command = list(argv)
    try:
        res = subprocess.run(
            command, shell=False, capture_output=True, text=True, cwd=REPO_ROOT
        )
    except OSError as exc:
        print(f"[CMD FAIL] {shlex.join(command)}\nERROR: {exc}")
        return False
    if res.returncode != 0:
        print(
            f"[CMD FAIL] {shlex.join(command)}\n"
            f"STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
        )
    return res.returncode == 0


_REQUIRED_RELEASE_EVIDENCE = (
    "owner-approval.json",
    "device-certificate.json",
    "benchmark.json",
    "sbom.json",
    "provenance.json",
    "rollback-plan.json",
)


def collect_release_evidence() -> dict[str, object]:
    """Return the external evidence state without inferring qualification.

    Local tests and a clean build are necessary but not sufficient.  The
    device certificate, matched benchmark, signed provenance, rollback plan,
    and owner approval must be supplied as one immutable packet.  CI does not
    have that packet, so the generated artifact must remain NOT_QUALIFIED.
    """

    configured = os.getenv("CHRONUS_RELEASE_EVIDENCE_DIR", "").strip()
    if not configured:
        return {
            "status": "MISSING",
            "path": None,
            "required": list(_REQUIRED_RELEASE_EVIDENCE),
            "missing": list(_REQUIRED_RELEASE_EVIDENCE) + [
                "CHRONUS_RELEASE_APPROVED=true",
            ],
        }

    root = os.path.abspath(configured)
    missing = [
        name for name in _REQUIRED_RELEASE_EVIDENCE
        if not os.path.isfile(os.path.join(root, name))
    ]
    if os.getenv("CHRONUS_RELEASE_APPROVED", "").strip().lower() not in {
        "1", "true", "yes",
    }:
        missing.append("CHRONUS_RELEASE_APPROVED=true")
    return {
        "status": "PRESENT" if not missing else "MISSING",
        "path": root,
        "required": list(_REQUIRED_RELEASE_EVIDENCE),
        "missing": missing,
    }


def main():
    print("=== GENERATING PRODUCTION QUALIFICATION MANIFEST ===")
    py = sys.executable

    # Run Gate 1: Unit & Integration Tests (F1.1-F1.10)
    p_tests = run_cmd([py, "scripts/ci/run_tests.py"])
    print(f"Gate 1 (Unit/Integration Tests): {'PASS' if p_tests else 'FAIL'}")

    # Run Gate 2: PCI Purity Gate Scanner (A1.2, A2.1-A2.6)
    p_purity = run_cmd([py, "scripts/ci/purity_gate.py"])
    print(f"Gate 2 (PCI Purity Gate): {'PASS' if p_purity else 'FAIL'}")

    # Run Gate 3: Determinism Check (A1.3, A3)
    p_determinism = run_cmd([py, "scripts/ci/determinism_check.py"])
    print(f"Gate 3 (Determinism Check): {'PASS' if p_determinism else 'FAIL'}")

    # Run Gate 4: Endianness Fuzzer (A1.4)
    p_fuzz = run_cmd([py, "scripts/ci/endian_fuzz.py", "--iters", "100000"])
    print(f"Gate 4 (Endianness Fuzzer): {'PASS' if p_fuzz else 'FAIL'}")

    # Run Gate 5: Stratum Replay (A1.5)
    p_replay = run_cmd([py, "-m", "pytest", "tests/test_stratum_replay.py", "-q"])
    print(f"Gate 5 (Wire Replay): {'PASS' if p_replay else 'FAIL'}")

    # Run Gate 6: Meta-Test Invariant Mutation Harness (Test the Tests)
    p_meta = run_cmd([py, "scripts/ci/test_the_tests.py"])
    print(f"Gate 6 (Meta-Test Mutation Harness): {'PASS' if p_meta else 'FAIL'}")

    # Run Gate 7: DIFC Sovereign Capability Attestation
    p_sovereign = run_cmd([py, "scripts/ci/sovereign_attestation.py"])
    print(f"Gate 7 (Sovereign DIFC Attestation): {'PASS' if p_sovereign else 'FAIL'}")

    all_passed = p_tests and p_purity and p_determinism and p_fuzz and p_replay and p_meta and p_sovereign

    # SystemVerilog lint check (run verilator if present, otherwise set to None; never hardcode PASS)
    verilator_bin = shutil.which("verilator")
    if verilator_bin:
        rtl_files = sorted(Path(REPO_ROOT, "hardware", "rtl").glob("*.sv"))
        rtl_files += sorted(Path(REPO_ROOT, "hw").glob("*.sv"))
        sv_lint_status = (
            "PASS" if rtl_files and run_cmd(
                [verilator_bin, "--lint-only", *(str(file) for file in rtl_files)]
            ) else "FAIL"
        )
    else:
        sv_lint_status = None

    # Provenance data grounded in repository reality (never hardcode git_sha)
    try:
        git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    except Exception:
        git_sha = None

    external_evidence = collect_release_evidence()

    # Lockfile hash: hash actual lockfile if present; otherwise None (never hardcode empty hash)
    lock_hash = None
    lock_candidates = ["uv.lock", "poetry.lock", "Pipfile.lock", "requirements.lock", "pyproject.toml"]
    for lock_name in lock_candidates:
        lock_path = os.path.join(REPO_ROOT, lock_name)
        if os.path.exists(lock_path):
            with open(lock_path, "rb") as f:
                lock_hash = hashlib.sha256(f.read()).hexdigest()
            break

    # Read empirical gatekeeper measurement from benchmark results if present, otherwise None
    gatekeeper_p99_us = None
    bench_result_path = os.path.join(REPO_ROOT, "build", "benchmarks", "gatekeeper_latency.json")
    if os.path.exists(bench_result_path):
        try:
            with open(bench_result_path, "r", encoding="utf-8") as f:
                bdata = json.load(f)
                gatekeeper_p99_us = bdata.get("p99_us")
        except Exception:
            gatekeeper_p99_us = None

    # Read live runtime metrics if present; otherwise None (never hardcode blocks_found or stale_share_rate)
    blocks_found = None
    stale_share_rate = None
    metrics_path = os.path.join(REPO_ROOT, "build", "metrics", "stratum_metrics.json")
    if os.path.exists(metrics_path):
        try:
            with open(metrics_path, "r", encoding="utf-8") as f:
                mdata = json.load(f)
                blocks_found = mdata.get("blocks_found")
                stale_share_rate = mdata.get("stale_share_rate")
        except Exception:
            pass

    manifest_data = {
        "status": "NOT_QUALIFIED",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "local_ci_checks": "PASS" if all_passed else "FAIL",
        "local_gate_status": "PASS" if all_passed else "FAIL",
        "external_release_evidence": external_evidence,
        "gates": {
            "pytest": "PASS" if p_tests else "FAIL",
            "purity": "PASS" if p_purity else "FAIL",
            "determinism": "PASS" if p_determinism else "FAIL",
            "endian_fuzz": "PASS" if p_fuzz else "FAIL",
            "replay": "PASS" if p_replay else "FAIL",
            "meta_test_mutation": "PASS" if p_meta else "FAIL",
            "sovereign_difc_attestation": "PASS" if p_sovereign else "FAIL",
            "mypy_strict": None,
            "sv_lint": sv_lint_status
        },
        "measurements": {
            "gatekeeper_p99_us": gatekeeper_p99_us,
            "submit_rate_achieved_sec": None,
            "shares_local_dropped": None,
            "blocks_found": blocks_found,
            "stale_share_rate": stale_share_rate
        },
        "provenance": {
            "git_sha": git_sha,
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "lock_hash": lock_hash
        },
        "verification_procedure": {"algorithm": None,
                                   "reason": "Local diagnostics are not a signed release attestation."},
        "signature": None,
    }

    manifest_path = os.path.join(REPO_ROOT, "reference-evidence", "PRODUCTION_QUALIFIED.json")
    os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    print(f"Manifest written to {manifest_path}")

    if all_passed:
        print(
            "LOCAL GATES PASSED; RELEASE REMAINS NOT QUALIFIED: "
            "external evidence packet or explicit owner approval is missing."
        )
        sys.exit(0)
    print("SYSTEM QUALIFICATION FAILED.")
    sys.exit(1)


if __name__ == "__main__":
    main()
