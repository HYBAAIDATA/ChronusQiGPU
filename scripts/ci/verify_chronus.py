#!/usr/bin/env python3
"""
Chronus Automated Qualification & Artifact Verifier.
Inspects legacy H1-H6 artifacts; this script does not issue release qualification.
"""

import os
import sys
import subprocess
import time
from collections.abc import Sequence

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

def run(argv: Sequence[str]) -> str:
    """Inspect a fixed executable and literal arguments without a shell."""
    if isinstance(argv, (str, bytes)) or not argv:
        raise TypeError("run requires a nonempty argument sequence")
    try:
        res = subprocess.run(
            list(argv), shell=False, capture_output=True, text=True, cwd=REPO_ROOT
        )
    except OSError as exc:
        return f"ERROR: command unavailable: {exc}"
    return res.stdout.strip() if res.returncode == 0 else (res.stdout + "\n" + res.stderr).strip()

def main():
    print("========================================================================")
    print("       CHRONUS LOCAL EVIDENCE INSPECTION (H1-H6; NOT RELEASE PROOF)      ")
    print("========================================================================")

    # H1: PRODUCTION_QUALIFIED.json
    print("\n[H1] Inspecting PRODUCTION_QUALIFIED.json:")
    h1_path = os.path.join(REPO_ROOT, "manifests", "historical", "PRODUCTION_QUALIFIED.json")
    if os.path.exists(h1_path):
        with open(h1_path, "r", encoding="utf-8") as f:
            print(f.read())
    else:
        print("ERROR: PRODUCTION_QUALIFIED.json missing!")

    # H2: Qualification Test Suite
    print("\n[H2] Running Qualification Tests:")
    print(run([sys.executable, "scripts/ci/run_tests.py"]))

    # H3: Hardware ALU Contract Inspection
    print("\n[H3] SystemVerilog Zeckendorf ALU Contract Inspection:")
    sv_path = os.path.join(REPO_ROOT, "hw/zeckendorf_alu_32lane.sv")
    if os.path.exists(sv_path):
        with open(sv_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if "module" in line or "input" in line or "output" in line or "OP_MUL" in line or "rst_sync" in line]
            print("\n".join(lines[:12]))

    # H4: Gatekeeper Benchmark
    print("\n[H4] Gatekeeper Latency Benchmark:")
    print(run([sys.executable, "scripts/benchmarks/benchmark_gatekeeper.py"]))

    # H5: f257_search.py Head 80 lines
    print("\n[H5] Algebraic F_257 Closed-Form Engine Head 80 lines:")
    f257_path = os.path.join(REPO_ROOT, "src/chronus/math/f257_search.py")
    if os.path.exists(f257_path):
        with open(f257_path, "r", encoding="utf-8") as f:
            content = f.readlines()[:80]
            print("".join(content))

    # H6: Critical Grep Patterns
    print("\n[H6] Critical Grep Audit:")
    pats = ["stale_share_rate", "test_stratum_replay", "odd_count", "regtest_block0"]
    for pat in pats:
        print(f"--- Pattern: {pat} ---")
        print(run(["git", "grep", "-n", "--", pat])[:300])

    print("\n========================================================================")
    print("INSPECTION COMPLETE; PRODUCTION QUALIFICATION NOT ESTABLISHED.")
    print("========================================================================")

if __name__ == "__main__":
    main()
