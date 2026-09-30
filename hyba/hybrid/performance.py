"""Measured performance accounting for the tensor/GPU/ASIC runtime.

This module deliberately separates physical SHA-256d work from advisory
compute. Floating-point throughput, scheduler scores, folds, projections and
vendor capacity figures never become hashes. A floor can be declared met only
from protocol-valid hashes executed inside a measured wall-clock interval.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Literal

DEFAULT_HASHRATE_FLOOR_HPS = 10_000_000_000_000_000_000.0  # 10 EH/s
LayerName = Literal["tensor", "igpu", "gpu", "asic", "cpu"]


@dataclass(frozen=True)
class LayerSample:
    """One attested measurement from a physical or advisory layer."""

    layer: LayerName
    device_id: str
    elapsed_ns: int
    protocol_hashes: int = 0
    tensor_operations: int = 0
    accepted_shares: int = 0
    source: str = "measured"

    def __post_init__(self) -> None:
        if not self.device_id.strip():
            raise ValueError("device_id must be non-empty")
        if self.elapsed_ns <= 0:
            raise ValueError("elapsed_ns must be > 0")
        for name in ("protocol_hashes", "tensor_operations", "accepted_shares"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be >= 0")
        if self.source != "measured":
            raise ValueError("only measured samples may enter production accounting")
        if self.layer == "tensor" and self.protocol_hashes:
            raise ValueError("tensor advisory work cannot be reported as protocol hashes")

    def as_dict(self) -> Dict[str, Any]:
        return {
            "layer": self.layer,
            "device_id": self.device_id,
            "elapsed_ns": self.elapsed_ns,
            "protocol_hashes": self.protocol_hashes,
            "tensor_operations": self.tensor_operations,
            "accepted_shares": self.accepted_shares,
            "source": self.source,
        }


@dataclass(frozen=True)
class PerformanceReport:
    """Aggregate measured work over one wall-clock observation window."""

    wall_ns: int
    samples: tuple[LayerSample, ...]
    floor_hps: float = DEFAULT_HASHRATE_FLOOR_HPS

    def __post_init__(self) -> None:
        if self.wall_ns <= 0:
            raise ValueError("wall_ns must be > 0")
        if not math.isfinite(self.floor_hps) or self.floor_hps <= 0:
            raise ValueError("floor_hps must be finite and > 0")

    @classmethod
    def from_samples(
        cls,
        wall_ns: int,
        samples: Iterable[LayerSample],
        *,
        floor_hps: float = DEFAULT_HASHRATE_FLOOR_HPS,
    ) -> "PerformanceReport":
        return cls(int(wall_ns), tuple(samples), float(floor_hps))

    @property
    def protocol_hashes(self) -> int:
        return sum(sample.protocol_hashes for sample in self.samples)

    @property
    def tensor_operations(self) -> int:
        return sum(sample.tensor_operations for sample in self.samples)

    @property
    def accepted_shares(self) -> int:
        return sum(sample.accepted_shares for sample in self.samples)

    @property
    def measured_hashrate_hps(self) -> float:
        return self.protocol_hashes * 1_000_000_000.0 / self.wall_ns

    @property
    def measured_tensor_tflops(self) -> float:
        return self.tensor_operations * 1_000_000_000.0 / self.wall_ns / 1_000_000_000_000.0

    @property
    def floor_met(self) -> bool:
        return self.measured_hashrate_hps >= self.floor_hps

    def by_layer(self) -> Dict[str, Dict[str, int]]:
        out: Dict[str, Dict[str, int]] = {}
        for sample in self.samples:
            row = out.setdefault(
                sample.layer,
                {"protocol_hashes": 0, "tensor_operations": 0, "accepted_shares": 0},
            )
            row["protocol_hashes"] += sample.protocol_hashes
            row["tensor_operations"] += sample.tensor_operations
            row["accepted_shares"] += sample.accepted_shares
        return out

    def as_dict(self) -> Dict[str, Any]:
        return {
            "truth_class": "measured",
            "wall_ns": self.wall_ns,
            "protocol_hashes": self.protocol_hashes,
            "measured_hashrate_hps": self.measured_hashrate_hps,
            "tensor_operations": self.tensor_operations,
            "measured_tensor_tflops": self.measured_tensor_tflops,
            "accepted_shares": self.accepted_shares,
            "floor_hps": self.floor_hps,
            "floor_met": self.floor_met,
            "by_layer": self.by_layer(),
            "samples": [sample.as_dict() for sample in self.samples],
        }


def job_performance_report(
    *,
    wall_ns: int,
    protocol_hashes: int,
    accepted_shares: int,
    device_id: str = "hybrid-job",
) -> PerformanceReport:
    """Build the canonical job-level report used by ``HybridCoordinator``."""
    return PerformanceReport.from_samples(
        wall_ns,
        (
            LayerSample(
                layer="gpu",
                device_id=device_id,
                elapsed_ns=wall_ns,
                protocol_hashes=protocol_hashes,
                accepted_shares=accepted_shares,
            ),
        ),
    )


__all__ = [
    "DEFAULT_HASHRATE_FLOOR_HPS",
    "LayerSample",
    "PerformanceReport",
    "job_performance_report",
]
