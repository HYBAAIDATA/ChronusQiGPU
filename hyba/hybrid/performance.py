"""Measured performance accounting for tensor, GPU and ASIC execution.

Only protocol-valid SHA-256d work enters H/s. Advisory operations retain their
own units. Reports are content-addressed and the floor is an explicit promotion
gate, never a multiplier or a pre-dispatch estimate.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Literal, Optional

DEFAULT_HASHRATE_FLOOR_HPS = 10_000_000_000_000_000_000.0
LayerName = Literal["tensor", "chronus", "gpu", "asic", "cpu", "hybrid"]


class HashrateFloorViolation(RuntimeError):
    """Raised when measured physical work does not satisfy a required floor."""


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class LayerSample:
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

    @property
    def measured_hashrate_hps(self) -> float:
        return self.protocol_hashes * 1_000_000_000.0 / self.elapsed_ns

    def as_dict(self) -> Dict[str, Any]:
        row = {
            "layer": self.layer,
            "device_id": self.device_id,
            "elapsed_ns": self.elapsed_ns,
            "protocol_hashes": self.protocol_hashes,
            "tensor_operations": self.tensor_operations,
            "accepted_shares": self.accepted_shares,
            "source": self.source,
            "measured_hashrate_hps": self.measured_hashrate_hps,
        }
        row["evidence_digest"] = _digest(row)
        return row


@dataclass(frozen=True)
class PerformanceReport:
    wall_ns: int
    samples: tuple[LayerSample, ...]
    floor_hps: float = DEFAULT_HASHRATE_FLOOR_HPS

    def __post_init__(self) -> None:
        if self.wall_ns <= 0:
            raise ValueError("wall_ns must be > 0")
        if not math.isfinite(self.floor_hps) or self.floor_hps <= 0:
            raise ValueError("floor_hps must be finite and > 0")
        if any(sample.elapsed_ns > self.wall_ns for sample in self.samples):
            raise ValueError("sample elapsed_ns cannot exceed the report observation window")

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
        return self.tensor_operations * 1_000_000_000.0 / self.wall_ns / 1e12

    @property
    def floor_met(self) -> bool:
        return self.measured_hashrate_hps >= self.floor_hps

    def by_layer(self) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for sample in self.samples:
            row = out.setdefault(sample.layer, {
                "protocol_hashes": 0,
                "tensor_operations": 0,
                "accepted_shares": 0,
                "devices": [],
            })
            row["protocol_hashes"] += sample.protocol_hashes
            row["tensor_operations"] += sample.tensor_operations
            row["accepted_shares"] += sample.accepted_shares
            row["devices"].append(sample.device_id)
        for row in out.values():
            row["devices"] = sorted(set(row["devices"]))
            row["observation_wall_ns"] = self.wall_ns
            row["measured_hashrate_hps"] = (
                row["protocol_hashes"] * 1_000_000_000.0 / self.wall_ns
            )
        return out

    def as_dict(self) -> Dict[str, Any]:
        row = {
            "truth_class": "measured",
            "observation_semantics": "concurrent_wall_window",
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
        row["evidence_digest"] = _digest(row)
        return row


def enforce_floor(report: PerformanceReport) -> PerformanceReport:
    """Fail closed at an explicit release/promotion boundary."""
    if not report.floor_met:
        raise HashrateFloorViolation(
            f"measured {report.measured_hashrate_hps:.6g} H/s is below "
            f"required {report.floor_hps:.6g} H/s"
        )
    return report


def job_performance_report(
    *,
    wall_ns: int,
    protocol_hashes: int = 0,
    accepted_shares: int = 0,
    device_id: str = "hybrid-job",
    samples: Optional[Iterable[LayerSample]] = None,
) -> PerformanceReport:
    if samples is not None:
        return PerformanceReport.from_samples(wall_ns, samples)
    return PerformanceReport.from_samples(wall_ns, (
        LayerSample("hybrid", device_id, wall_ns, protocol_hashes, 0, accepted_shares),
    ))


__all__ = [
    "DEFAULT_HASHRATE_FLOOR_HPS", "HashrateFloorViolation", "LayerSample",
    "PerformanceReport", "enforce_floor", "job_performance_report",
]
