"""Check the GA cold-import budget using an outlier-tolerant statistical gate.

The budget is a performance claim, so the measurement has to survive a busy
machine. Three things make that possible:

* Warmup samples are discarded. The first import pays for the operating
  system's page cache and for the interpreter's own start-up, so it is not
  representative of a cold import.
* The gate is a p95 over many samples, not a median. A median of 11 samples
  ignores the tail entirely, so a gate on the median passes on a machine
  that is intermittently stalling.
* The budget is set above the observed floor with headroom for load.

A gate that fails on a busy machine is worse than a slow one, because it
teaches reviewers to ignore it.
"""

from __future__ import annotations

import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Warmup samples are measured and discarded: they populate the page cache.
WARMUP = 3
# Measured samples. The p95 of these is the gate.
SAMPLES = 21

# Budget on the p95 of the measured samples. The floor is around 240 ms on
# an idle machine; the budget leaves generous headroom for load while still
# catching a regression that adds real work to the import path.
P95_BUDGET_SECONDS = 1.5

# A sample slower than this is a scheduling stall rather than the import
# cost, and is discarded rather than allowed to dominate the percentile.
STALL_SECONDS = 5.0

STATEMENT = "import ga.mathcore, ga.api"


def _run_once(env: dict[str, str]) -> float:
    started = time.perf_counter()
    subprocess.run(
        [sys.executable, "-c", STATEMENT],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return time.perf_counter() - started


def measure_imports() -> tuple[list[float], list[float]]:
    """Return (warmup samples, measured samples) in seconds."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    warmup = [_run_once(env) for _ in range(WARMUP)]
    samples = [_run_once(env) for _ in range(SAMPLES)]
    return warmup, samples


def percentile(samples: list[float], fraction: float) -> float:
    """Return the given percentile of the samples, nearest-rank."""
    if not samples:
        raise ValueError("no samples")
    ordered = sorted(samples)
    index = max(0, min(len(ordered) - 1, round(fraction * (len(ordered) - 1))))
    return ordered[index]


def main() -> int:
    warmup, measured = measure_imports()
    # A sample slower than the stall threshold is the machine, not the import.
    kept = [sample for sample in measured if sample <= STALL_SECONDS]
    discarded = len(measured) - len(kept)
    if not kept:
        print(
            f"GA import measurement unusable: all {len(measured)} samples "
            "exceeded the stall threshold",
            file=sys.stderr,
        )
        return 1

    p95 = percentile(kept, 0.95)
    median = statistics.median(kept)
    formatted = ", ".join(f"{sample * 1000:.1f}" for sample in sorted(measured))
    warm = ", ".join(f"{sample * 1000:.1f}" for sample in sorted(warmup))

    if p95 >= P95_BUDGET_SECONDS:
        print(
            f"GA import regression: p95 {p95 * 1000:.1f} ms exceeds "
            f"{P95_BUDGET_SECONDS * 1000:.0f} ms; "
            f"median {median * 1000:.1f} ms; "
            f"warmup [{warm}]; samples [{formatted}]",
            file=sys.stderr,
        )
        return 1

    note = f"; discarded {discarded} stall sample(s)" if discarded else ""
    print(
        f"import-ok p95={p95 * 1000:.1f}ms median={median * 1000:.1f}ms "
        f"n={len(kept)}{note}; warmup [{warm}]; samples [{formatted}]"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
