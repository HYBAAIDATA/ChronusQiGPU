"""Energy per operation — derived only from measured power and measured work.

Invariants:
    EN1: energy per op is watts × seconds / ops, all measured.
    EN2: when power is unavailable, energy is unavailable — never back-filled.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .power import PowerMeasurement


@dataclass
class EnergyMeasurement:
    joules_per_hash: Optional[float]
    joules_per_flop: Optional[float]
    available: bool
    method: str
    reason: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "joules_per_hash": self.joules_per_hash,
            "joules_per_flop": self.joules_per_flop,
            "available": self.available,
            "method": self.method,
            "reason": self.reason,
        }


def measure_energy(
    power: PowerMeasurement,
    hps_mean: Optional[float] = None,
    gflops_mean: Optional[float] = None,
) -> EnergyMeasurement:
    """Combine measured watts with measured rates; honest when power is absent."""
    if not power.available or power.watts is None or power.watts.mean <= 0:
        return EnergyMeasurement(
            joules_per_hash=None,
            joules_per_flop=None,
            available=False,
            method="requires_measured_power",
            reason=power.reason or "power unavailable",
        )
    watts = power.watts.mean
    j_per_hash = watts / hps_mean if hps_mean and hps_mean > 0 else None
    j_per_flop = watts / (gflops_mean * 1e9) if gflops_mean and gflops_mean > 0 else None
    return EnergyMeasurement(
        joules_per_hash=j_per_hash,
        joules_per_flop=j_per_flop,
        available=j_per_hash is not None or j_per_flop is not None,
        method=f"measured_watts({power.method})/measured_rate",
    )
