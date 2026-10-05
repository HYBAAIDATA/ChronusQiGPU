# protocol.py
# Chronos GPU -- reproducible benchmark protocol (5 Oct 2026)
#
# The elevation doctrine is "elevate the code to meet the documents, never
# water the documents down." A claim is only as strong as the run that
# produced it, so every benchmark artifact follows one protocol:
#
#   1. Full environment capture -- host platform, Python, NumPy, CPU count,
#      thread environment, UTC timestamp, optional operator host label.
#   2. Real workloads -- full QSDL scenes through the real pipeline
#      (manifold -> Hamiltonian -> evolution -> ray-traced reconstruction),
#      never micro-benchmarks standing in for the documented envelope.
#   3. Repetition statistics -- wall times report every sample plus
#      median/mean/stdev/min/max. A single sample may be requested and is
#      then labelled as such; it is never presented as a distribution.
#   4. Fail-closed measurement -- a run that cannot produce a finite number
#      records ``measured: false`` with the reason. NaN never masquerades as
#      evidence (the phi^18/phi^20 rule).
#   5. Versioned schema -- every artifact carries ``schema`` and
#      ``protocol_version`` so future agents can reconcile old artifacts
#      without re-deriving their semantics.

from __future__ import annotations

import json
import math
import os
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

import numpy as np

PROTOCOL_VERSION = "1.0.0"
SCHEMA_NAME = "chronos-v33-benchmarks-v2"


def capture_environment(host_label: Optional[str] = None) -> Dict[str, Any]:
    """Capture everything that materially affects wall-time reproducibility."""
    env: Dict[str, Any] = {
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "cpu_count": os.cpu_count(),
        "utc_timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "protocol_version": PROTOCOL_VERSION,
    }
    thread_vars = [
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "CHRONUS_V33_RENDER_BACKEND",
    ]
    env["thread_environment"] = {name: os.environ.get(name) for name in thread_vars}
    label = host_label or os.environ.get("CHRONUS_BENCH_HOST_LABEL")
    if label:
        env["host_label"] = label
    return env


def _finite(value: float) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def nan_guard(value: Any, reason_if_nan: str = "value is not finite") -> Dict[str, Any]:
    """The phi^18 rule: NaN is a fail-closed state, not evidence."""
    try:
        finite = math.isfinite(float(value))
    except (TypeError, ValueError):
        finite = False
    if finite:
        return {"value": float(value), "measured": True, "reason": ""}
    return {"value": None, "measured": False, "reason": reason_if_nan}


def measure(
    fn: Callable[[], Any],
    *,
    repetitions: int = 1,
    warmup: int = 0,
) -> Dict[str, Any]:
    """Run ``fn`` and return repetition statistics with all samples kept.

    ``repetitions: 1`` is labelled single_sample; it is honest but it is not
    a distribution and never reported as one.
    """
    repetitions = max(1, int(repetitions))
    for _ in range(max(0, int(warmup))):
        fn()
    samples: List[float] = []
    result: Any = None
    for _ in range(repetitions):
        t0 = time.perf_counter()
        result = fn()
        samples.append(time.perf_counter() - t0)
    if not all(_finite(s) for s in samples):
        return {
            "measured": False,
            "reason": "non-finite wall-time sample",
            "samples_seconds": [None if not _finite(s) else s for s in samples],
            "repetitions": repetitions,
        }
    out: Dict[str, Any] = {
        "measured": True,
        "repetitions": repetitions,
        "single_sample": repetitions == 1,
        "samples_seconds": [round(s, 6) for s in samples],
        "median_seconds": round(statistics.median(samples), 6),
        "mean_seconds": round(statistics.fmean(samples), 6),
        "min_seconds": round(min(samples), 6),
        "max_seconds": round(max(samples), 6),
    }
    if repetitions >= 2:
        out["stdev_seconds"] = round(statistics.stdev(samples), 6)
    return out


def envelope(
    environment: Optional[Dict[str, Any]] = None,
    sections: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Standard artifact envelope: schema, environment, then measurements."""
    return {
        "schema": SCHEMA_NAME,
        "protocol_version": PROTOCOL_VERSION,
        "environment": environment or capture_environment(),
        **(sections or {}),
    }


def write_artifact(payload: Dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str))
    return path


__all__ = [
    "PROTOCOL_VERSION",
    "SCHEMA_NAME",
    "capture_environment",
    "measure",
    "nan_guard",
    "envelope",
    "write_artifact",
]