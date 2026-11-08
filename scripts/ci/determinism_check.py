#!/usr/bin/env python3
"""
Chronus Determinism & Bit-Identical Output Verification.
Executes 3 deterministic runs across f257, Zeckendorf, QSqrt5, and header construction.
Asserts bit-identical SHA-256 hashes of canonical outputs.
"""

import hashlib
import json
import os
import sys

# Ensure repository root and src directory are on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from chronus.math.f257_search import f257_phases
from chronus.hw.zeckendorf import fold_to_zeckendorf, unfold
from chronus.math.binet_lucas import lucas_binet, unfold as unfold_q
from chronus.stratum.endian_engine import swap_prevhash_words, compute_merkle_root_stratum, build_header80
from chronus.stratum.bip310 import apply_version_rolling


def run_pipeline_deterministic(seed: int = 42) -> str:
    """Executes deterministic calculations and returns SHA-256 digest of JSON output."""
    output_data = {}

    # 1. F257 Phases
    u = ((seed * 17) % 256) + 1
    phases = f257_phases(u, 100, 1)
    output_data["f257_phases"] = phases

    # 2. Zeckendorf
    val = seed * 100000 + 12345
    rep = fold_to_zeckendorf(val)
    unfolded_val = unfold(rep)
    output_data["zeckendorf"] = {"input": val, "rep": rep, "unfolded": unfolded_val}

    # 3. Binet / Lucas
    lucas_val = unfold_q(lucas_binet(30))
    output_data["lucas_binet_30"] = lucas_val

    # 4. Stratum Header Construction
    prev_hex = "0000000000000000000000000000000000000000000000000000000000000001"
    swapped_prev = swap_prevhash_words(prev_hex)
    merkle_raw = compute_merkle_root_stratum("01000000", "a45b7889", "00000001", "00000000", [])
    final_ver, ver_hex = apply_version_rolling("20000000", "1fffe000", 0x1000)
    hdr80 = build_header80(final_ver, swapped_prev, merkle_raw, 0x60000000, 0x1d00ffff, 0x12345678)

    output_data["header80_sha256"] = hashlib.sha256(hdr80).hexdigest()

    canonical_json = json.dumps(output_data, sort_keys=True)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def main():
    print("=== EXECUTING DETERMINISM CHECK (3 SEEDED RUNS) ===")
    h1 = run_pipeline_deterministic(seed=42)
    h2 = run_pipeline_deterministic(seed=42)
    h3 = run_pipeline_deterministic(seed=42)

    print(f"Run 1 SHA-256: {h1}")
    print(f"Run 2 SHA-256: {h2}")
    print(f"Run 3 SHA-256: {h3}")

    if h1 == h2 == h3:
        print("PASSED: 3/3 runs yielded 100% bit-identical outputs.")
        sys.exit(0)
    else:
        print("FAILED: Output divergence detected across runs!")
        sys.exit(1)


if __name__ == "__main__":
    main()
