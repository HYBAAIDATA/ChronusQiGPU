"""Reproducible bounded SHA-256d and nonce-representation benchmark."""

import argparse
import json
import os
import platform
import time

from chronus.execution.mining import _max_candidates, search_nonce_range
from chronus.execution.structural import zeckendorf_decode, zeckendorf_encode


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=int, default=32768)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    max_candidates = _max_candidates()  # runtime bound (CHRONUS_* config), not a constant
    if not 1 <= args.candidates <= max_candidates:
        parser.error(f"candidates must be between 1 and {max_candidates}")

    start = time.perf_counter()
    result = search_nonce_range(bytes(80), 0, args.candidates, 0, args.workers)
    hash_seconds = time.perf_counter() - start

    start = time.perf_counter()
    binary = 0
    for _ in range(args.candidates):
        binary += 1
    binary_seconds = time.perf_counter() - start

    start = time.perf_counter()
    encoded = ()
    for _ in range(args.candidates):
        encoded = zeckendorf_encode(zeckendorf_decode(encoded) + 1)
    structural_seconds = time.perf_counter() - start
    assert binary == zeckendorf_decode(encoded) == args.candidates

    print(json.dumps({
        "execution_mode": "SOFTWARE_EXECUTION",
        "platform": platform.platform(),
        "python": platform.python_version(),
        "logical_cpus": os.cpu_count(),
        "requested_workers": args.workers,
        "actual_workers": result["workers"],
        "lanes": len(result["lanes"]),
        "candidates": result["tested"],
        "sha256d_seconds": hash_seconds,
        "sha256d_hashes_per_second": result["tested"] / hash_seconds,
        "binary_increment_seconds": binary_seconds,
        "zeckendorf_decode_increment_reencode_seconds": structural_seconds,
    }, indent=2))


if __name__ == "__main__":
    main()
