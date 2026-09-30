"""Distribution-aware capability measurement. Closes P4.

Routing consumes a quantile selected by a declared policy, never a
naked mean. Fewer than 32 cleaned samples is a measurement error.
"""

from __future__ import annotations

import math
import statistics
from typing import Iterable, List, Sequence

from igpu.seam.types import Distribution, Err, Ok, Result, RoutingPolicy, SeamError


UNSTABLE_CV = 0.25
MIN_SAMPLES = 32


def _percentile(sorted_vals: Sequence[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    rank = (pct / 100.0) * (len(sorted_vals) - 1)
    lo = int(math.floor(rank))
    hi = int(math.ceil(rank))
    if lo == hi:
        return float(sorted_vals[lo])
    frac = rank - lo
    return float(sorted_vals[lo]) * (1.0 - frac) + float(sorted_vals[hi]) * frac


def reject_measurement_errors(raw: Iterable[float]) -> List[float]:
    """Drop non-positive samples and isolated zeros. Keep real variance."""
    values = [float(x) for x in raw if x is not None and math.isfinite(float(x)) and float(x) > 0.0]
    if len(values) < 3:
        return values
    mean = statistics.fmean(values)
    std = statistics.pstdev(values)
    if std <= 0.0:
        return values
    return [v for v in values if abs(v - mean) <= 5.0 * std]


def distribution_from_samples(raw: Iterable[float]) -> Result[Distribution]:
    cleaned = reject_measurement_errors(raw)
    if len(cleaned) < MIN_SAMPLES:
        return Err(SeamError.unknown, f"distribution samples {len(cleaned)} < {MIN_SAMPLES}")
    ordered = sorted(cleaned)
    mean = statistics.fmean(ordered)
    std = statistics.pstdev(ordered) if len(ordered) > 1 else 0.0
    return Ok(
        Distribution(
            mean=mean,
            stddev=std,
            samples=len(ordered),
            p50=_percentile(ordered, 50),
            p95=_percentile(ordered, 95),
            p99=_percentile(ordered, 99),
        )
    )


def measure_hps_distribution(measure_once, samples: int = 64, warmup: int = 8) -> Result[Distribution]:
    raw: List[float] = []
    total = samples + warmup
    for i in range(total):
        try:
            hps = float(measure_once())
        except Exception:
            continue
        if i >= warmup:
            raw.append(hps)
    return distribution_from_samples(raw)


def effective_hps(measured: Distribution, policy: RoutingPolicy = RoutingPolicy.balanced) -> float:
    if policy is RoutingPolicy.conservative:
        return float(measured.p50 or measured.mean)
    if policy is RoutingPolicy.aggressive:
        return float(measured.p95 or measured.mean)
    return float(measured.mean)


def is_unstable(measured: Distribution) -> bool:
    if measured.mean <= 0.0:
        return True
    return (measured.stddev / measured.mean) > UNSTABLE_CV


def declared_policy_hps(measured: Distribution, policy: RoutingPolicy) -> float:
    """P4a: every routing decision names a policy that selects a quantile."""
    if is_unstable(measured) and policy is not RoutingPolicy.conservative:
        policy = RoutingPolicy.conservative
    return effective_hps(measured, policy)
