#!/usr/bin/env python3
"""Benchmark selective PULVINI reconstruction on SHA256-verified observed .npy data.

No data generation, physical accelerator inference, production admission or
signed attestation. Index compilation cost is recorded separately from reads.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import statistics
import subprocess
import sys
import time

import numpy as np

from chronus.pulvini.partial import VerifiedFoldIndex
from chronus.tensor.folded_compute import FoldedTensorExecutor


def measure(path: Path, sha256: str, *, depth: int = 4,
            window: int = 64, samples: int = 61) -> dict:
    if not isinstance(sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ValueError("full expected source sha256 required")
    path = Path(path)
    if path.is_symlink():
        raise ValueError("symlink inputs are not permitted")
    source = path.resolve(strict=True)
    if not source.is_file() or source.stat().st_size > 8*1024*1024:
        raise ValueError("untrusted or oversized source")
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise ValueError("source sha256 mismatch")
    array = np.load(io.BytesIO(raw), allow_pickle=False)
    if (not isinstance(array,np.ndarray) or array.dtype != np.dtype("float64") or
        not 1 <= array.ndim <= 4 or not 0 < array.size <= 1_000_000 or
        not np.all(np.isfinite(array))):
        raise ValueError("unsupported numeric observed data contract")
    if type(samples) is not int or not 5 <= samples <= 10000:
        raise ValueError("sample budget outside policy")
    if type(window) is not int or not 1 <= window <= array.size:
        raise ValueError("window outside source size")
    exe = FoldedTensorExecutor(depth=depth)
    t=time.perf_counter_ns()
    operand=exe.fold(array)
    initial_ns=time.perf_counter_ns()-t
    t=time.perf_counter_ns()
    index=VerifiedFoldIndex.compile(operand)
    compile_ns=time.perf_counter_ns()-t
    start=(array.size-window)//2
    stop=start+window
    expected=array.reshape(-1)[start:stop]
    np.testing.assert_allclose(index.read(start,stop),expected,rtol=1e-12,atol=1e-12)
    np.testing.assert_allclose(exe.materialise(operand).reshape(-1)[start:stop],expected,
                               rtol=1e-12,atol=1e-12)
    partial_times,full_times=[],[]
    for _ in range(3):
        index.read(start,stop)
        exe.materialise(operand)
    for i in range(samples):
        if i%2:
            t=time.perf_counter_ns()
            reconstructed=exe.materialise(operand).reshape(-1)[start:stop]
            full_times.append(time.perf_counter_ns()-t)
            t=time.perf_counter_ns()
            selected=index.read(start,stop)
            partial_times.append(time.perf_counter_ns()-t)
        else:
            t=time.perf_counter_ns()
            selected=index.read(start,stop)
            partial_times.append(time.perf_counter_ns()-t)
            t=time.perf_counter_ns()
            reconstructed=exe.materialise(operand).reshape(-1)[start:stop]
            full_times.append(time.perf_counter_ns()-t)
        np.testing.assert_allclose(selected,reconstructed,rtol=1e-12,atol=1e-12)
    try:
        commit=subprocess.check_output(["git","rev-parse","HEAD"],text=True,
                cwd=Path(__file__).resolve().parents[2],stderr=subprocess.DEVNULL).strip()
    except (OSError,subprocess.CalledProcessError):
        commit="UNAVAILABLE"
    evidence={
        "schema":"chronus.pulvini.real-observed-selective/1",
        "source_sha256":sha256,"source_bytes":len(raw),"tensor_shape":list(array.shape),
        "fold_depth":depth,"window_elements":window,"samples_per_path":samples,
        "index_built_after_full_reconstruction_validation":True,
        "original_numpy_fold_ns":initial_ns,"immutable_index_compile_ns":compile_ns,
        "selected_per_call_ns":partial_times,"full_unfold_per_call_ns":full_times,
        "median_selected_ns":int(statistics.median(partial_times)),
        "median_full_unfold_ns":int(statistics.median(full_times)),
        "comparison_excludes_index_compilation":True,
        "retained_folded_bytes":operand.evidence.retained_bytes,
        "original_numeric_bytes":operand.evidence.original_bytes,
        "backend":"numpy-reference","git_commit":commit,"python":platform.python_version(),
        "numpy":np.__version__,"logical_cpus":os.cpu_count(),
        "physical_accelerator_measured":False,"net_compression_claim":False,
        "production_qualification":"UNVERIFIED","signed_evidence":False,
        "data_generated_by_benchmark":False,
    }
    evidence["integrity_sha256"]=hashlib.sha256(json.dumps(evidence,sort_keys=True,
                    separators=(",",":")).encode()).hexdigest()
    return evidence


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data",type=Path,required=True)
    parser.add_argument("--sha256",required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--depth",type=int,default=4)
    parser.add_argument("--window",type=int,default=64)
    parser.add_argument("--samples",type=int,default=61)
    args=parser.parse_args(argv)
    try:
        target=args.output.resolve()
        if target.exists() or target==args.data.resolve():
            raise ValueError("refusing to overwrite evidence or its source")
        evidence=measure(args.data,args.sha256,depth=args.depth,
                         window=args.window,samples=args.samples)
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open("x",encoding="utf8") as stream:
            json.dump(evidence,stream,indent=2)
        print(json.dumps({"result":"PASS","output":str(target),
                          "production_qualification":"UNVERIFIED"}))
        return 0
    except (OSError,ValueError,TypeError,AssertionError) as error:
        print(json.dumps({"result":"FAIL","reason":str(error)}),file=sys.stderr)
        return 2


if __name__=="__main__":
    sys.exit(main())
