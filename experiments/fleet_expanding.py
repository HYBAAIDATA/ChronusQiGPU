"""Expanding-fleet packing test.

Work items arrive sequentially. Devices are added at Lucas rungs.
Golden-angle assignment places each new item at angle i * golden_angle.
Capacity-weighted places each item on the least-loaded device.
Measures utilisation CV as the fleet grows.
"""

from __future__ import annotations

import math
from typing import Dict, List

PHI = (1 + math.sqrt(5)) / 2
GOLDEN_ANGLE = 2 * math.pi / (PHI ** 2)


def golden_device(i: int, n_devices: int) -> int:
    # Map golden angle to device index via fractional part
    frac = (i * PHI) % 1.0
    return int(frac * n_devices)


def run_expanding(max_items: int, device_schedule: List[int]) -> Dict[str, object]:
    """device_schedule[k] = number of devices after item k is added (or at step)."""
    results = []
    loads_g = []
    loads_w = []
    n_dev = 0
    for i in range(max_items):
        if i < len(device_schedule):
            n_dev = device_schedule[i]
        if n_dev == 0:
            continue
        # grow load arrays
        while len(loads_g) < n_dev:
            loads_g.append(0)
            loads_w.append(0)
        # golden
        d_g = golden_device(i, n_dev)
        loads_g[d_g] += 1
        # capacity-weighted (least loaded)
        d_w = min(range(n_dev), key=lambda d: loads_w[d])
        loads_w[d_w] += 1
        if (i + 1) % 500 == 0 or i == max_items - 1:
            def cv(loads, n):
                active = loads[:n]
                mean = sum(active) / n
                if mean == 0:
                    return 0.0
                var = sum((x - mean) ** 2 for x in active) / n
                return math.sqrt(var) / mean
            results.append({
                "items": i + 1,
                "devices": n_dev,
                "golden_cv": cv(loads_g, n_dev),
                "weighted_cv": cv(loads_w, n_dev),
            })
    return {"trace": results}


if __name__ == "__main__":
    import json
    # grow devices at Lucas-ish intervals
    schedule = []
    n = 1
    for i in range(5000):
        if i in (0, 100, 300, 800, 2000, 4000):
            n = min(n * 2, 64)
        schedule.append(n)
    out = run_expanding(5000, schedule)
    print(json.dumps(out, indent=2))
