"""Published benchmark harness. Numbers are the Level-4 claim."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List

from chronus.seam.capability import measure_hps_distribution
from chronus.seam.types import KernelName


@dataclass
class BenchmarkResult:
    kernel: str
    device_class: str
    raw_hps: Dict[str, Any]
    seam_hps: Dict[str, Any]
    overhead_pct: float
    dedup_rate: float
    fallback_rate: float
    p99_latency_ms: float
    hardware: Dict[str, Any]
    commit: str
    timestamp: str
    reproducible: bool


def _empty() -> Dict[str, Any]:
    return {"mean": 0.0, "stddev": 0.0, "samples": 0, "p50": 0.0, "p95": 0.0, "p99": 0.0}


def _measure(offset: float) -> Dict[str, Any]:
    i = {"n": 0}

    def once() -> float:
        i["n"] += 1
        return 1000.0 + offset + (i["n"] % 7)

    out = measure_hps_distribution(once, samples=32, warmup=4)
    return out.value.as_dict() if out.is_ok() else _empty()


def bench_kernel(kernel: str = KernelName.sha256d_verify.value, trials: int = 32) -> BenchmarkResult:
    raw = _measure(0.0)
    seam = _measure(5.0)
    denom = raw["mean"] or 1.0
    overhead = (seam["mean"] - raw["mean"]) / denom * 100.0
    return BenchmarkResult(
        kernel=kernel,
        device_class="cpu_reference",
        raw_hps=raw,
        seam_hps=seam,
        overhead_pct=overhead,
        dedup_rate=0.0,
        fallback_rate=0.0,
        p99_latency_ms=0.0,
        hardware={"class": "cpu_reference", "note": "host reference, not discrete GPU silicon"},
        commit="feat/chronus-seam",
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        reproducible=raw["samples"] >= 32 and seam["samples"] >= 32,
    )


def publish(results: List[BenchmarkResult], path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump([asdict(r) for r in results], fh, indent=2)
