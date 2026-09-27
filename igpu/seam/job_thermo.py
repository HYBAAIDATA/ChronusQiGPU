"""T6 / F6 / F7 — job thermodynamic summary and reversible preference."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from igpu.seam.signatures import signature_of
from igpu.seam.thermodynamics import Technology, ThermoPolicy, measure_thermodynamic
from igpu.seam.types import KernelName


@dataclass(frozen=True)
class JobThermoSummary:
    total_energy: float
    total_landauer: float
    reversible_fraction: float
    technology: str

    def as_dict(self) -> dict:
        return {
            "total_energy": self.total_energy,
            "total_landauer": self.total_landauer,
            "reversible_fraction": self.reversible_fraction,
            "technology": self.technology,
        }


def summarize_kernels(kernels: Sequence[KernelName], technology: Technology = Technology.cpu_reference) -> JobThermoSummary:
    if not kernels:
        return JobThermoSummary(0.0, 0.0, 0.0, technology.value)
    energy = 0.0
    landauer = 0.0
    rev = 0
    for k in kernels:
        sig = signature_of(k)
        m = measure_thermodynamic(technology, k, bits_erased=sig.landauer_bits, reversible=sig.reversible)
        energy += m.net_energy
        landauer += m.landauer_bound
        if sig.reversible:
            rev += 1
    return JobThermoSummary(energy, landauer, rev / len(kernels), technology.value)


def prefer_reversible(candidates: Sequence[KernelName], policy: ThermoPolicy = ThermoPolicy.max_reversible) -> Optional[KernelName]:
    if not candidates:
        return None
    if policy is ThermoPolicy.max_reversible:
        rev = [k for k in candidates if signature_of(k).reversible]
        if rev:
            return rev[0]
    return list(candidates)[0]
