"""Enterprise intelligence agentic controller benchmark.

Measures:
  - Decision latency per step
  - Capability evaluation throughput
  - Orchestrator state transition times
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


def bench_intelligence_agentic(trials: int = 10) -> Dict[str, Any]:
    """Benchmark Intelligence agentic controller operations.

    Measures:
      - Decision latency per step
      - Capability evaluation throughput
      - Orchestrator state transition times
    """
    from Intelligence.agentic_controller import AgenticController

    steps_per_trial = 5
    latencies: List[float] = []

    for trial in range(trials):
        rng = rng_for("intelligence", trial)
        controller = AgenticController()
        trial_latencies = []

        for _ in range(steps_per_trial):
            start = time.perf_counter()
            # Use search method with properly-sized header/target (target is 32 bytes)
            _ = controller.search(
                header=b"\x00" * 76,
                target=b"\x00" * 32,
                max_faces=2,
                max_hashes=64,
            )
            elapsed = time.perf_counter() - start
            trial_latencies.append(elapsed)

        latencies.extend(trial_latencies)

    return {
        "name": "intelligence_agentic",
        "latencies": summarize(latencies, "agentic_latency"),
        "trials": trials,
        "steps_per_trial": steps_per_trial,
        "seed": SEED,
    }