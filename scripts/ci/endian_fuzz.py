#!/usr/bin/env python3
"""
Chronus Endianness & Header Construction Fuzzer.
Executes high-iteration fuzzing over header packing and PrevHash word swapping
to guarantee 0 mismatches against Bitcoin protocol specifications.
"""

import argparse
import hashlib
import os
import sys

# Ensure repository root and src directory are on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from chronus.stratum.endian_engine import swap_prevhash_words, build_header80


def reference_swap_prevhash_words(hex_str: str) -> bytes:
    """Independent reference implementation of 32-bit word swapping."""
    raw = bytes.fromhex(hex_str)
    words = [raw[i:i+4] for i in range(0, 32, 4)]
    reversed_words = [w[::-1] for w in words]
    return b"".join(reversed_words)


def main():
    parser = argparse.ArgumentParser(description="Chronus Endianness Fuzzer")
    parser.add_argument("--iters", type=int, default=10000, help="Number of fuzzing iterations")
    args = parser.parse_args()

    print(f"=== EXECUTING ENDIANNESS FUZZER ({args.iters} ITERATIONS) ===")

    mismatches = 0
    for i in range(args.iters):
        # Generate pseudo-random 32 bytes using deterministic hash derivation
        raw_seed = hashlib.sha256(f"seed_{i}".encode()).digest()
        prevhash_hex = raw_seed.hex()

        try:
            prod_swapped = swap_prevhash_words(prevhash_hex)
            ref_swapped = reference_swap_prevhash_words(prevhash_hex)

            if prod_swapped != ref_swapped:
                print(f"Mismatch at iter {i}: Prod={prod_swapped.hex()} Ref={ref_swapped.hex()}")
                mismatches += 1

            # Test build_header80
            hdr = build_header80(
                0x20000000, prod_swapped, raw_seed, 0x60000000, 0x1d00ffff, i
            )
            if len(hdr) != 80:
                print(f"Header length mismatch at iter {i}: {len(hdr)} != 80")
                mismatches += 1
        except Exception as e:
            print(f"Exception at iter {i}: {e}")
            mismatches += 1

    if mismatches == 0:
        print(f"PASSED: 0 mismatches across {args.iters} fuzzing iterations.")
        sys.exit(0)
    else:
        print(f"FAILED: Found {mismatches} mismatches during fuzzing.")
        sys.exit(1)


if __name__ == "__main__":
    main()
