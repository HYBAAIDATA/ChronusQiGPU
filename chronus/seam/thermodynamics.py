"""Thermodynamic core — axioms A5, A6, T1–T6.

Modeled accounting. Commodity silicon reports conventional CMOS unless a
device explicitly declares an adiabatic technology.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict

from .types import KernelName, PhysicalMeasurement

K_B = 1.380649e-23
T_ROOM = 300.0
T_CRYO = 4.2
LN2 = math.log(2.0)


class Technology(str, Enum):
    conventional_cmos = "conventional_cmos"
    adiabatic_cmos_crl = "adiabatic_cmos_crl"
    adiabatic_cmos_scrl = "adiabatic_cmos_scrl"
    adiabatic_cmos_2lal = "adiabatic_cmos_2lal"
    superconducting_aqfp = "superconducting_aqfp"
    quantum_annealer = "quantum_annealer"
    cpu_reference = "cpu_reference"


class ThermoPolicy(str, Enum):
    min_energy = "min_energy"
    min_landauer = "min_landauer"
    min_cost = "min_cost"
    max_reversible = "max_reversible"
    balanced = "balanced"


@dataclass(frozen=True)
class ThermodynamicMeasurement:
    conventional_energy: float
    adiabatic_energy: float
    landauer_bound: float
    uncomputation_savings: float
    net_energy: float
    bits_erased: int
    technology: Technology
    time_ns: int = 0
    temperature_k: float = T_ROOM

    def as_dict(self) -> Dict[str, Any]:
        return {
            "conventional_energy": self.conventional_energy,
            "adiabatic_energy": self.adiabatic_energy,
            "landauer_bound": self.landauer_bound,
            "uncomputation_savings": self.uncomputation_savings,
            "net_energy": self.net_energy,
            "bits_erased": self.bits_erased,
            "technology": self.technology.value,
            "time_ns": self.time_ns,
            "temperature_k": self.temperature_k,
        }

    def physical(self) -> PhysicalMeasurement:
        return PhysicalMeasurement(
            time_ns=self.time_ns,
            energy_j=self.net_energy,
            temperature_c=self.temperature_k - 273.15,
            error_rate=0.0,
        )


def landauer_bound(bits_erased: int, temperature_k: float = T_ROOM) -> float:
    return float(bits_erased) * K_B * temperature_k * LN2


def adiabatic_energy(
    c_farad: float,
    v_volt: float,
    r_ohm: float,
    t_s: float,
) -> float:
    if t_s <= 0.0:
        return 0.5 * c_farad * v_volt * v_volt
    return c_farad * v_volt * v_volt * ((r_ohm * c_farad) / t_s)


def conventional_energy(c_farad: float, v_volt: float) -> float:
    return 0.5 * c_farad * v_volt * v_volt


def advantage_factor(t_s: float, r_ohm: float, c_farad: float) -> float:
    denom = r_ohm * c_farad
    if denom <= 0.0:
        return 0.0
    return 0.5 * (t_s / denom)


def measure_thermodynamic(
    technology: Technology,
    kernel: KernelName,
    bits_erased: int,
    switches: int = 1,
    reversible: bool = False,
    time_ns: int = 0,
    c_farad: float = 1e-15,
    v_volt: float = 0.8,
    r_ohm: float = 1e3,
    t_s: float = 1e-9,
) -> ThermodynamicMeasurement:
    conv = conventional_energy(c_farad, v_volt) * switches
    if technology in (Technology.conventional_cmos, Technology.cpu_reference):
        bound = landauer_bound(bits_erased)
        return ThermodynamicMeasurement(
            conv,
            0.0,
            bound,
            0.0,
            conv,
            bits_erased,
            technology,
            time_ns,
        )
    if technology is Technology.superconducting_aqfp:
        bound = landauer_bound(bits_erased, T_CRYO)
        adia = 1e-21 * switches
        savings = bound if reversible else 0.0
        return ThermodynamicMeasurement(
            0.0,
            adia,
            bound,
            savings,
            adia,
            bits_erased,
            technology,
            time_ns,
            T_CRYO,
        )
    adia = adiabatic_energy(c_farad, v_volt, r_ohm, t_s) * switches
    bound = landauer_bound(bits_erased)
    savings = bound if reversible else 0.0
    return ThermodynamicMeasurement(
        conv,
        adia,
        bound,
        savings,
        max(0.0, adia + bound - savings),
        bits_erased,
        technology,
        time_ns,
    )


def predict_energy(
    technology: Technology,
    reversible: bool,
    switches: int = 1,
) -> float:
    return measure_thermodynamic(
        technology,
        KernelName.sha256d_verify,
        0 if reversible else 1,
        switches,
        reversible,
    ).net_energy


def predict_landauer(reversible: bool, bits: int = 1) -> float:
    return 0.0 if reversible else landauer_bound(bits)
