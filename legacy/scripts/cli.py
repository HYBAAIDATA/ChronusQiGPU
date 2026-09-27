"""CLI for running and independently verifying the Lucas system artifact."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

try:
    from scripts.benchmark_harness import BenchmarkHarness
    from scripts.verify import verify_artifact
except ImportError:
    from benchmark_harness import BenchmarkHarness
    from verify import verify_artifact


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lucas-bench")
    parser.add_argument("--workload-id", default="fingerprint-001")
    parser.add_argument("--seed-hex")
    parser.add_argument("--nonce-bits", type=int, default=12)
    parser.add_argument("--target-bytes", type=int, default=1)
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--scale-matrix-json")
    parser.add_argument("--output")
    parser.add_argument("--verify-only")
    args = parser.parse_args(argv)

    if args.verify_only:
        artifact = json.loads(Path(args.verify_only).read_text(encoding="utf-8"))
        ok = verify_artifact(artifact)
        print(f"artifact_verified = {ok}")
        return 0 if ok else 1

    seed = bytes.fromhex(args.seed_hex) if args.seed_hex else hashlib.sha256(
        b"default-master-seed|" + args.workload_id.encode()
    ).digest()
    matrix = None
    if args.scale_matrix_json:
        config = json.loads(Path(args.scale_matrix_json).read_text(encoding="utf-8"))
        if "domains" in config:
            required = ("search", "memory", "tensor", "virtual_quantum", "hardware",
                        "intelligence", "coherence", "verification", "schedule")
            matrix = {domain: int(config["domains"][domain]["recurrence_index"]) for domain in required}
        else:
            matrix = config
    artifact = BenchmarkHarness(
        seed, nonce_bits=args.nonce_bits, target_prefix_bytes=args.target_bytes,
        scale_matrix=matrix, trials=args.trials,
    ).run(args.workload_id)
    text = json.dumps(artifact, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"wrote {args.output}")
    else:
        print(text)
    return 0 if verify_artifact(artifact) else 1


if __name__ == "__main__":
    raise SystemExit(main())
