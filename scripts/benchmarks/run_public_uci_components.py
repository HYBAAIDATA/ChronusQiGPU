#!/usr/bin/env python3
"""Run maintained Chronus CPU components on SHA-pinned public observations.

No generated data and no physical/backend claim. All measurements are local
application-call wall timings; an unkeyed checksum is not a signed receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

import numpy as np
import yaml

from chronus.pulvini import fold_verified, unfold_verified
from chronus.tensor.folded_state import ExactFoldState
from chronus.tensor.geodesic import PhiTensorCore

PUBLIC_SHA256 = frozenset({
    "0f1c225bbabf3d4eaccd81f73c9594ceec77d84c9b425ef0e4cc815743050529",
    "09af9db3ce2a52b3f168d5d9eb1d4d4ceba584fad9e0e9aba63ff536c192c6a6",
    "602e781b91843b0ea3dc8bf3ff3e63055985230cad47c45a5099780e3c33459f",
    "10e8a802908b34f86e5da8ce962f3c806694bc98450a18f61851af59f324bede",
})


def _stats(samples: list[int]) -> dict:
    if not samples:
        raise ValueError("measurement samples missing")
    values = sorted(samples)
    n = len(values)
    return {"count": n, "median_ns": int(statistics.median(values)),
            "p95_ns": values[math.ceil(.95*n)-1],
            "p99_ns": values[math.ceil(.99*n)-1]}


def _head() -> str | None:
    try:
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True,
                                      stderr=subprocess.DEVNULL).strip()
        return sha if len(sha) in (40, 64) else None
    except (OSError, subprocess.CalledProcessError):
        return None


def _measure_source(path: Path, expected: str, kind: str, *, depth: int) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > (1 << 20):
        raise ValueError("missing, linked or oversize public dataset")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("input SHA-256 mismatch")
    result = {"path": path.name, "source_sha256": expected,
              "input_bytes": len(raw), "source_class": "PUBLIC_OBSERVED_DATASET"}
    if kind == "tensor":
        array = np.load(io.BytesIO(raw), allow_pickle=False)
        if (not isinstance(array, np.ndarray) or array.ndim != 2 or
                array.dtype != np.dtype("float64") or not np.all(np.isfinite(array))):
            raise ValueError("unexpected public numeric tensor contract")
        expected_add = np.add(array, array)
        core = PhiTensorCore()
        for _ in range(10):
            core.execute("add", array, array)
            np.add(array, array)
        core_times = []
        baseline_times = []
        for i in range(201):
            if i % 2:
                t = time.perf_counter_ns()
                actual = core.execute("add", array, array)
                core_times.append(time.perf_counter_ns() - t)
                t = time.perf_counter_ns()
                baseline = np.add(array, array)
                baseline_times.append(time.perf_counter_ns() - t)
            else:
                t = time.perf_counter_ns()
                baseline = np.add(array, array)
                baseline_times.append(time.perf_counter_ns() - t)
                t = time.perf_counter_ns()
                actual = core.execute("add", array, array)
                core_times.append(time.perf_counter_ns() - t)
            if (actual["backend"] != "numpy-reference" or
                    not np.array_equal(actual["output"], baseline) or
                    not np.array_equal(actual["output"], expected_add)):
                raise ValueError("tensor output/backend verification failed")
        fold_times, unfold_times = [], []
        for _ in range(3):
            state, receipt = fold_verified(array, depth=depth)
            unfold_verified(state, receipt=receipt)
        for _ in range(31):
            t = time.perf_counter_ns()
            state, receipt = fold_verified(array, depth=depth)
            fold_times.append(time.perf_counter_ns() - t)
            t = time.perf_counter_ns()
            restored = unfold_verified(state, receipt=receipt)
            unfold_times.append(time.perf_counter_ns() - t)
            if not np.allclose(restored, array, rtol=1e-12, atol=1e-12):
                raise ValueError("numerical reconstruction failed")
        if receipt.retained_bytes != receipt.folded_bytes + receipt.kernel_bytes:
            raise ValueError("incomplete kernel storage accounting")
        result["tensor"] = {
            "shape": list(array.shape), "dtype": str(array.dtype),
            "same_workload_numpy_add": _stats(baseline_times),
            "chronus_phitensorcore_add": _stats(core_times),
            "backend": "numpy-reference", "output_exact_match": True,
            "chronus_over_numpy_latency_ratio":
                statistics.median(core_times) / statistics.median(baseline_times),
            "pulvini_depth": state.depth,
            "pulvini_verified_fold_including_reconstruction": _stats(fold_times),
            "pulvini_additional_verified_unfold": _stats(unfold_times),
            "pulvini_original_bytes": receipt.original_bytes,
            "pulvini_active_bytes": receipt.folded_bytes,
            "pulvini_all_kernel_bytes": receipt.kernel_bytes,
            "pulvini_total_retained_bytes": receipt.retained_bytes,
            "pulvini_relative_error": receipt.relative_reconstruction_error,
            "pulvini_bitwise_identical": restored.tobytes() == array.tobytes(),
            "net_compression_claim": False,
        }
    elif kind != "snapshot":
        raise ValueError("unsupported public input kind")

    state = ExactFoldState.from_bytes(raw)
    if state.unfold() != raw:
        raise ValueError("exact reference recovery failed")
    fold_times, full_times, partial_times = [], [], []
    for _ in range(5):
        start = time.perf_counter_ns()
        state = ExactFoldState.from_bytes(raw)
        fold_times.append(time.perf_counter_ns() - start)
        start = time.perf_counter_ns()
        recovered = state.unfold()
        full_times.append(time.perf_counter_ns() - start)
        if recovered != raw:
            raise ValueError("full byte-for-byte recovery failed")
        lo = len(raw) // 2
        hi = min(len(raw), lo + 64)
        for _ in range(31):
            start = time.perf_counter_ns()
            recovered = state.unfold_partial(lo, hi)
            partial_times.append(time.perf_counter_ns() - start)
            if recovered != raw[lo:hi]:
                raise ValueError("partial byte-for-byte recovery failed")
    result["exact_byte_state"] = {
        "encoded_bytes": len(state.folded),
        "byte_exact_roundtrip_verified": True, "partial_window_equal": True,
        "fold_call": _stats(fold_times), "full_unfold_call": _stats(full_times),
        "partial_up_to_64_bytes_call": _stats(partial_times),
        "constant_time_proven": False, "net_compression_claim": False,
    }
    return result


def run(manifest: Path, depth: int = 4) -> dict:
    manifest = Path(manifest).resolve(strict=True)
    if not 0 <= depth <= 32:
        raise ValueError("depth outside policy")
    source = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    if not isinstance(source, dict) or source.get("schema") != "chronus.real-workload-manifest/1":
        raise ValueError("unexpected public input manifest")
    entries = source.get("data_sources")
    if not isinstance(entries, list) or len(entries) != 4:
        raise ValueError("expected exactly four pinned public observational inputs")
    seen = set()
    results = []
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("source_class") != "PUBLIC_OBSERVED_DATASET":
            raise ValueError("public observed source identity missing")
        sha, kind, filename = entry.get("sha256"), entry.get("kind"), entry.get("path")
        if (sha not in PUBLIC_SHA256 or not isinstance(filename, str) or
                "/" in filename or "\\" in filename or filename in seen):
            raise ValueError("unverified public source or duplicate filename")
        seen.add(filename)
        results.append(_measure_source(manifest.parent / filename, sha, kind, depth=depth))
    evidence = {
        "schema": "chronus.public-uci-components/1",
        "classification": "OBSERVED_PUBLIC_INPUT_SOURCE_VERIFIED_LOCAL_SOFTWARE",
        "git_commit": _head(), "execution_platform": platform.platform(),
        "python": platform.python_version(), "numpy": np.__version__,
        "logical_cpus": os.cpu_count(), "input_data_generated": False,
        "warmup_fold_calls": 3, "samples_verified_fold": 31,
        "warmup_add_calls": 10, "samples_add": 201,
        "samples_byte_fold": 5, "samples_partial_read_per_fold": 31,
        "full_triad_execution": "NOT TESTED", "accelerator": "NOT MEASURED",
        "production_qualification": "UNVERIFIED", "measurements": results,
    }
    evidence["integrity_sha256"] = hashlib.sha256(json.dumps(
        evidence, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--depth", type=int, default=4)
    args = parser.parse_args(argv)
    try:
        dest = args.output.resolve()
        if dest.exists() or dest == args.manifest.resolve():
            raise ValueError("refusing overwrite or invalid evidence destination")
        result = run(args.manifest, depth=args.depth)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2)
        print(json.dumps({"result": "PASS", "output": str(dest),
                          "production_qualification": "UNVERIFIED"}))
        return 0
    except (OSError, ValueError, TypeError, RuntimeError, yaml.YAMLError) as exc:
        print(json.dumps({"result": "FAIL", "reason": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
