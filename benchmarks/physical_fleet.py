# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Collect candidate evidence from an existing fleet using an operator-supplied workload.

No provisioning, simulated devices, or production qualification. The pinned key must be independently collected from the coordinator.
Collect and verify the coordinator ledger separately after the run.
Worker labels are not physical host/GPU identity. Raw receipts are retained.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from chronus.fleet.auth import load_token
from chronus.fleet.executor import FleetExecutor
from chronus.fleet.receipts import verify_receipt
from chronus.fleet.workunit import WorkUnit


def nearest_rank(values: list[int], numerator: int, denominator: int) -> int:
    if not values or not 0 < numerator <= denominator:
        raise ValueError("non-empty samples and a valid percentile are required")
    return sorted(values)[(len(values) * numerator + denominator - 1) // denominator - 1]


def summary(values: list[int]) -> dict:
    if not values:
        return {"status": "UNAVAILABLE", "samples": 0}
    return {"samples": len(values), "units": "ns", "p50": nearest_rank(values, 50, 100),
            "p99": nearest_rank(values, 99, 100),
            "p999": nearest_rank(values, 999, 1000) if len(values) >= 1000 else None,
            "p999_status": "MEASURED" if len(values) >= 1000 else "INSUFFICIENT_SAMPLES"}


def git_revision() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def physical_route_records(receipt: dict, route: str) -> set[str]:
    """Worker-reported GPU records only; never count these as physical inventory."""
    workers = set()
    for device in receipt.get("devices", []):
        executed = device.get("routes_executed", {})
        if executed.get(route, 0) > 0 and "gpu" in device.get("silicon", []):
            workers.add(device["node_id"])
    return workers


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coordinator", required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--tls-ca", required=True)
    parser.add_argument("--public-key-file", type=Path, required=True,
                        help="independently pinned ML-DSA-65 public key (hex)")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--kernel", choices=("m15_fold", "m15_unfold"), required=True)
    parser.add_argument("--route", choices=("opencl", "metal", "cuda"), required=True)
    parser.add_argument("--expected-workers", type=int, required=True)
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--timeout", type=float, default=600)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if not args.coordinator.startswith("https://"):
        parser.error("physical fleet candidate evidence requires HTTPS")
    if args.expected_workers < 1 or args.iterations < 1 or not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("invalid worker count, iterations or timeout")
    payload = args.input.read_bytes()
    if not payload or len(payload) % 2:
        parser.error("input must contain non-empty, complete 16-bit elements")
    public_key = args.public_key_file.read_text().strip()
    if len(bytes.fromhex(public_key)) != 1952:
        parser.error("wrong ML-DSA-65 public key length")
    revision = git_revision()
    # Refuse a dirty candidate; write results outside the source checkout.
    if subprocess.check_output(["git", "status", "--porcelain"], text=True).strip():
        parser.error("benchmark requires a clean source checkout")
    args.out.mkdir(parents=True, exist_ok=False)
    unit = WorkUnit(args.kernel, payload, {}, args.route, 8000)
    report = {"schema": "chronus.fleet.physical-candidate/v1",
              "client_source_commit": revision,
              "remote_source_commit": None, "remote_source_commit_status": "UNAVAILABLE",
              "client_platform": platform.platform(),
              "started_at": datetime.now(timezone.utc).isoformat(),
              "input_sha256": hashlib.sha256(payload).hexdigest(), "input_bytes": len(payload),
              "work_unit_digest": unit.digest(), "requested_route": args.route,
              "expected_worker_reports": args.expected_workers, "iterations_requested": args.iterations,
              "samples": [], "qualification": "NOT_QUALIFIED",
              "physical_inventory_status": "UNAVAILABLE",
              "kernel_utilization": "UNAVAILABLE", "dispatch_overhead": "UNAVAILABLE",
              "fault_recovery": "UNAVAILABLE", "distributed_custody_overhead": "UNAVAILABLE"}
    observed: set[str] = set()
    first_digest = None
    error = None
    try:
        with FleetExecutor(args.coordinator, token=load_token(token_file=args.token_file),
                           tls_ca=args.tls_ca, public_key=public_key, name="physical-benchmark") as fleet:
            report["status_before"] = fleet.status()
            for i in range(args.iterations):
                start = time.monotonic_ns()
                result = fleet.submit(unit, timeout=args.timeout)
                elapsed = time.monotonic_ns() - start
                receipt = result.receipt
                receipt_path = args.out / f"receipt-{i:06d}.json"
                receipt_raw = json.dumps(receipt, sort_keys=True, indent=2).encode()
                receipt_path.write_bytes(receipt_raw)
                verify_started = time.monotonic_ns()
                check = verify_receipt(receipt, public_key=public_key,
                                       output=result.output, work_unit_digest=unit.digest())
                verify_ns = time.monotonic_ns() - verify_started
                digest = hashlib.sha256(result.output).hexdigest()
                workers = physical_route_records(receipt, args.route)
                observed.update(workers)
                sample = {"job_id": result.job_id, "end_to_end_ns": elapsed,
                          "receipt_verification_ns": verify_ns, "receipt_verified": check.valid,
                          "result_sha256": digest, "worker_report_ids": sorted(workers),
                          "receipt": receipt_path.name, "receipt_sha256": hashlib.sha256(receipt_raw).hexdigest()}
                report["samples"].append(sample)
                if not check.valid or not workers or (first_digest is not None and first_digest != digest):
                    raise RuntimeError("candidate receipt, explicit GPU route or exact repeatability check failed")
                first_digest = digest
            report["status_after"] = fleet.status()
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["observed_worker_report_ids"] = sorted(observed)
        report["end_to_end"] = summary([s["end_to_end_ns"] for s in report["samples"]])
        report["receipt_verification"] = summary([s["receipt_verification_ns"] for s in report["samples"]])
        report["error"] = error
        report["collection_complete"] = (error is None and len(report["samples"]) == args.iterations
                                         and len(observed) >= args.expected_workers)
        (args.out / "benchmark.json").write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    return 0 if report["collection_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
