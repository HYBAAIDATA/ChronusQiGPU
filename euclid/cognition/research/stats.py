"""Statistics for the research programme (no third-party dependencies).

* :func:`t_interval` — mean with a two-sided 95% Student-t interval across
  independent seeds (the unit of replication);
* :func:`paired_bootstrap` — percentile bootstrap of a mean paired difference
  (tasks paired by identity and seed), seeded for reproducibility;
* :func:`wilson` — Wilson score interval for a proportion;
* :func:`brier`, :func:`expected_calibration_error`, :func:`reliability_bins`.
"""
from __future__ import annotations

import math
import random
import statistics
from typing import Sequence

# two-sided 97.5% quantiles of Student's t for df = 1..30 (then normal)
_T975 = [12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228,
         2.201, 2.179, 2.160, 2.145, 2.131, 2.120, 2.110, 2.101, 2.093, 2.086,
         2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042]


def t_quantile(df: int) -> float:
    if df < 1:
        return float("nan")
    return _T975[df - 1] if df <= len(_T975) else 1.96


def t_interval(values: Sequence[float]) -> dict[str, float | int | None]:
    values = [float(v) for v in values if v is not None]
    if not values:
        return {"mean": None, "low95": None, "high95": None, "sd": None, "n": 0}
    mean = statistics.fmean(values)
    if len(values) < 2:
        return {"mean": mean, "low95": None, "high95": None, "sd": None, "n": 1}
    sd = statistics.stdev(values)
    half = t_quantile(len(values) - 1) * sd / math.sqrt(len(values))
    return {"mean": mean, "low95": mean - half, "high95": mean + half, "sd": sd,
            "n": len(values)}


def paired_bootstrap(
    a: Sequence[float], b: Sequence[float], *, resamples: int = 4000, seed: int = 0
) -> dict[str, float | int | bool | None]:
    """Mean of ``a - b`` with a 95% percentile bootstrap interval."""
    if len(a) != len(b):
        raise ValueError("paired samples must align")
    diffs = [float(x) - float(y) for x, y in zip(a, b)]
    if not diffs:
        return {"mean_diff": None, "low95": None, "high95": None, "n": 0,
                "excludes_zero": False}
    rng = random.Random(seed)
    n = len(diffs)
    means = []
    for _ in range(resamples):
        means.append(sum(diffs[rng.randrange(n)] for _ in range(n)) / n)
    means.sort()
    low = means[int(0.025 * resamples)]
    high = means[min(resamples - 1, int(0.975 * resamples))]
    return {"mean_diff": sum(diffs) / n, "low95": low, "high95": high, "n": n,
            "excludes_zero": low > 0.0 or high < 0.0}


def wilson(successes: int, trials: int) -> dict[str, float | int | None]:
    if trials <= 0:
        return {"rate": None, "low95": None, "high95": None, "n": 0}
    z = 1.96
    p = successes / trials
    denom = 1 + z * z / trials
    centre = (p + z * z / (2 * trials)) / denom
    half = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denom
    return {"rate": p, "low95": centre - half, "high95": centre + half, "n": trials}


def brier(pairs: Sequence[tuple[float, int]]) -> float | None:
    if not pairs:
        return None
    return sum((p - y) ** 2 for p, y in pairs) / len(pairs)


def reliability_bins(pairs: Sequence[tuple[float, int]], bins: int = 10) -> list[dict]:
    rows = []
    for index in range(bins):
        lo, hi = index / bins, (index + 1) / bins
        members = [(p, y) for p, y in pairs if lo <= p < hi or (index == bins - 1 and p == 1.0)]
        if not members:
            continue
        rows.append({"bin": [round(lo, 2), round(hi, 2)], "n": len(members),
                     "mean_predicted": sum(p for p, _ in members) / len(members),
                     "observed_rate": sum(y for _, y in members) / len(members)})
    return rows


def expected_calibration_error(pairs: Sequence[tuple[float, int]], bins: int = 10) -> float | None:
    if not pairs:
        return None
    total = len(pairs)
    return sum(
        row["n"] / total * abs(row["mean_predicted"] - row["observed_rate"])
        for row in reliability_bins(pairs, bins)
    )


__all__ = [
    "brier",
    "expected_calibration_error",
    "paired_bootstrap",
    "reliability_bins",
    "t_interval",
    "t_quantile",
    "wilson",
]
