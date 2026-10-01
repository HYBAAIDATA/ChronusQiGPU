"""Run-to-run variance — the same real measurement repeated.

Invariants:
    REG1: the regression runs the measurement multiple times.
    REG2: the variance is reported.
"""

from __future__ import annotations

import statistics
from typing import Any, Callable, Dict


def run_regression(
    measure_fn: Callable[[], float],
    runs: int = 5,
) -> Dict[str, Any]:
    """Run ``measure_fn`` ``runs`` times; report mean/stddev/CV of the means."""
    means = [float(measure_fn()) for _ in range(max(2, runs))]
    mean_of_means = statistics.fmean(means)
    std = statistics.pstdev(means) if len(means) > 1 else 0.0
    return {
        "runs": len(means),
        "means": means,
        "mean_of_means": mean_of_means,
        "stddev_of_means": std,
        "coefficient_of_variation": (std / mean_of_means) if mean_of_means else 0.0,
    }
