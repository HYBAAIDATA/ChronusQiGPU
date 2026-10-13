"""Golden-angle vs round-robin work distribution across a modelled fleet.

Models N discrete work items assigned to D devices.
Golden-angle assignment: device = floor(i * phi) % D
Round-robin: device = i % D
Measures load balance (coefficient of variation of items per device)
and maximum load.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Dict, List, Tuple

PHI = (1 + math.sqrt(5)) / 2
GOLDEN_ANGLE = 2 * math.pi / (PHI ** 2)


def assign_golden(n_items: int, n_devices: int) -> List[int]:
    return [math.floor(i * PHI) % n_devices for i in range(n_items)]


def assign_round_robin(n_items: int, n_devices: int) -> List[int]:
    return [i % n_devices for i in range(n_items)]


def load_stats(assignment: List[int], n_devices: int) -> Dict[str, float]:
    counts = Counter(assignment)
    loads = [counts.get(d, 0) for d in range(n_devices)]
    mean = sum(loads) / n_devices
    var = sum((x - mean) ** 2 for x in loads) / n_devices
    cv = math.sqrt(var) / mean if mean else 0.0
    return {
        "mean": mean,
        "max": max(loads),
        "min": min(loads),
        "cv": cv,
        "imbalance": max(loads) - min(loads),
    }


def run(n_items: int, n_devices: int) -> Dict[str, object]:
    g = load_stats(assign_golden(n_items, n_devices), n_devices)
    r = load_stats(assign_round_robin(n_items, n_devices), n_devices)
    return {
        "n_items": n_items,
        "n_devices": n_devices,
        "golden": g,
        "round_robin": r,
        "cv_ratio": g["cv"] / r["cv"] if r["cv"] else None,
        "max_load_ratio": g["max"] / r["max"] if r["max"] else None,
    }


if __name__ == "__main__":
    import json
    results = []
    for devices in (8, 16, 32, 64):
        for items in (1000, 10000, 100000):
            results.append(run(items, devices))
    print(json.dumps(results, indent=2))
