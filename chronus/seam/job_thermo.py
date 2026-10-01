"""T6 / F6 / F7 — job thermodynamic summary and reversible preference."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from .signatures import signature_of
from .thermodynamics import Technology, ThermoPolicy, measure_thermodynamic
from .types import KernelName


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


def summarize_kernels(
    kernels: Sequence[KernelName],
    technology: Technology = Technology.cpu_reference,
) -> JobThermoSummary:
    if not kernels:
        return JobThermoSummary(0.0, 0.0, 0.0, technology.value)
    energy = 0.0
    landauer = 0.0
    reversible_count = 0
    for kernel in kernels:
        signature = signature_of(kernel)
        measurement = measure_thermodynamic(
            technology,
            kernel,
            bits_erased=signature.landauer_bits,
            reversible=signature.reversible,
        )
        energy += measurement.net_energy
        landauer += measurement.landauer_bound
        if signature.reversible:
            reversible_count += 1
    return JobThermoSummary(
        energy,
        landauer,
        reversible_count / len(kernels),
        technology.value,
    )


def prefer_reversible(
    candidates: Sequence[KernelName],
    policy: ThermoPolicy = ThermoPolicy.max_reversible,
) -> Optional[KernelName]:
    if not candidates:
        return None
    if policy is ThermoPolicy.max_reversible:
        reversible = [kernel for kernel in candidates if signature_of(kernel).reversible]
        if reversible:
            return reversible[0]
    return list(candidates)[0]
