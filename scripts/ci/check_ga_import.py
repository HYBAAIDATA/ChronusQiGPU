"""Check the GA cold-import budget using an outlier-tolerant statistical gate."""

from __future__ import annotations

import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = 11
MEDIAN_BUDGET_SECONDS = 0.5
SECOND_WORST_BUDGET_SECONDS = 0.75
STATEMENT = "import ga.mathcore, ga.api"


def measure_imports() -> list[float]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    samples = []
    for _ in range(SAMPLES):
        started = time.perf_counter()
        subprocess.run(
            [sys.executable, "-c", STATEMENT],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        samples.append(time.perf_counter() - started)
    return samples


def main() -> int:
    samples = sorted(measure_imports())
    median = statistics.median(samples)
    second_worst = samples[-2]
    formatted = ", ".join(f"{sample * 1000:.1f}" for sample in samples)
    failures = []
    if median >= MEDIAN_BUDGET_SECONDS:
        failures.append(
            f"median {median * 1000:.1f} ms exceeds "
            f"{MEDIAN_BUDGET_SECONDS * 1000:.0f} ms"
        )
    if second_worst >= SECOND_WORST_BUDGET_SECONDS:
        failures.append(
            f"second-worst {second_worst * 1000:.1f} ms exceeds "
            f"{SECOND_WORST_BUDGET_SECONDS * 1000:.0f} ms"
        )
    if failures:
        print(
            f"GA import regression ({'; '.join(failures)}); samples: [{formatted}]",
            file=sys.stderr,
        )
        return 1
    print(
        f"import-ok median={median * 1000:.1f}ms "
        f"second-worst={second_worst * 1000:.1f}ms samples=[{formatted}]"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
