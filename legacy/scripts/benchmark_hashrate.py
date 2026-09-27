#!/usr/bin/env python3
"""Offline, consensus-checked SHA-256d throughput benchmark.

No sockets, pool credentials, or share submissions are used. A zero target
forces the backend to exhaust every nonce in each batch.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mining.bitcoin_hasher import BitcoinHasher  # noqa: E402
from mining.hash_pipeline import double_sha256  # noqa: E402

GENESIS_HEADER_PREFIX = bytes.fromhex(
    "01000000" + "00" * 32
    + "3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a"
    + "29ab5f49" + "ffff001d"
)
GENESIS_HASH = "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=("auto", "opencl", "gpu", "cpu"), default="auto")
    parser.add_argument("--batch", type=int, default=1_000_000)
    parser.add_argument("--iterations", type=int, default=5)
    args = parser.parse_args()
    if not 1 <= args.batch <= 1 << 20 or args.iterations < 1:
        parser.error("batch must be 1..1048576 and iterations must be positive")
    genesis = GENESIS_HEADER_PREFIX + (2083236893).to_bytes(4, "little")
    vector_ok = double_sha256(genesis)[::-1].hex() == GENESIS_HASH
    if not vector_ok:
        raise SystemExit("consensus vector failed; refusing to benchmark")
    hasher = BitcoinHasher(backend=args.backend)
    target = bytes(32)
    started = time.perf_counter()
    hashes = 0
    elapsed_work = 0.0
    errors: list[str] = []
    for iteration in range(args.iterations):
        t0 = time.perf_counter()
        winner, digest, count = hasher.grind_target_range(
            GENESIS_HEADER_PREFIX + b"\0\0\0\0", target, iteration * args.batch, args.batch
        )
        elapsed_work += time.perf_counter() - t0
        hashes += count
        if winner is not None or digest is not None or count != args.batch:
            errors.append("backend returned an early or partial result for zero target")
    total_elapsed = time.perf_counter() - started
    report = {
        "backend": hasher.backend,
        "device": hasher.device,
        "kernel_compiled": hasher.backend != "cpu",
        "kernel_executed": hasher.backend != "cpu",
        "consensus_vector_passed": vector_ok,
        "duration_seconds": total_elapsed,
        "hashes": hashes,
        "hashrate_hs": hashes / elapsed_work if elapsed_work > 0 else 0.0,
        "network_calls": 0,
        "errors": errors,
        "truth_class": "measured_hardware" if hasher.backend.startswith("opencl") else "measured_cpu_reference",
        "telemetry": hasher.telemetry(),
    }
    print(json.dumps(report, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
