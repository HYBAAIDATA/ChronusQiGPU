#!/usr/bin/env python3
"""Reproduce the PureQuantumMathASIC proof bundle in a clean environment.

The bundle spans products: the capacity model and the SHA-256d thermodynamic
boundary are Mining's; the Q(zeta_8) field registry and the surface-code
algebra are TURING's (exact algebra underneath from Kellogg).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mining.fault_tolerant_asic import PureQuantumMathASIC
from mining.thermodynamics_exact import thermodynamic_boundary_report
from turing_universal_quantum_computer.canonical_serialization import (
    canonical_sha256,
)
from turing_universal_quantum_computer.exact_field_registry import (
    verify_q_zeta_8_registry,
)
from turing_universal_quantum_computer.surface_code_exact import (
    verify_surface_code_algebra,
)


def reproduce(logical_scale: int = 10_000) -> dict:
    asic = PureQuantumMathASIC()
    verification = asic.verify_first_principles()
    capacity = asic.deterministic_hashrate_system()
    field = verify_q_zeta_8_registry()
    distance_31 = verify_surface_code_algebra(31)
    thermodynamics = thermodynamic_boundary_report()
    payload = {
        "schema": "turing.pure_quantum_math.reproduction/v1",
        "logical_scale": logical_scale,
        "checks": dict(verification.checks),
        "artifacts": dict(verification.artifacts),
        "capacity_certificate": capacity.certificate.as_dict(),
        "capacity_proof_obligations": capacity.proof_obligations(),
        "unified_field": {
            **field.__dict__,
            "exact_gate_domain": list(field.exact_gate_domain),
        },
        "surface_code_distance_31": distance_31.unsigned_dict(),
        "thermodynamic_boundary": thermodynamics.__dict__,
        "verified": verification.verified,
        "independent_model_review_self_issued": False,
    }
    return {**payload, "reproduction_digest": canonical_sha256(payload)}


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
