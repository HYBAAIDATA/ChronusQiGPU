"""Equivalent-output region retrieval over the current Aethel numeric plane.

Run from the repository root: python -m scripts.benchmark_data_region --help.
Synthetic local evidence, not an enterprise capacity or CapEx qualification.
PULVINI's exact rational plane is distinct; this runner does not benchmark it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import statistics
import subprocess
import time
from pathlib import Path

import numpy as np

from aethel.phi_fold import phi_fold, phi_unfold, region_flat_boundaries, unfold_region

ROOT = Path(__file__).resolve().parents[1]


class BenchmarkValidationError(RuntimeError):
    """A timed operation did not return the complete agreed result."""


def _integer(name, value, minimum):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")


def _verify(got, expected):
    if (got.shape != expected.shape or got.dtype != expected.dtype
            or got.tobytes(order="C") != expected.tobytes(order="C")):
        raise BenchmarkValidationError("region result is not bit-identical to the reference")


def _provenance():
    try:
        commit = subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL, text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    files = ("scripts/benchmark_data_region.py", "aethel/phi_fold.py", "aethel/__init__.py")
    return {
        "checkout_commit": commit,
        "source_sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in files},
        "python": platform.python_version(), "numpy": np.__version__,
        "platform": platform.platform(),
    }


def benchmark_regions(data, region, *, depth=3, repetitions=10, warmups=2):
    """Measure three implementations of the same owned-array region result.

    Setup is separate. Each timed call includes output allocation but excludes
    this runner's post-call bitwise check. The full-decode comparator intentionally
    decodes the whole object first; the direct dense-region comparator does not.
    Neither comparator may be omitted when interpreting the report.
    """
    _integer("depth", depth, 0)
    _integer("repetitions", repetitions, 1)
    _integer("warmups", warmups, 0)
    data = np.asarray(data)
    # Validate before timing or custody: use the production boundary rules.
    _, region_shape = region_flat_boundaries(data.shape, region)
    expected = np.ascontiguousarray(data[region]).reshape(region_shape).copy()
    setup_started = time.perf_counter_ns()
    state = phi_fold(data, depth=depth)
    fold_setup_ns = time.perf_counter_ns() - setup_started
    # Establish whole-object correctness independently before selective reads.
    _verify(phi_unfold(state), data)

    def direct():
        return data[region].reshape(region_shape).copy(), None

    def full_decode():
        return phi_unfold(state)[region].reshape(region_shape).copy(), None

    def selective():
        return unfold_region(state, region)

    operations = {"dense_direct_region": direct, "full_decode_then_region": full_decode,
                  "folded_selective_region": selective}
    samples = {name: [] for name in operations}
    last_stats = None
    names = tuple(operations)
    # Rotate execution order to avoid always favouring one cache/order position.
    for iteration in range(warmups + repetitions):
        shift = iteration % len(names)
        for name in names[shift:] + names[:shift]:
            started = time.perf_counter_ns()
            result, stats = operations[name]()
            elapsed = time.perf_counter_ns() - started
            _verify(result, expected)
            if stats is not None:
                last_stats = stats
            if iteration >= warmups:
                samples[name].append(elapsed)
    medians = {name: statistics.median(values) for name, values in samples.items()}
    selective_median = medians["folded_selective_region"]
    return {
        "schema_version": "hyba.data-region-benchmark/1",
        "workload": "bit-exact owned region retrieval",
        "plane": "aethel.numeric_partition", "synthetic": None,
        "shape": list(data.shape), "dtype": data.dtype.str,
        "region": [[s.start, s.stop, s.step] if isinstance(s, slice) else s for s in region],
        "depth": depth, "repetitions": repetitions, "warmups": warmups,
        "input_sha256": hashlib.sha256(data.tobytes(order="C")).hexdigest(),
        "output_sha256": hashlib.sha256(expected.tobytes(order="C")).hexdigest(),
        "output_shape": list(expected.shape), "output_bytes": expected.nbytes,
        "bit_exact_all_calls": True, "fold_setup_ns": fold_setup_ns,
        "timing_boundary": "call and output allocation; runner validation excluded; fold setup separate",
        "elapsed_ns": samples, "median_elapsed_ns": medians,
        "full_decode_over_selective_time_ratio": (
            medians["full_decode_then_region"] / selective_median if selective_median else None),
        "dense_direct_over_selective_time_ratio": (
            medians["dense_direct_region"] / selective_median if selective_median else None),
        "selective_read": {
            "requested_values": last_stats.requested_values,
            "source_values_read": last_stats.source_values_read,
            "decoded_bytes": last_stats.decoded_bytes,
            "full_length": last_stats.full_length,
        },
        "resident_array_payload_bytes": sum(a.nbytes for a in (state.retained, *state.complements)),
        "input_array_payload_bytes": data.nbytes,
        "retained_working_values": state.retained_size,
        "storage_scope": "array payload only; excludes Python objects, hashes and allocator overhead",
        "physical_compression_ratio": None, "peak_memory_bytes": None,
        "energy_joules": None, "statistical_significance": None,
        "claim_boundary": "local region-retrieval measurements only; no fleet, CapEx or exponential-speed claim",
        "provenance": _provenance(),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=256)
    parser.add_argument("--cols", type=int, default=256)
    parser.add_argument("--region", type=int, nargs=4, default=(8, 16, 8, 16),
                        metavar=("ROW_START", "ROW_STOP", "COL_START", "COL_STOP"))
    parser.add_argument("--depth", type=int, default=3)
    parser.add_argument("--repetitions", type=int, default=10)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    _integer("rows", args.rows, 1)
    _integer("cols", args.cols, 1)
    rng = np.random.default_rng(args.seed)
    data = rng.normal(size=(args.rows, args.cols)).astype(np.float64)
    r0, r1, c0, c1 = args.region
    report = benchmark_regions(data, (slice(r0, r1), slice(c0, c1)),
                               depth=args.depth, repetitions=args.repetitions, warmups=args.warmups)
    report.update(synthetic=True, seed=args.seed)
    payload = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(payload)
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
