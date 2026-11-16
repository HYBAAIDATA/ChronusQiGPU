#!/usr/bin/env python3
"""Device-directory application storage evidence from genuine SHA-pinned inputs.

Measures THESEUS SQLite/WAL application calls, NEVER raw NVMe IOPS, actual
power-loss recovery, production qualification, or an independent attestation.
No benchmark inputs are generated or silently substituted.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform
import sqlite3
import statistics
import sys
import tempfile
from time import perf_counter_ns

from benchmarks.real_workload_benchmark import _git_commit, _read_verified, discover
from chronus.storage.durable import DurableTheseusService


def _timing(samples: list[int]) -> dict:
    if not samples:
        raise ValueError("at least one executed operation is required")
    values = sorted(samples)
    return {
        "count": len(values),
        "median_ns": int(statistics.median(values)),
        "p95_ns": values[math.ceil(0.95 * len(values)) - 1],
        "p99_ns": values[math.ceil(0.99 * len(values)) - 1],
        "total_ns": sum(values),
        "application_calls_per_second": len(values) * 1e9 / sum(values),
    }


def measure(manifest: Path, target_directory: Path) -> dict:
    """Record distinct real input writes, reopen, and byte-verify every read."""
    manifest = Path(manifest).resolve(strict=True)
    provided = Path(target_directory)
    if provided.is_symlink() or not provided.is_dir():
        raise ValueError("target must be an existing non-symlink directory")
    target = provided.resolve(strict=True)
    sources = discover(manifest)
    # All inputs are verified BEFORE creating any SQLite state on target.
    inputs = [(item, _read_verified(item)) for item in sources]
    if len({item["sha256"] for item, _ in inputs}) != len(inputs):
        raise ValueError("duplicate source content cannot count as distinct writes")
    input_class = ("TEST_FIXTURE_NON_PRODUCTION" if any(
        item["source_class"] == "TEST_FIXTURE_NON_PRODUCTION" for item, _ in inputs
    ) else "OPERATOR_DECLARED_OR_PUBLIC_OBSERVED_NOT_ATTESTED")
    results = []
    writes: list[int] = []
    reads: list[int] = []
    with tempfile.TemporaryDirectory(prefix="chronus-device-reference-", dir=target) as folder:
        path = Path(folder) / "custody.sqlite3"
        service = DurableTheseusService(str(path), lane_count=32)
        for item, payload in inputs:
            started = perf_counter_ns()
            record = service.store("device-reference", payload)
            elapsed = perf_counter_ns() - started
            writes.append(elapsed)
            results.append({
                "source_sha256": item["sha256"],
                "source_class": item["source_class"],
                "provenance": item["provenance"],
                "source_bytes": len(payload),
                "object_id": record.object_id,
                "write_application_ns": elapsed,
            })
        service = DurableTheseusService(str(path), lane_count=32)
        for result, (_, payload) in zip(results, inputs):
            started = perf_counter_ns()
            recovered = service.reconstruct("device-reference", result["object_id"])
            elapsed = perf_counter_ns() - started
            reads.append(elapsed)
            if recovered != payload:
                raise ValueError("THESEUS byte-exact restart/readback failed")
            result["read_application_ns"] = elapsed
            result["readback_verified"] = True
        service.verify_store()
        checkpoint = service.checkpoint()
        if checkpoint["busy"] != 0:
            raise ValueError("SQLite checkpoint remained busy")
        sqlite_bytes = sum(
            item.stat().st_size for item in Path(folder).iterdir() if item.is_file()
        )
    return {
        "schema": "chronus.storage-device-application-reference/1",
        "status": "MEASURED_LOCAL_APPLICATION_REFERENCE",
        "production_qualified": False,
        "data_generated_by_benchmark": False,
        "source_commit": _git_commit(),
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "host": platform.platform(),
        "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version,
        "target_directory": str(target),
        "target_directory_stat_device": target.stat().st_dev,
        "physical_disk_model": None,
        "physical_media_type": None,
        "disk_hardware_attested": False,
        "input_classification": input_class,
        "distinct_source_count": len(inputs),
        "total_source_bytes": sum(len(payload) for _, payload in inputs),
        "write_application": _timing(writes),
        "read_application": _timing(reads),
        "sqlite_family_bytes_after_checkpoint": sqlite_bytes,
        "sqlite_checkpoint": checkpoint,
        "fresh_service_restart_verified": True,
        "all_payloads_byte_exact": True,
        "physical_device_iops": None,
        "power_loss_recovery": None,
        "sustained_soak": None,
        "independent_attestation": None,
        "results": results,
        "limitation": (
            "SQLite/WAL app-call timings on nominated filesystem, not physical "
            "IOPS, power-loss recovery, device-vs-baseline or a release verdict."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--target-directory", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        sources = discover(args.manifest)
        output = args.output.resolve()
        protected = {args.manifest.resolve(), *(s["path"].resolve() for s in sources)}
        if output in protected or output.exists():
            raise ValueError("evidence destination must be new and must not overwrite inputs")
        evidence = measure(args.manifest, args.target_directory)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as stream:
            json.dump(evidence, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
        print(json.dumps({
            "result": "RECORDED", "evidence_path": str(output),
            "production_qualified": False,
        }))
        return 0
    except (ValueError, TypeError, OSError, sqlite3.Error) as exc:
        print(json.dumps({
            "result": "UNAVAILABLE_OR_FAILED", "reason": str(exc),
            "production_qualified": False,
        }), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
