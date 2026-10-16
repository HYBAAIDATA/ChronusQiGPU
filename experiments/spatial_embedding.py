"""Spatial embedding of golden-angle placement.

Places work items as points in the plane using the Vogel model
(angle = i * golden_angle, radius = c * sqrt(i)).
Devices are Voronoi seeds. Measures load balance when items are
assigned to the nearest device seed.
"""

from __future__ import annotations

import math
from typing import List, Tuple

PHI = (1 + math.sqrt(5)) / 2
GOLDEN_ANGLE = 2 * math.pi / (PHI ** 2)


def vogel_points(n: int, c: float = 1.0) -> List[Tuple[float, float]]:
    pts = []
    for i in range(1, n + 1):
        r = c * math.sqrt(i)
        theta = i * GOLDEN_ANGLE
        pts.append((r * math.cos(theta), r * math.sin(theta)))
    return pts


def device_seeds(n_devices: int, radius: float) -> List[Tuple[float, float]]:
    # Place device seeds on a circle, or as a smaller Vogel set
    return vogel_points(n_devices, c=radius / math.sqrt(n_devices))


def nearest(point: Tuple[float, float], seeds: List[Tuple[float, float]]) -> int:
    px, py = point
    best, best_d = 0, float("inf")
    for i, (sx, sy) in enumerate(seeds):
        d = (px - sx) ** 2 + (py - sy) ** 2
        if d < best_d:
            best, best_d = i, d
    return best


def load_cv(assignment: List[int], n_devices: int) -> float:
    counts = [0] * n_devices
    for d in assignment:
        counts[d] += 1
    mean = sum(counts) / n_devices
    if mean == 0:
        return 0.0
    var = sum((c - mean) ** 2 for c in counts) / n_devices
    return math.sqrt(var) / mean


def run(n_items: int, n_devices: int) -> dict:
    items = vogel_points(n_items)
    seeds = device_seeds(n_devices, radius=math.sqrt(n_items))
    assignment = [nearest(p, seeds) for p in items]
    return {
        "n_items": n_items,
        "n_devices": n_devices,
        "cv": load_cv(assignment, n_devices),
        "max_load": max(assignment.count(d) for d in range(n_devices)),
        "min_load": min(assignment.count(d) for d in range(n_devices)),
    }


if __name__ == "__main__":
    import json
    results = [run(n, d) for d in (8, 16, 32) for n in (400, 1600, 6400)]
    print(json.dumps(results, indent=2))
