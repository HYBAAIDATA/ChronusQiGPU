#!/usr/bin/env python3
"""Assess real-input PULVINI folding evidence without auto-promoting RS-WORK.

The held 11.5x verified-work claim is a matched useful-work/time claim, not a
byte ratio. PULVINI active working-set ratios cannot by themselves verify it.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import sys

SCHEMA = "chronus.claims.fold-characterization/1"
INPUT_SCHEMA = "chronus.real-workload/1"


def characterize(document: dict, expected_sha: str | None = None) -> dict:
    """Validate evidence and retain a held claims disposition."""
    if not isinstance(document, dict) or document.get("schema") != INPUT_SCHEMA:
        raise ValueError("real-workload evidence schema required")
    if document.get("result") != "PASS" or document.get("data_generated_by_benchmark") is not False:
        raise ValueError("successful real-input evidence required")
    sha = document.get("git_commit")
    if expected_sha is not None:
        if not re.fullmatch("[0-9a-f]{40}", expected_sha):
            raise ValueError("expected commit must be exact lowercase SHA")
        if sha != expected_sha:
            raise ValueError("benchmark evidence commit mismatch")
    entries = document.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("at least one executed input required")
    records = []
    for entry in entries:
        if not isinstance(entry, dict) or not re.fullmatch(
            "[0-9a-f]{64}", str(entry.get("source_sha256", ""))
        ):
            raise ValueError("missing actual input SHA-256")
        workload = entry.get("workload")
        if not isinstance(workload, dict):
            raise ValueError("missing executed workload")
        if workload.get("operation") != "tensor_reference_add_and_pulvini":
            continue
        if workload.get("addition_exact_match") is not True:
            raise ValueError("incorrect useful work")
        fold = workload.get("pulvini")
        if not isinstance(fold, dict) or fold.get("numerical_reconstruction_verified") is not True:
            raise ValueError("PULVINI verification absent")
        original = fold.get("input_promoted_bytes")
        active = fold.get("working_set_bytes")
        kernels = fold.get("kernel_bytes")
        retained = fold.get("complete_retained_bytes")
        if any(type(x) is not int or x < 0 for x in (original, active, kernels, retained)):
            raise ValueError("invalid complete byte accounting")
        if not original or not active or retained != active + kernels:
            raise ValueError("missing or inconsistent retained kernels")
        if fold.get("net_storage_compression_claim") is not False:
            raise ValueError("unqualified net-compression claim")
        error = fold.get("relative_reconstruction_error")
        if type(error) not in (float, int) or not math.isfinite(error) or error > 1e-12 or error < 0:
            raise ValueError("invalid reconstruction tolerance")
        records.append({
            "source_sha256": entry["source_sha256"],
            "source_class": entry.get("source_class", "UNAVAILABLE"),
            "active_working_set_ratio": original / active,
            "complete_retained_ratio": original / retained,
            "original_bytes": original,
            "active_bytes": active,
            "kernel_bytes": kernels,
            "complete_retained_bytes": retained,
            "relative_reconstruction_error": error,
            "reconstruction_class": "NUMERICAL_WITH_TOLERANCE_NOT_BITWISE_EXACT",
        })
    if not records:
        raise ValueError("no PULVINI tensor workloads in supplied evidence")
    benchmark_digest = sha256(json.dumps(
        document, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()).hexdigest()
    return {
        "schema": SCHEMA,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "benchmark_sha256": benchmark_digest,
        "source_commit": sha,
        "claim": "RS-WORK",
        "claim_text": "11.5x verified work",
        "claim_status": "HELD",
        "why_held": (
            "Active working-set and total retained bytes are representation metrics; "
            "the source does not furnish a matched 11.5x verified-useful-work "
            "timing experiment with independent baseline and all overhead."
        ),
        "11_5x_verified_work_proven": False,
        "source_input_count": document["input_count"],
        "tensor_records": records,
        "production_qualified": False,
        "claims_register_mutated": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real-workload-evidence", required=True, type=Path)
    parser.add_argument("--expected-sha")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        target = args.output.resolve()
        source = args.real_workload_evidence.resolve(strict=True)
        if target == source or target.exists():
            raise ValueError("output must be a new file separate from source")
        evidence = characterize(json.loads(source.read_text(encoding="utf-8")),
                                 expected_sha=args.expected_sha)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("x", encoding="utf-8") as stream:
            json.dump(evidence, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
        print(json.dumps({"claim": "RS-WORK", "status": "HELD", "output": str(target)}))
        return 0  # A correctly withheld claim is NOT a failed evidence-processing job.
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"status": "INVALID_EVIDENCE", "error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
