"""Vogel spatial embedding with non-uniform item sizes.

Items placed by golden-angle Vogel model.
Item sizes drawn from a heavy-tailed distribution.
Devices are Vogel seeds. Assignment by nearest seed.
Compares geometric nearest-seed load against capacity-weighted
on the same size sequence.
"""

from __future__ import annotations

import math
import random
from typing import List, Tuple

PHI = (1 + math.sqrt(5)) / 2
GOLDEN_ANGLE = 2 * math.pi / (PHI ** 2)


def vogel_points(n: int, c: float = 1.0) -> List[Tuple[float, float]]:
    return [
        (c * math.sqrt(i) * math.cos(i * GOLDEN_ANGLE),
         c * math.sqrt(i) * math.sin(i * GOLDEN_ANGLE))
        for i in range(1, n + 1)
    ]


def nearest(point: Tuple[float, float], seeds: List[Tuple[float, float]]) -> int:
    px, py = point
    best, best_d = 0, float("inf")
    for i, (sx, sy) in enumerate(seeds):
        d = (px - sx) ** 2 + (py - sy) ** 2
        if d < best_d:
            best, best_d = i, d
    return best


def load_cv(loads: List[float]) -> float:
    n = len(loads)
    mean = sum(loads) / n
    if mean == 0:
        return 0.0
    var = sum((x - mean) ** 2 for x in loads) / n
    return math.sqrt(var) / mean


def run(n_items: int, n_devices: int, seed: int = 0x9E3779B9) -> dict:
    rng = random.Random(seed)
    # heavy-tailed sizes
    sizes = [rng.paretovariate(1.5) for _ in range(n_items)]
    items = vogel_points(n_items)
    seeds = vogel_points(n_devices, c=math.sqrt(n_items) / math.sqrt(n_devices))
    # geometric nearest
    geo_loads = [0.0] * n_devices
    for p, s in zip(items, sizes):
        geo_loads[nearest(p, seeds)] += s
    # capacity-weighted (least current load)
    cap_loads = [0.0] * n_devices
    for s in sizes:
        d = min(range(n_devices), key=lambda i: cap_loads[i])
        cap_loads[d] += s
    return {
        "n_items": n_items,
        "n_devices": n_devices,
        "geo_cv": load_cv(geo_loads),
        "cap_cv": load_cv(cap_loads),
        "geo_max": max(geo_loads),
        "cap_max": max(cap_loads),
    }


if __name__ == "__main__":
    import json
    results = [run(n, d) for d in (8, 16, 32) for n in (400, 1600, 6400)]
    print(json.dumps(results, indent=2))
