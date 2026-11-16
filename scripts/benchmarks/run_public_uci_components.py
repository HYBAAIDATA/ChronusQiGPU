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

PINNED_INPUTS = {
    "uci_digits.npy": ("0f1c225bbabf3d4eaccd81f73c9594ceec77d84c9b425ef0e4cc815743050529", "tensor"),
    "uci_wine.npy": ("09af9db3ce2a52b3f168d5d9eb1d4d4ceba584fad9e0e9aba63ff536c192c6a6", "tensor"),
    "uci_breast_cancer.npy": ("602e781b91843b0ea3dc8bf3ff3e63055985230cad47c45a5099780e3c33459f", "tensor"),
    "uci_wine_packaged_file.snapshot": ("10e8a802908b34f86e5da8ce962f3c806694bc98450a18f61851af59f324bede", "snapshot"),
}


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
                                      cwd=Path(__file__).resolve().parents[2],
                                      stderr=subprocess.DEVNULL).strip()
        return sha if len(sha) in (40, 64) else None
    except (OSError, subprocess.CalledProcessError):
        return None



def _paired_verified_work(array: np.ndarray, core: PhiTensorCore, *, depth: int,
                          repetitions: int = 13, warmup: int = 2) -> dict:
    """Measure matched useful work including ALL verified folding overhead.

    Both routes compute x+x on the same observed numeric tensor. The candidate
    folds, verifies, independently unfolds, then executes through Chronus.
    The reference directly computes the same addition through NumPy. This is
    a CPU software comparison, never a quantum or device acceleration proof.
    """
    if type(repetitions) is not int or not 3 <= repetitions <= 201:
        raise ValueError("matched repetitions must be within 3..201")
    if type(warmup) is not int or not 0 <= warmup <= 20:
        raise ValueError("warmup outside policy")
    reference_output = np.add(array, array)
    candidate_ns, reference_ns = [], []
    maximum_error = 0.0

    def _candidate() -> np.ndarray:
        state, receipt = fold_verified(array, depth=depth)
        if receipt.retained_bytes != receipt.folded_bytes + receipt.kernel_bytes:
            raise ValueError("incomplete PULVINI retained-state accounting")
        reconstructed = unfold_verified(state, receipt=receipt)
        operation = core.execute("add", reconstructed, reconstructed)
        if operation["backend"] != "numpy-reference":
            raise ValueError("unexpected or unverified tensor backend")
        return operation["output"]

    def _reference() -> np.ndarray:
        return np.add(array, array)

    for i in range(warmup + repetitions):
        measured = i >= warmup
        calls = ((_candidate, candidate_ns), (_reference, reference_ns)) if i % 2 else (
            (_reference, reference_ns), (_candidate, candidate_ns))
        for execute, samples in calls:
            start = time.perf_counter_ns()
            output = execute()
            elapsed = time.perf_counter_ns() - start
            if not np.allclose(output, reference_output, rtol=1e-12, atol=1e-12):
                raise ValueError("matched useful-work output parity failed")
            maximum_error = max(maximum_error, float(np.max(np.abs(output - reference_output))))
            if measured:
                samples.append(elapsed)

    direct_median = statistics.median(reference_ns)
    candidate_median = statistics.median(candidate_ns)
    if direct_median <= 0 or candidate_median <= 0:
        raise ValueError("timing clock resolution insufficient for comparison")
    speedup = direct_median / candidate_median
    return {
        "classification": "MATCHED_CPU_REFERENCE_WORK_NOT_QUANTUM_ACCELERATION",
        "useful_work": "add same observed tensor to itself with output tolerance 1e-12",
        "reference_path": "direct NumPy add, same input",
        "candidate_path": "verified PULVINI fold, verified unfold, PhiTensorCore add",
        "candidate_backend": "numpy-reference",
        "fold_and_verification_in_timed_candidate": True,
        "input_generated": False,
        "same_result_within_tolerance": True,
        "maximum_absolute_output_error": maximum_error,
        "warmups_per_path": warmup,
        "measured_pairs": repetitions,
        "direct_add_ns": _stats(reference_ns),
        "fold_unfold_add_ns": _stats(candidate_ns),
        "raw_direct_add_ns": reference_ns,
        "raw_fold_unfold_add_ns": candidate_ns,
        "observed_speedup_direct_over_folded": speedup,
        "target_speedup": 13.0,
        "meets_13x_target": speedup >= 13.0,
        "physical_or_quantum_advantage_claimed": False,
        "production_qualification": "UNVERIFIED",
    }

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
        result["matched_useful_work"] = _paired_verified_work(array, core, depth=depth)
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
        if (not isinstance(filename, str) or filename not in PINNED_INPUTS or
                PINNED_INPUTS[filename] != (sha, kind) or filename in seen):
            raise ValueError("public source name, digest, type or uniqueness mismatch")
        seen.add(filename)
        results.append(_measure_source(manifest.parent / filename, sha, kind, depth=depth))
    if seen != set(PINNED_INPUTS):
        raise ValueError("missing required public observational input")
    evidence = {
        "schema": "chronus.public-uci-components/1",
        "classification": "OBSERVED_PUBLIC_INPUT_SOURCE_VERIFIED_LOCAL_SOFTWARE",
        "git_commit": _head(), "execution_platform": platform.platform(),
        "python": platform.python_version(), "numpy": np.__version__,
        "logical_cpus": os.cpu_count(), "input_data_generated": False,
        "warmup_fold_calls": 3, "samples_verified_fold": 31,
        "warmup_add_calls": 10, "samples_add": 201,
        "matched_workload_repetitions": 13, "matched_workload_warmups": 2,
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
