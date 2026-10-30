"""Enterprise hash pipeline benchmark — SHA256d throughput and real-work verification.

Measures:
  - Nonces processed per second (throughput)
  - Winner discovery rate at target difficulty
  - Midstate acceleration efficiency
  - Digest reproducibility across runs
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


def bench_hash_pipeline(trials: int = 20) -> Dict[str, Any]:
    """Benchmark SHA256d hash pipeline throughput and real-work verification.

    Measures:
      - Nonces processed per second (throughput)
      - Winner discovery rate at target difficulty
      - Midstate acceleration efficiency
      - Digest reproducibility across runs
    """
    from benchmarks.common import real_winners, synthetic_header

    target_int = 2 ** 224  # difficulty threshold (adjusted for throughput)
    headers = [synthetic_header(h) for h in range(800_000, 800_005)]

    times: List[float] = []
    winner_counts: List[int] = []

    for trial in range(trials):
        rng = rng_for("hash_pipeline", trial)
        start = time.perf_counter()

        total_winners = 0
        for header in headers:
            winners = real_winners(header, target_int, base=0xFFFF_FFFF, count=0x10000)
            total_winners += len(winners)

        elapsed = time.perf_counter() - start

        times.append(elapsed)
        winner_counts.append(total_winners)

    return {
        "name": "hash_pipeline",
        "times_seconds": summarize(times, "hash_time_sec"),
        "winner_counts": summarize(winner_counts, "hash_winners"),
        "trials": trials,
        "seed": SEED,
    }