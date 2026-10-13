"""Golden-angle vs capacity-weighted assignment on non-uniform fleets.

Devices have heterogeneous capacities. Work items are equal-sized.
Golden assignment: floor(i * phi) % D  (ignores capacity)
Capacity-weighted: assign next item to the device with lowest current load/capacity
Round-robin: i % D
"""

from __future__ import annotations

import math
import random
from typing import Dict, List

PHI = (1 + math.sqrt(5)) / 2


def assign_golden(n_items: int, n_devices: int) -> List[int]:
    return [math.floor(i * PHI) % n_devices for i in range(n_items)]


def assign_round_robin(n_items: int, n_devices: int) -> List[int]:
    return [i % n_devices for i in range(n_items)]


def assign_capacity_weighted(n_items: int, capacities: List[float]) -> List[int]:
    loads = [0.0] * len(capacities)
    assignment = []
    for _ in range(n_items):
        # pick device with lowest load/capacity
        ratios = [loads[d] / capacities[d] for d in range(len(capacities))]
        d = min(range(len(capacities)), key=lambda i: ratios[i])
        loads[d] += 1.0
        assignment.append(d)
    return assignment


def utilisation_stats(assignment: List[int], capacities: List[float]) -> Dict[str, float]:
    counts = [0] * len(capacities)
    for d in assignment:
        counts[d] += 1
    utils = [counts[d] / capacities[d] for d in range(len(capacities))]
    mean = sum(utils) / len(utils)
    var = sum((u - mean) ** 2 for u in utils) / len(utils)
    cv = math.sqrt(var) / mean if mean else 0.0
    return {
        "mean_util": mean,
        "max_util": max(utils),
        "min_util": min(utils),
        "cv": cv,
        "imbalance": max(utils) - min(utils),
    }


def run(n_items: int, capacities: List[float]) -> Dict[str, object]:
    n = len(capacities)
    g = utilisation_stats(assign_golden(n_items, n), capacities)
    r = utilisation_stats(assign_round_robin(n_items, n), capacities)
    w = utilisation_stats(assign_capacity_weighted(n_items, capacities), capacities)
    return {
        "n_items": n_items,
        "capacities": capacities,
        "golden": g,
        "round_robin": r,
        "capacity_weighted": w,
    }


if __name__ == "__main__":
    import json
    random.seed(0x9E3779B9)
    results = []
    # heterogeneous capacities
    for n_devices in (8, 16):
        caps = [random.uniform(0.5, 2.0) for _ in range(n_devices)]
        caps = [c / sum(caps) * n_devices for c in caps]  # normalise mean=1
        for items in (1000, 10000):
            results.append(run(items, caps))
    print(json.dumps(results, indent=2))
