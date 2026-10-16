"""Criticality and power-law analysis for agent decision telemetry."""

from __future__ import annotations
import math
from typing import Sequence, Dict, Any, List
from ..models.telemetry import TelemetryRecord


def compute_burst_avalanches(telemetry_records: Sequence[TelemetryRecord]) -> List[int]:
    avalanches: List[int] = []
    current_burst = 0

    for rec in telemetry_records:
        novel_count = len(rec.novel_elements.unattributed)
        if novel_count > 0:
            current_burst += novel_count
        else:
            if current_burst > 0:
                avalanches.append(current_burst)
                current_burst = 0

    if current_burst > 0:
        avalanches.append(current_burst)

    return avalanches


def criticality_indicators(telemetry_records: Sequence[TelemetryRecord]) -> Dict[str, Any]:
    avalanches = compute_burst_avalanches(telemetry_records)
    if len(avalanches) < 4:
        return {
            "has_criticality_signature": False,
            "avalanche_count": len(avalanches),
            "power_law_alpha": None,
            "power_law_fit": 0.0,
            "branching_ratio": None,
            "ks_statistic": None,
            "note": "Insufficient avalanche data for criticality evaluation",
        }

    x_min = max(1, min(avalanches))
    n = len(avalanches)
    log_sum = sum(math.log(x / (x_min - 0.5 if x_min > 0.5 else 0.5)) for x in avalanches)
    alpha = 1.0 + n / log_sum if log_sum > 0 else 1.0

    ratios = []
    for i in range(len(avalanches) - 1):
        if avalanches[i] > 0:
            ratios.append(avalanches[i + 1] / avalanches[i])
    branching_ratio = sum(ratios) / len(ratios) if ratios else 1.0

    sorted_av = sorted(avalanches)
    max_ks = 0.0
    for i, x in enumerate(sorted_av):
        empirical_cdf = (i + 1) / n
        theo_cdf = 1.0 - math.pow(x / x_min, -(alpha - 1.0)) if alpha > 1.0 else 0.0
        diff = abs(empirical_cdf - theo_cdf)
        if diff > max_ks:
            max_ks = diff

    power_law_fit = max(0.0, round(1.0 - max_ks, 4))
    is_critical = (1.2 <= alpha <= 2.8) and (0.75 <= branching_ratio <= 1.25) and (max_ks < 0.35)

    return {
        "has_criticality_signature": is_critical,
        "avalanche_count": n,
        "power_law_alpha": round(alpha, 4),
        "power_law_fit": power_law_fit,
        "branching_ratio": round(branching_ratio, 4),
        "ks_statistic": round(max_ks, 4),
        "critical_regime": "critical" if is_critical else ("subcritical" if branching_ratio < 0.75 else "supercritical"),
    }
