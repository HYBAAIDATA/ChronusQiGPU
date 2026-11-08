#!/usr/bin/env python3
"""
Chronus "Test the Tests" Mutation Verification Harness.
Validates the efficacy and integrity of the test suite by injecting intentional
algebraic and behavioral faults into core mathematical and networking invariants.

Every injected mutant MUST be detected and killed by the test suite (100% kill rate).
If any mutant survives, the harness fails with exit code 1, flagging a weak or tautological test.
"""

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import List

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
SRC_DIR = os.path.join(REPO_ROOT, "src")


@dataclass
class Mutation:
    name: str
    description: str
    target_rel_path: str
    original_code: str
    mutated_code: str
    test_command: str


MUTATIONS: List[Mutation] = [
    Mutation(
        name="M1: Gatekeeper Target Acceptance Inversion",
        description="Invert hash target condition from '<= share_target' to '> share_target'",
        target_rel_path="src/chronus/stratum/gatekeeper.py",
        original_code="is_share_valid = (hash_int <= share_target_int)",
        mutated_code="is_share_valid = (hash_int > share_target_int)",
        test_command=f'"{sys.executable}" -m unittest tests/test_gatekeeper.py',
    ),
    Mutation(
        name="M2: Endianness PrevHash Word Swap Bypass",
        description="Bypass the 8x 32-bit word reversal in swap_prevhash_words",
        target_rel_path="src/chronus/stratum/endian_engine.py",
        original_code='return struct.pack("<8I", *struct.unpack(">8I", raw))',
        mutated_code="return raw",
        test_command=f'"{sys.executable}" -m unittest tests/test_endian_engine.py',
    ),
    Mutation(
        name="M3: F_257 Galois Mean Field Shift Offset",
        description="Corrupt alpha shift from (u_inv + 1) to (u_inv + 2) mod 257",
        target_rel_path="src/chronus/math/f257_search.py",
        original_code="alpha = (u_inv + 1) % P_PRIME",
        mutated_code="alpha = (u_inv + 2) % P_PRIME",
        test_command=f'"{sys.executable}" -m unittest tests/test_f257_search.py',
    ),
    Mutation(
        name="M4: Binet/Lucas Q(sqrt(5)) Conjugate Root Flip",
        description="Flip PSI conjugate root from (1 - sqrt(5))/2 to (1 + sqrt(5))/2",
        target_rel_path="src/chronus/math/binet_lucas.py",
        original_code="PSI = QSqrt5(Fraction(1, 2), Fraction(-1, 2))",
        mutated_code="PSI = QSqrt5(Fraction(1, 2), Fraction(1, 2))",
        test_command=f'"{sys.executable}" -m unittest tests/test_binet_lucas.py',
    ),
    Mutation(
        name="M5: Zeckendorf Non-Adjacency Bit Generation",
        description="Break Fibonacci table lookup step in fold_to_zeckendorf",
        target_rel_path="src/chronus/hw/zeckendorf.py",
        original_code="if FIBONACCI_TABLE[idx] <= temp:",
        mutated_code="if FIBONACCI_TABLE[idx] < temp:",
        test_command=f'"{sys.executable}" -m unittest tests/test_zeckendorf.py',
    ),
    Mutation(
        name="M6: Token Bucket Refill Freeze",
        description="Prevent token bucket from ever accumulating new tokens",
        target_rel_path="src/chronus/stratum/rate_limiter.py",
        original_code="if elapsed_ns >= self.ns_per_token:",
        mutated_code="if elapsed_ns < 0:",
        test_command=f'"{sys.executable}" -m unittest tests/test_rate_limiter.py',
    ),
    Mutation(
        name="M7: BIP310 Version Mask Application Corrupter",
        description="Corrupt version-rolling bitwise AND to bitwise OR",
        target_rel_path="src/chronus/stratum/bip310.py",
        original_code="final_version = (base_ver & ~mask) | masked_bits",
        mutated_code="final_version = (base_ver | mask) | masked_bits",
        test_command=f'"{sys.executable}" -m unittest tests/test_bip310.py',
    ),
]


def execute_mutation(mut: Mutation) -> bool:
    """
    Applies mutation, executes target test command, asserts tests fail, and restores original code.
    Returns True if mutant was KILLED (tests failed as expected).
    Returns False if mutant SURVIVED (tests passed despite mutation).
    """
    full_path = os.path.join(REPO_ROOT, mut.target_rel_path)
    if not os.path.exists(full_path):
        print(f"[ERROR] Target file does not exist: {full_path}")
        return False

    with open(full_path, "r", encoding="utf-8") as f:
        content = f.read()

    if mut.original_code not in content:
        print(f"[ERROR] Target string for '{mut.name}' not found in {mut.target_rel_path}")
        return False

    mutated_content = content.replace(mut.original_code, mut.mutated_code, 1)

    try:
        # Write mutation
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(mutated_content)

        # Run test
        env = dict(os.environ)
        env["PYTHONPATH"] = f"{SRC_DIR}{os.pathsep}{REPO_ROOT}"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        res = subprocess.run(
            mut.test_command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            env=env,
        )

        # A successful mutation test MUST result in returncode != 0 (the test caught the bug!)
        if res.returncode != 0:
            print(f"  [KILLED] {mut.name}")
            return True
        else:
            print(f"  [SURVIVED] {mut.name}")
            print(f"    Mutant survived! Test suite did not catch fault: {mut.description}")
            return False
    finally:
        # Always restore original code cleanly
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)


def main():
    print("========================================================================")
    print("         CHRONUS META-TEST HARNESS (TESTING THE TESTS)                  ")
    print("========================================================================")
    print(f"Total Invariant Mutants: {len(MUTATIONS)}")
    print("Executing mutation testing against core mathematical and wire engines...")
    print("------------------------------------------------------------------------")

    killed = 0
    survived = 0
    t0 = time.time()

    for mut in MUTATIONS:
        if execute_mutation(mut):
            killed += 1
        else:
            survived += 1

    elapsed = time.time() - t0
    total = len(MUTATIONS)
    kill_rate = (killed / total) * 100.0 if total > 0 else 0.0

    print("------------------------------------------------------------------------")
    print(f"Mutants Killed: {killed}/{total} ({kill_rate:.1f}%)")
    print(f"Mutants Survived: {survived}/{total}")
    print(f"Verification Duration: {elapsed:.2f}s")
    print("========================================================================")

    if survived == 0:
        print("RESULT: 100% MUTATION KILL RATE — ALL BEHAVIORAL INVARIANTS VERIFIED!")
        sys.exit(0)
    else:
        print(f"RESULT: VERIFICATION FAILED — {survived} mutant(s) survived.")
        sys.exit(1)


if __name__ == "__main__":
    main()
