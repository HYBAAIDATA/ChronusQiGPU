"""Performance per watt — quotient of two measurements, never a guess.

Invariants:
    PPW1: perf/watt is computed from measured performance and measured power.
    PPW2: the method is declared; unavailable when power is unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ...seam.types import Distribution
from ..workload.hashrate import HashrateMeasurement
from ..workload.tensor import TensorMeasurement
from .power import PowerMeasurement


@dataclass
class PerfPerWatt:
    hps_per_watt: Optional[Distribution]
    gflops_per_watt: Optional[Distribution]
    method: str
    available: bool
    reason: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "hps_per_watt": self.hps_per_watt.as_dict() if self.hps_per_watt else None,
            "gflops_per_watt": self.gflops_per_watt.as_dict() if self.gflops_per_watt else None,
            "method": self.method,
            "available": self.available,
            "reason": self.reason,
        }


def _ratio(num: Distribution, den: Distribution) -> Distribution:
    return Distribution(
        mean=num.mean / den.mean,
        stddev=0.0,
        samples=min(num.samples, den.samples),
        p50=num.p50 / den.p50,
        p95=num.p95 / den.p95,
        p99=num.p99 / den.p99,
    )


def compute_perf_per_watt(
    hashrate: Optional[HashrateMeasurement],
    tensor: Optional[TensorMeasurement],
    power: PowerMeasurement,
) -> PerfPerWatt:
    """Quotient of measured throughput and measured watts."""
    if not power.available or power.watts is None or power.watts.mean <= 0:
        return PerfPerWatt(
            hps_per_watt=None,
            gflops_per_watt=None,
            method="requires_measured_power",
            available=False,
            reason=power.reason or "power unavailable",
        )
    hps_pw = _ratio(hashrate.hps, power.watts) if hashrate is not None else None
    gf_pw = _ratio(tensor.gflops, power.watts) if tensor is not None else None
    return PerfPerWatt(
        hps_per_watt=hps_pw,
        gflops_per_watt=gf_pw,
        method=f"measured_rate/measured_watts({power.method})",
        available=hps_pw is not None or gf_pw is not None,
    )
