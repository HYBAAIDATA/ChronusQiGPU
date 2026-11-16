#!/usr/bin/env python3
"""Measure actual PULVINI selective reconstruction on pinned UCI observations.

Runs the exact protected formal fold and selective tensor implementation.
Source Git blobs and observational input SHA-256 digests fail closed.
This is measured local software behavior, not device/hardware qualification.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import platform
import statistics
import time
from pathlib import Path
import numpy as np
import sklearn
from sklearn.datasets import load_digits, load_wine, load_breast_cancer
from chronus.pulvini.formal import PhiRecursiveOperator
from chronus.tensor.pulvini_selective import unfold_partial_recursive
import chronus.pulvini.formal as formal_module
import chronus.tensor.pulvini_selective as selective_module

INPUT_SHA256 = {
    "UCI_digits": "0f1c225bbabf3d4eaccd81f73c9594ceec77d84c9b425ef0e4cc815743050529",
    "UCI_wine": "09af9db3ce2a52b3f168d5d9eb1d4d4ceba584fad9e0e9aba63ff536c192c6a6",
    "UCI_breast_cancer": "602e781b91843b0ea3dc8bf3ff3e63055985230cad47c45a5099780e3c33459f",
}
SOURCE_GIT_BLOBS = {
    "formal": "863c0397e9c9e8ee9935183f4b736153b8160f8b",
    "selective": "69c20486cd4c36eb7339d0de3c9972e7e4350c8c",
}


def _blob(path: str) -> str:
    data = Path(path).read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def measure(repetitions: int = 31) -> dict:
    if type(repetitions) is not int or not 3 <= repetitions <= 200:
        raise ValueError("repetitions must be 3..200")
    actual = {"formal": _blob(formal_module.__file__),
              "selective": _blob(selective_module.__file__)}
    if actual != SOURCE_GIT_BLOBS:
        raise ValueError("executed source does not match pinned Git blobs")
    results = []
    for name, loader in (("UCI_digits", load_digits), ("UCI_wine", load_wine),
                         ("UCI_breast_cancer", load_breast_cancer)):
        array = np.asarray(loader().data, dtype=np.float64)
        stream = io.BytesIO()
        np.save(stream, array, allow_pickle=False)
        digest = hashlib.sha256(stream.getvalue()).hexdigest()
        if digest != INPUT_SHA256[name]:
            raise ValueError(f"observed data SHA-256 differs: {name}")
        operator = PhiRecursiveOperator(normalization="orthonormal")
        state = operator.fold_recursive(array, depth=4)
        full = operator.unfold_recursive(state).reshape(-1)
        size = min(64, array.size)
        samples = []
        last = None
        for _ in range(repetitions):
            started = time.perf_counter_ns()
            part = unfold_partial_recursive(state, 0, size)
            samples.append(time.perf_counter_ns() - started)
            if not np.allclose(part.values, array.reshape(-1)[:size], rtol=0, atol=1e-12):
                raise AssertionError("selective reconstruction incorrect")
            if not np.allclose(part.values, full[:size], rtol=0, atol=1e-12):
                raise AssertionError("formal inverse and selective result differ")
            last = part
        results.append({
            "dataset": name, "shape": list(array.shape),
            "source_class": "PUBLIC_OBSERVED_DATASET",
            "npy_sha256": digest, "fold_depth": state.depth,
            "selected_values": size,
            "independent_partial_correctness_verified": True,
            "full_unfold_called_inside_partial": False,
            "selected_deepest_folded_entries": last.touched_folded_indices,
            "selected_kernel_entries": last.touched_kernel_entries,
            "full_original_digest_verified_by_partial": False,
            "latency_ns_samples": samples,
            "latency_ns_median": int(statistics.median(samples)),
            "latency_ns_min": min(samples), "latency_ns_max": max(samples),
        })
    return {
        "schema": "chronus.public-observed-selective-reference/1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "classification": "ISOLATED_LOCAL_SOFTWARE_OBSERVED_INPUT",
        "source_git_blob_sha1": actual,
        "input_pinned_sha256": INPUT_SHA256,
        "host_platform": platform.platform(),
        "python": platform.python_version(),
        "numpy": np.__version__, "sklearn": sklearn.__version__,
        "repetitions": repetitions,
        "device_hardware_measured": False,
        "signed_evidence": False,
        "production_qualified": False,
        "results": results,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repetitions", type=int, default=31)
    opts = parser.parse_args(argv)
    target = opts.output.resolve()
    if target.exists():
        raise SystemExit("output exists; refusing evidence overwrite")
    result = measure(opts.repetitions)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps({"saved": str(target), "production_qualified": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
