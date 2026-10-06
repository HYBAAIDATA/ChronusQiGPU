#!/usr/bin/env python3
"""Reproduce the PureQuantumMathASIC proof bundle in a clean environment."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from turing_universal_quantum_computer import TenThousandQubitSystem


def canonical_digest(payload) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()


def reproduce(logical_scale: int = 10_000) -> dict:
    system = TenThousandQubitSystem(n_qubits=logical_scale)
    verification = system.verify_pure_quantum_asic()
    capacity = system.deterministic_10eh_system()
    payload = {
        "schema": "turing.pure_quantum_math.reproduction/v1",
        "logical_scale": logical_scale,
        "checks": dict(verification.checks),
        "artifacts": dict(verification.artifacts),
        "capacity_certificate": capacity.certificate.as_dict(),
        "capacity_proof_obligations": capacity.proof_obligations(),
        "verified": verification.verified,
        "independent_model_review_self_issued": False,
    }
    return {**payload, "reproduction_digest": canonical_digest(payload)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--logical-scale", type=int, default=10_000)
    parser.add_argument("--expected-digest")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = reproduce(args.logical_scale)
    if args.expected_digest and report["reproduction_digest"] != args.expected_digest:
        raise SystemExit(
            "reproduction digest mismatch: "
            f"expected {args.expected_digest}, got {report['reproduction_digest']}"
        )
    text = json.dumps(report, sort_keys=True, indent=2, default=str) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    else:
        print(text, end="")
    checks = report["checks"]
    capacity = report["capacity_certificate"]
    return 0 if all(checks.values()) and capacity["cold_start_floor_met"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
