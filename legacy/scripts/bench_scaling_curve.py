#!/usr/bin/env python3
"""Measure an observed solver-scaling curve without extrapolation.

This harness launches one independent HashPipeline per requested solver lane.
Each lane receives a disjoint nonce interval, so duplicate work is prevented by
construction and the aggregate is the sum of measured wall-clock throughput.
It does not claim that a lane is a physical core, board, GPU, or quantum
solver; that mapping must be supplied by the deployment operator.

Examples:
    python scripts/bench_scaling_curve.py --samples 1,2,4 --warmup 2 --duration 5 --json
    python scripts/bench_scaling_curve.py --samples 1,2,4,8,16,32,64,128,256,512,600 \
        --warmup 30 --duration 300 --backend opencl --json --output scaling.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mining.hash_pipeline import HashPipeline  # noqa: E402


DEFAULT_SAMPLES = "1"
MAX_TARGET = b"\xff" * 32
HEADER80 = bytes(80)


def _parse_samples(value: str) -> list[int]:
    samples = [int(part.strip()) for part in value.split(",") if part.strip()]
    if not samples or any(item < 1 for item in samples):
        raise argparse.ArgumentTypeError("samples must be positive integers")
    return sorted(set(samples))


def _run_lane(
    lane: int,
    solver_count: int,
    backend: str,
    nonce_count: int,
    duration: float,
) -> dict[str, Any]:
    # The interval size is deterministic.  For a run with N lanes, lane i
    # starts at i * nonce_count; no lane may intentionally overlap another.
    pipe = HashPipeline(hasher_backend=backend)
    report = pipe.benchmark_hashrate(
        HEADER80,
        MAX_TARGET,
        nonce_count=nonce_count,
        duration_s=duration,
        start_nonce=lane * nonce_count,
    )
    return {
        "lane": lane,
        "solver_count": solver_count,
        **report,
    }


def _measure_once(
    solver_count: int,
    backend: str,
    nonce_count: int,
    warmup: float,
    duration: float,
) -> dict[str, Any]:
    """Run one warm-up plus one timed observation for N lanes."""
    # A Bitcoin header has a 32-bit nonce.  Refuse to wrap intervals: a
    # wrapped lane would silently re-use work and poison the scaling curve.
    if solver_count * nonce_count > (1 << 32):
        raise ValueError(
            "solver_count * nonce_count exceeds the 32-bit nonce space; "
            "reduce --nonce-count or provide distinct job headers"
        )
    # Warm-up is intentionally measured as a separate run and discarded.
    with ThreadPoolExecutor(max_workers=solver_count) as pool:
        warmups = [
            pool.submit(_run_lane, lane, solver_count, backend, nonce_count, warmup)
            for lane in range(solver_count)
        ]
        for future in as_completed(warmups):
            future.result()

        started = time.perf_counter()
        futures = [
            pool.submit(_run_lane, lane, solver_count, backend, nonce_count, duration)
            for lane in range(solver_count)
        ]
        lanes: list[dict[str, Any]] = []
        failures = 0
        for future in as_completed(futures):
            try:
                lanes.append(future.result())
            except Exception as exc:  # report failure; never turn it into H/s
                failures += 1
                lanes.append({"error": type(exc).__name__, "message": str(exc)})
        elapsed = time.perf_counter() - started

    rates = [float(item["measured_hps"]) for item in lanes if "measured_hps" in item]
    hashes = sum(int(item.get("hashes", 0)) for item in lanes)
    dispatch_values = [
        float(item["dispatch_overhead_seconds"])
        for item in lanes
        if item.get("dispatch_overhead_seconds") is not None
    ]
    devices = sorted({str(item.get("device", "unknown")) for item in lanes if "device" in item})
    kernel_configs = [item.get("kernel_config") for item in lanes if item.get("kernel_config") is not None]
    aggregate = sum(rates)
    mean = statistics.fmean(rates) if rates else 0.0
    variance = (statistics.pstdev(rates) / mean) if len(rates) > 1 and mean else 0.0
    return {
        "solver_count": solver_count,
        "backend": backend,
        "warmup_seconds": warmup,
        "duration_seconds": duration,
        "wall_elapsed_seconds": elapsed,
        "lanes_completed": len(rates),
        "lane_failures": failures,
        "raw_sha256d_hps": aggregate,
        "hashes": hashes,
        "solver_hps_min": min(rates) if rates else 0.0,
        "solver_hps_median": statistics.median(rates) if rates else 0.0,
        "solver_hps_max": max(rates) if rates else 0.0,
        "solver_hps_cv": variance,
        "dispatch_overhead_seconds": sum(dispatch_values) if dispatch_values else None,
        "dispatch_overhead_basis": "sum of lane-reported elapsed minus profiled kernel time",
        "temperature_c": None,
        "temperature_status": "sensor_not_exposed_by_active_backend",
        "power_watts": None,
        "power_status": "sensor_not_exposed_by_active_backend",
        "memory_bandwidth_bytes_per_second": None,
        "memory_bandwidth_status": "sensor_not_exposed_by_active_backend",
        "devices": devices,
        "kernel_config": kernel_configs[0] if kernel_configs else None,
        "duplicate_work_pct": 0.0,
        "duplicate_work_basis": "disjoint nonce intervals",
        "validated_hps": None,
        "validated_hps_status": "not_materialized_by_active_hasher",
        "thermal_throttle_events": None,
        "thermal_status": "sensor_not_exposed_by_active_backend",
        "failure_rate": failures / solver_count,
        "effective_ehs": aggregate / 1e18,
        "truth_class": "measured",
    }


def _measure(
    solver_count: int,
    backend: str,
    nonce_count: int,
    warmup: float,
    duration: float,
    repeats: int,
) -> dict[str, Any]:
    """Run the protocol's repeated observations and summarize min/median/max."""
    runs = [
        _measure_once(solver_count, backend, nonce_count, warmup, duration)
        for _ in range(repeats)
    ]
    rates = [float(run["raw_sha256d_hps"]) for run in runs]
    representative = runs[len(runs) // 2] if len(runs) == 1 else min(
        runs, key=lambda run: abs(run["raw_sha256d_hps"] - statistics.median(rates))
    )
    result = dict(representative)
    result.update(
        {
            "repeats": repeats,
            "raw_sha256d_hps_min": min(rates),
            "raw_sha256d_hps_median": statistics.median(rates),
            "raw_sha256d_hps_max": max(rates),
            "runs": runs,
        }
    )
    # Scaling uses the median observed run, not a best-case run.
    result["raw_sha256d_hps"] = statistics.median(rates)
    result["effective_ehs"] = result["raw_sha256d_hps"] / 1e18
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=_parse_samples, default=_parse_samples(DEFAULT_SAMPLES))
    parser.add_argument("--backend", choices=("auto", "opencl", "gpu", "cpu"), default="auto")
    parser.add_argument("--warmup", type=float, default=30.0)
    parser.add_argument("--duration", type=float, default=300.0)
    parser.add_argument("--nonce-count", type=int, default=1 << 20)
    parser.add_argument(
        "--auto-fit-nonce-count", action="store_true",
        help="fit one disjoint interval per requested sample inside uint32 nonce space",
    )
    parser.add_argument("--nonce-headroom", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=3, help="timed observations per sample")
    parser.add_argument("--json", action="store_true", help="emit one JSON document")
    parser.add_argument("--output", type=Path, help="write the JSON document to this path")
    args = parser.parse_args()
    if args.warmup < 0 or args.duration <= 0 or args.nonce_count <= 0 or args.repeats < 1:
        parser.error("warmup >= 0, duration > 0, nonce-count > 0, repeats >= 1 are required")
    if args.nonce_headroom < 0:
        parser.error("nonce-headroom must be >= 0")
    if args.auto_fit_nonce_count:
        capacity = (1 << 32) - args.nonce_headroom
        args.nonce_count = capacity // max(args.samples)
        if args.nonce_count <= 0:
            parser.error("requested samples cannot fit in the uint32 nonce space")

    baseline = None
    points = []
    for count in args.samples:
        point = _measure(count, args.backend, args.nonce_count, args.warmup, args.duration, args.repeats)
        if baseline is None and point["lanes_completed"] == count:
            baseline = point["raw_sha256d_hps"]
        point["scaling_efficiency"] = (
            point["raw_sha256d_hps"] / (count * baseline)
            if baseline and point["lanes_completed"] == count
            else None
        )
        points.append(point)
        if not args.json:
            eta = point["scaling_efficiency"]
            eta_text = "n/a" if eta is None else f"{eta:.4f}"
            print(
                f"N={count:>4} aggregate={point['raw_sha256d_hps']:,.0f} H/s "
                f"eta={eta_text} cv={point['solver_hps_cv']:.4f} "
                f"failures={point['lane_failures']}"
            )

    document = {
        "protocol": "offline-solver-scaling-v1",
        "header80_hex": HEADER80.hex(),
        "target_be_hex": MAX_TARGET.hex(),
        "target_semantics": "offline throughput target; no network calls or submissions",
        "solver_unit": "one independent HashPipeline lane; deployment mapping required",
        "nonce_count_per_lane": args.nonce_count,
        "nonce_space_capacity": 1 << 32,
        "nonce_space_headroom": (1 << 32) - max(args.samples) * args.nonce_count,
        "samples": points,
        "no_extrapolation": True,
        "repeats_per_sample": args.repeats,
        "truth_class": "measured",
    }
    encoded = json.dumps(document, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    if args.json:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
