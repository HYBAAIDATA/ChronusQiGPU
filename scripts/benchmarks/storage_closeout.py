#!/usr/bin/env python3
"""Run bounded, reproducible Chronus storage and complete-state fold measurements.

Application call timings and controlled reference inputs are NOT device IOPS,
durability guarantees, hardware speedups, or production evidence. All kernels,
chronology, dtype and shape are retained when assessing the PULVINI fold.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import platform
import sqlite3
import statistics
import subprocess
import tempfile
import time
from pathlib import Path

import numpy as np

from chronus.pulvini import FoldState, fold_verified, unfold_verified
from chronus.storage.durable import DurableTheseusService


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _latencies(samples: list[int]) -> dict:
    if not samples:
        raise ValueError("latency observations required")
    ordered = sorted(samples)
    def at(q: float) -> int:
        return ordered[math.ceil(q * len(ordered)) - 1]
    return {
        "sample_count": len(ordered),
        "median_ns": int(statistics.median(ordered)),
        "p95_ns": at(0.95),
        "p99_ns": at(0.99),
        "total_ns": sum(ordered),
        "application_calls_per_second": len(ordered) * 1e9 / sum(ordered),
    }


def storage_benchmark(*, records: int, payload_bytes: int) -> dict:
    """One local SQLite/WAL reference run; logical payload roundtrip verified."""
    if records < 1 or payload_bytes < 1 or records > 4096 or payload_bytes > (1 << 20):
        raise ValueError("reference workload outside bounded policy")
    samples = [
        hashlib.shake_256(f"closeout:{i}:{payload_bytes}".encode()).digest(payload_bytes)
        for i in range(records)
    ]
    writes: list[int] = []
    reads: list[int] = []
    with tempfile.TemporaryDirectory(prefix="chronus-closeout-") as directory:
        database = Path(directory) / "theseus.sqlite3"
        custody = DurableTheseusService(str(database), lane_count=32)
        identifiers: list[str] = []
        for payload in samples:
            started = time.perf_counter_ns()
            record = custody.store("reference-tenant", payload)
            writes.append(time.perf_counter_ns() - started)
            identifiers.append(record.object_id)
        # Fresh service instance and fresh SQLite connections.
        custody = DurableTheseusService(str(database), lane_count=32)
        for identifier, payload in zip(identifiers, samples):
            started = time.perf_counter_ns()
            restored = custody.reconstruct("reference-tenant", identifier)
            reads.append(time.perf_counter_ns() - started)
            if restored != payload:
                raise AssertionError("byte-for-byte durable readback mismatch")
        custody.verify_store()
        checkpoint = custody.checkpoint()
        sqlite_bytes = sum(
            candidate.stat().st_size
            for candidate in (database, Path(str(database) + "-wal"),
                              Path(str(database) + "-shm"))
            if candidate.exists()
        )
    return {
        "classification": "CONTROLLED_REFERENCE_ONLY",
        "input_class": "deterministic generated test bytes, not production/customer data",
        "records": records,
        "payload_bytes_each": payload_bytes,
        "logical_payload_bytes": records * payload_bytes,
        "sqlite_family_bytes_after_checkpoint": sqlite_bytes,
        "write_call_latency": _latencies(writes),
        "read_call_latency": _latencies(reads),
        "checkpoint": checkpoint,
        "fresh_service_reopen_verified": True,
        "byte_exact_readback_verified": True,
        "device_iops": None,
        "nvme_baseline": None,
        "power_loss_recovery": None,
        "independent_verification": None,
        "limitations": "Timings include Python and SQLite overhead; no physical media metrics.",
    }


def serialize_complete_fold(state: FoldState) -> bytes:
    """Store every kernel + all reconstruction metadata, without ZIP compression."""
    sink = io.BytesIO()
    values = {
        "folded": state.folded,
        "kernel_count": np.asarray([len(state.kernels)], dtype=np.int64),
        "sizes": np.asarray(state.sizes, dtype=np.int64),
        "original_shape": np.asarray(state.original_shape, dtype=np.int64),
        "original_dtype": np.asarray([state.original_dtype]),
        "normalization": np.asarray([state.normalization]),
    }
    values.update({f"kernel_{i}": kernel for i, kernel in enumerate(state.kernels)})
    np.savez(sink, **values)
    return sink.getvalue()


def deserialize_complete_fold(data: bytes) -> FoldState:
    with np.load(io.BytesIO(data), allow_pickle=False) as values:
        count = int(values["kernel_count"][0])
        if count < 0 or count > 32 or count != len(values["sizes"]) - 1:
            raise ValueError("invalid serialized fold chronology")
        return FoldState(
            folded=values["folded"].copy(),
            kernels=tuple(values[f"kernel_{i}"].copy() for i in range(count)),
            sizes=tuple(int(v) for v in values["sizes"]),
            original_shape=tuple(int(v) for v in values["original_shape"]),
            original_dtype=str(values["original_dtype"][0]),
            normalization=str(values["normalization"][0]),
        )


def fold_benchmark(*, elements: int, depth: int, seed: int) -> dict:
    if not 1 <= elements <= 1_000_000 or not 0 <= depth <= 32:
        raise ValueError("fold reference parameters outside policy")
    generator = np.random.default_rng(seed)
    original = (
        np.sin(np.arange(elements, dtype=np.float64) / 17.0)
        + 0.01 * generator.standard_normal(elements)
    )
    started = time.perf_counter_ns()
    state, receipt = fold_verified(original, depth=depth)
    fold_ns = time.perf_counter_ns() - started
    representation = serialize_complete_fold(state)
    recovered_state = deserialize_complete_fold(representation)
    started = time.perf_counter_ns()
    recovered = unfold_verified(recovered_state, receipt=receipt)
    unfold_ns = time.perf_counter_ns() - started
    if not np.allclose(recovered, original, rtol=0, atol=1e-12):
        raise AssertionError("PULVINI reference reconstruction exceeded tolerance")
    return {
        "classification": "CONTROLLED_REFERENCE_ONLY",
        "input_class": "seeded structured sine with noise; not customer data",
        "seed": seed,
        "elements": elements,
        "requested_depth": depth,
        "executed_depth": state.depth,
        "normalization": state.normalization,
        "input_sha256": _sha(original.tobytes()),
        "recovered_sha256": _sha(recovered.tobytes()),
        "bitwise_identical": original.tobytes() == recovered.tobytes(),
        "relative_reconstruction_error": receipt.relative_reconstruction_error,
        "reconstruction_tolerance": 1e-12,
        "original_bytes": receipt.original_bytes,
        "active_working_set_bytes": receipt.folded_bytes,
        "all_kernel_bytes": receipt.kernel_bytes,
        "complete_retained_bytes": receipt.retained_bytes,
        "serialized_complete_bytes": len(representation),
        "active_ratio": receipt.working_set_ratio,
        "complete_retained_ratio": receipt.retained_state_ratio,
        "serialized_total_ratio": receipt.original_bytes / len(representation),
        "fold_ns": fold_ns,
        "reconstruction_ns": unfold_ns,
        "claimed_11_5x_promoted": False,
        "device_evidence": None,
        "limitations": "Numerical float64 recovery; all kernels retained; no general compression proof.",
    }


def measure(*, records: int = 32, payload_bytes: int = 256,
            elements: int = 4096, depth: int = 8, seed: int = 20260723) -> dict:
    try:
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        head = None
    return {
        "schema": "chronus.storage-fold-reference/1",
        "git_commit": head,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "sqlite_version": sqlite3.sqlite_version,
        "numpy_version": np.__version__,
        "claim_elevation": "NONE",
        "storage": storage_benchmark(records=records, payload_bytes=payload_bytes),
        "pulvini": fold_benchmark(elements=elements, depth=depth, seed=seed),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=int, default=64)
    parser.add_argument("--payload-bytes", type=int, default=1024)
    parser.add_argument("--elements", type=int, default=10648)
    parser.add_argument("--depth", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260723)
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()
    data = measure(records=args.records, payload_bytes=args.payload_bytes,
                   elements=args.elements, depth=args.depth, seed=args.seed)
    content = json.dumps(data, sort_keys=True, indent=2, allow_nan=False) + "\n"
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(content, encoding="utf-8")
    print(content, end="")


if __name__ == "__main__":
    main()
