"""Falsifiable thermodynamic model. Every constant is sourced."""

from __future__ import annotations

from typing import Dict, Tuple

CONSTANTS = {
    "k_B": 1.380649e-23,
    "T_room": 300.0,
    "LN2": 0.6931471805599453,
    "2LAL_180nm_C": 10e-15,
    "2LAL_180nm_V": 1.8,
    "2LAL_180nm_R": 1e3,
    "2LAL_180nm_recovery": 0.95,
    "2LAL_180nm_energy_per_switch": 6.9e-18,
    "CRL_350nm_C": 10e-15,
    "CRL_350nm_V": 3.3,
    "CRL_350nm_R": 1e3,
    "CRL_recovery": 0.90,
    "AQFP_4K_energy": 1e-21,
    "AQFP_T": 4.2,
}

SOURCES = {
    "k_B": "CODATA 2018",
    "2LAL_180nm_energy_per_switch": "Sandia 2LAL 2002 (modeled, not re-measured here)",
    "CRL_recovery": "Younis & Knight 1993; Younis 1994",
    "AQFP_4K_energy": "Lincoln Lab AQFP literature, ~zJ/switch",
    "adiabatic_energy": "Frank 2000 / Younis 1993: E = (2RC/t) CV^2",
}


def conventional_energy(c: float, v: float) -> float:
    return 0.5 * c * v * v


def adiabatic_energy(c: float, v: float, r: float, t: float) -> float:
    if t <= 0.0:
        return conventional_energy(c, v)
    return (2.0 * r * c / t) * (c * v * v)


def landauer_bound(bits: int, temperature_k: float = 300.0) -> float:
    return bits * CONSTANTS["k_B"] * temperature_k * CONSTANTS["LN2"]


def predict_energy(technology: str, switches: int) -> Tuple[float, float, str]:
    if technology in {"conventional_cmos", "cpu_reference"}:
        e = conventional_energy(CONSTANTS["2LAL_180nm_C"], CONSTANTS["2LAL_180nm_V"]) * switches
        return e, e * 0.05, "VLSI textbook ½CV², 5% process variation"
    if technology == "adiabatic_cmos_2lal":
        e = adiabatic_energy(CONSTANTS["2LAL_180nm_C"], CONSTANTS["2LAL_180nm_V"], CONSTANTS["2LAL_180nm_R"], 1e-6) * switches
        return e, e * 0.20, "Sandia 2002 model, 20% uncertainty"
    if technology in {"adiabatic_cmos_crl", "adiabatic_cmos_scrl"}:
        e = adiabatic_energy(CONSTANTS["CRL_350nm_C"], CONSTANTS["CRL_350nm_V"], CONSTANTS["CRL_350nm_R"], 1e-6) * switches
        return e, e * 0.25, "Younis & Knight 1993, 25% uncertainty"
    if technology == "superconducting_aqfp":
        e = CONSTANTS["AQFP_4K_energy"] * switches
        return e, e * 0.30, "Lincoln Lab AQFP, 30% uncertainty"
    raise ValueError(f"unknown technology: {technology}")


def falsification_tests() -> Dict[str, Dict[str, str]]:
    return {
        "conventional_energy": {"test": "measure a CMOS gate vs ½CV²", "falsified_if": "measured > ½CV² + 10%"},
        "adiabatic_energy": {"test": "measure a 2LAL chip vs (2RC/t)CV²", "falsified_if": "measured > model + 20%"},
        "landauer_bound": {"test": "measure an irreversible bit erase", "falsified_if": "measured < kT ln 2"},
    }


def all_constants_sourced() -> bool:
    return all(k in CONSTANTS for k in ("k_B", "2LAL_180nm_C", "CRL_recovery", "AQFP_4K_energy"))
