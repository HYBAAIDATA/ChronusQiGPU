"""Roofline model — ridge point from measured peaks, workloads classified.

Invariants:
    RL1: every workload is classified as memory-bound or compute-bound.
    RL2: the ridge point is peak_compute / peak_bandwidth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Protocol


@dataclass
class RooflinePoint:
    name: str
    intensity: float
    performance: float
    bound: str  # "memory" or "compute"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "intensity": self.intensity,
            "performance": self.performance,
            "bound": self.bound,
        }


@dataclass
class RooflineModel:
    peak_compute_tflops: float
    peak_bandwidth_gbps: float
    ridge_point: float
    points: List[RooflinePoint] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "peak_compute_tflops": self.peak_compute_tflops,
            "peak_bandwidth_gbps": self.peak_bandwidth_gbps,
            "ridge_point": self.ridge_point,
            "points": [p.as_dict() for p in self.points],
        }


class _Workload(Protocol):
    name: str
    flops: int
    bytes_transferred: int


def build_roofline(
    peak_tflops: float,
    peak_bandwidth_gbps: float,
    workloads: List[_Workload],
) -> RooflineModel:
    """Ridge in FLOPs/byte = TFLOPs/s over GB/s (same 1e9/1e12 -> x1000)."""
    if peak_bandwidth_gbps <= 0:
        raise ValueError("roofline needs a positive measured bandwidth")
    ridge = float(peak_tflops) * 1e3 / float(peak_bandwidth_gbps)
    points = []
    for w in workloads:
        intensity = float(w.flops) / float(w.bytes_transferred)
        if intensity < ridge:
            bound = "memory"
            performance = intensity * float(peak_bandwidth_gbps) / 1e3
        else:
            bound = "compute"
            performance = float(peak_tflops)
        points.append(
            RooflinePoint(
                name=w.name,
                intensity=intensity,
                performance=performance,
                bound=bound,
            )
        )
    return RooflineModel(
        peak_compute_tflops=float(peak_tflops),
        peak_bandwidth_gbps=float(peak_bandwidth_gbps),
        ridge_point=ridge,
        points=points,
    )
