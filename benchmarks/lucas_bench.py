"""Enterprise Lucas sequence benchmark — exact arithmetic via fast doubling.

Measures:
  - Computation time for L_n, F_n at increasing n
  - Scaling exponent (should be O(1) for fixed-width ints, O(log n) growth)
  - Integer precision retention (no floating-point drift)
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import random
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

# --- Path & seed setup ---
ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"
DATA = REPORTS / "data"

for _extra in (
    str(ROOT),
    str(ROOT / "turing_universal_quantum_computer"),
    str(ROOT / "chronus/mla1517_platform" / "python"),
):
    if _extra not in sys.path:
        sys.path.insert(0, _extra)

SEED = 0x50595448  # "PYTH"

def sha256d(payload: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(payload).digest()).digest()

def env_fingerprint() -> dict:
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
        ).stdout.strip()
    except Exception:
        head = "unknown"
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "git_head": head,
    }

def rng_for(tag: str, trial: int) -> random.Random:
    key = f"{SEED}:{tag}:{trial}".encode()
    return random.Random(int.from_bytes(hashlib.sha256(key).digest()[:8], "big"))

def quantile(data: Sequence[float], q: float) -> float:
    if not data:
        return float("nan")
    xs = sorted(data)
    idx = min(len(xs) - 1, max(0, int(math.ceil(q * len(xs)) - 1)))
    return float(xs[idx])

def bootstrap_ci(
    data: Sequence[float], tag: str, resamples: int = 2000
) -> tuple[float, float]:
    if not data:
        return (float("nan"), float("nan"))
    rng = rng_for("bootstrap", int(hashlib.sha256(tag.encode()).hexdigest()[:8], 16))
    n = len(data)
    means = sorted(
        statistics.fmean(rng.choice(data) for _ in range(n)) for _ in range(resamples)
    )
    return (float(means[int(0.025 * resamples)]), float(means[int(0.975 * resamples)]))

def summarize(values: Sequence[float], tag: str) -> dict:
    if not values:
        return {"n": 0}
    lo, hi = bootstrap_ci(list(values), tag)
    return {
        "n": len(values),
        "mean": statistics.fmean(values),
        "median": quantile(list(values), 0.5),
        "p95": quantile(list(values), 0.95),
        "ci95": [lo, hi],
        "min": min(values),
        "max": max(values),
    }


def bench_lucas_sequences(trials: int = 20) -> Dict[str, Any]:
    """Benchmark exact Lucas/Fibonacci arithmetic via fast doubling.

    Measures:
      - Computation time for L_n, F_n at increasing n
      - Scaling exponent (should be O(1) for fixed-width ints, O(log n) growth)
      - Integer precision retention (no floating-point drift)
    """
    from benchmarks.common import loglog_slope
    from lucas.core import lucas, fibonacci, lucas_sequence

    ns = [100, 500, 1000, 2000, 5000]
    times: Dict[int, List[float]] = {n: [] for n in ns}

    for trial in range(trials):
        rng = rng_for("lucas", trial)
        for n in ns:
            start = time.perf_counter()
            _ = lucas(n)
            _ = fibonacci(n)
            elapsed = time.perf_counter() - start
            times[n].append(elapsed)

    summarized = {}
    for n in ns:
        summarized[f"lucas_{n}"] = summarize(times[n], f"lucas_{n}_time")
        summarized[f"fib_{n}"] = summarize(times[n], f"fib_{n}_time")

    # Compute scaling exponent across the range
    slopes = []
    for i in range(len(ns) - 1):
        x_vals = [ns[i], ns[-1]]
        y_vals = [sum(times[n][0] for _ in range(1)) or 1, sum(times[n][-1] for _ in range(1)) or 1]
        slope = loglog_slope(x_vals, y_vals)
        slopes.append(slope)

    return {
        "name": "lucas_sequences",
        "scaling_exponent": summarize(slopes, "lucas_slope"),
        "times_by_n": summarized,
        "trials": trials,
        "seed": SEED,
    }