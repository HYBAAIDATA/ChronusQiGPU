"""Discontinuity and jump-point detection for emergence phase transitions."""

from __future__ import annotations
import math
from typing import List, Sequence, Tuple, Union, Dict, Any


def detect_discontinuities(
    curve: Sequence[Union[float, Tuple[int, float], Dict[str, float]]],
    threshold_multiplier: float = 2.5,
) -> List[Dict[str, Any]]:
    """Detect sudden nonlinear jump points in emergence rate curves.
    
    Verbatim preservation of step-changes without smoothing into narratives.
    """
    if len(curve) < 2:
        return []

    points: List[Tuple[float, float]] = []
    for idx, item in enumerate(curve):
        if isinstance(item, (int, float)):
            points.append((float(idx), float(item)))
        elif isinstance(item, (tuple, list)) and len(item) >= 2:
            points.append((float(item[0]), float(item[1])))
        elif isinstance(item, dict):
            x = float(item.get("iteration", idx))
            y = float(item.get("rate", item.get("count", 0.0)))
            points.append((x, y))

    diffs = []
    for i in range(1, len(points)):
        dx = points[i][0] - points[i - 1][0]
        dy = points[i][1] - points[i - 1][1]
        rate = dy / dx if dx != 0 else dy
        diffs.append((points[i][0], rate, dy))

    if not diffs:
        return []

    rates = [d[1] for d in diffs]
    mean_rate = sum(rates) / len(rates)
    variance = sum((r - mean_rate) ** 2 for r in rates) / len(rates)
    std_dev = math.sqrt(variance)

    cutoff = mean_rate + threshold_multiplier * max(std_dev, 0.05)

    jump_points = []
    for x_val, rate, raw_dy in diffs:
        if rate > cutoff and rate > 0:
            jump_points.append({
                "iteration": int(x_val),
                "jump_rate": round(rate, 4),
                "delta": round(raw_dy, 4),
                "threshold_exceeded_by": round(rate - cutoff, 4),
            })

    return jump_points
