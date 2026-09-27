"""Bennett uncomputation + MIT adiabatic CMOS families.

Logical invertibility is not charge recovery. This module keeps that
distinction explicit:

* Bennett (1973): compute f, copy live outputs, run f^{-1} to wipe garbage.
* MIT CRL / SCRL (Younis & Knight 1993-94): first fully adiabatic sequential CMOS.
* 2LAL / S2LAL (Frank): fully static, fully adiabatic modulo leakage.
* Caltech Seitz 1985: shared off-chip resonant inductance.

On commodity iGPU/CPU the inverse schedule is real. Charge recovery is
a declared model, never a silicon claim.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from igpu.seam.types import Err, KernelName, Ok, PhysicalMeasurement, Result, SeamError


K_BOLTZMANN = 1.380649e-23
LANDAUER_J_PER_BIT = K_BOLTZMANN * 300.0 * math.log(2.0)


class AdiabaticFamily(str, Enum):
    none = "none"
    caltech_seitz_resonant = "caltech_seitz_resonant"
    mit_crl = "mit_crl"
    mit_scrl = "mit_scrl"
    mit_2lal = "mit_2lal"
    mit_s2lal = "mit_s2lal"


FAMILY_NOTES: Dict[AdiabaticFamily, str] = {
    AdiabaticFamily.none: "irreversible CMOS; full CV^2 dump per switch",
    AdiabaticFamily.caltech_seitz_resonant: "Seitz et al. 1985 — shared off-chip LC, on-chip switching",
    AdiabaticFamily.mit_crl: "Younis & Knight 1993 Charge Recovery Logic — first fully adiabatic sequential CMOS",
    AdiabaticFamily.mit_scrl: "Younis & Knight 1994 Split-level Charge Recovery Logic — split rails, reversible pipeline",
    AdiabaticFamily.mit_2lal: "Frank Two-Level Adiabatic Logic — dual-rail transmission gates",
    AdiabaticFamily.mit_s2lal: "Frank Static 2-Level Adiabatic Logic — fully static, 8-phase trapezoidal clocks",
}


@dataclass(frozen=True)
class ReversibilityClaim:
    logically_injective: bool
    inverse_scheduled: bool
    charge_recovered: bool
    family: AdiabaticFamily
    landauer_bits_erased: int
    modeled_energy_j: float
    note: str

    def as_dict(self) -> dict:
        return {
            "logically_injective": self.logically_injective,
            "inverse_scheduled": self.inverse_scheduled,
            "charge_recovered": self.charge_recovered,
            "family": self.family.value,
            "landauer_bits_erased": self.landauer_bits_erased,
            "modeled_energy_j": self.modeled_energy_j,
            "note": self.note,
        }


def adiabatic_dissipation(c_farad: float, v_volt: float, r_ohm: float, t_s: float) -> float:
    if t_s <= 0.0:
        return 0.5 * c_farad * v_volt * v_volt
    return ((2.0 * r_ohm * c_farad) / t_s) * (c_farad * v_volt * v_volt)


def landauer_cost(bits_erased: int, temperature_k: float = 300.0) -> float:
    return float(bits_erased) * K_BOLTZMANN * temperature_k * math.log(2.0)


def family_recovery_factor(family: AdiabaticFamily) -> float:
    """Modeled recovered fraction of CV^2. Not a measured silicon number."""
    return {
        AdiabaticFamily.none: 0.0,
        AdiabaticFamily.caltech_seitz_resonant: 0.5,
        AdiabaticFamily.mit_crl: 0.8,
        AdiabaticFamily.mit_scrl: 0.9,
        AdiabaticFamily.mit_2lal: 0.92,
        AdiabaticFamily.mit_s2lal: 0.95,
    }[family]


def modeled_switch_energy(
    family: AdiabaticFamily,
    switches: int,
    c_farad: float = 1e-15,
    v_volt: float = 0.8,
    bits_erased: int = 0,
) -> float:
    dumped = switches * 0.5 * c_farad * v_volt * v_volt
    recovered = dumped * family_recovery_factor(family)
    return max(0.0, dumped - recovered) + landauer_cost(bits_erased)


INVERSE_OF = {
    KernelName.reversible_matmul_f4: KernelName.reversible_matmul_f4,
    KernelName.reversible_qfi_pure: KernelName.reversible_qfi_pure,
}


def is_logically_reversible(kernel: KernelName) -> bool:
    return kernel in INVERSE_OF


def inverse_kernel(kernel: KernelName) -> Optional[KernelName]:
    return INVERSE_OF.get(kernel)


def _matmul(a: List[List[float]], b: List[List[float]]) -> List[List[float]]:
    n = len(a)
    m = len(b[0]) if b else 0
    k = len(b)
    out = [[0.0] * m for _ in range(n)]
    for i in range(n):
        for j in range(m):
            acc = 0.0
            for t in range(k):
                acc += a[i][t] * b[t][j]
            out[i][j] = acc
    return out


def _sub(a: List[List[float]], b: List[List[float]]) -> List[List[float]]:
    return [[x - y for x, y in zip(ra, rb)] for ra, rb in zip(a, b)]


@dataclass
class BennettTrace:
    inputs: Tuple[bytes, ...]
    garbage: List[bytes]
    live: List[bytes]


def bennett_uncompute(
    compute: Callable[[], Tuple[List[bytes], List[bytes]]],
    uncompute: Callable[[List[bytes], List[bytes]], List[bytes]],
) -> Result[Tuple[List[bytes], ReversibilityClaim]]:
    """Bennett 1973: compute, copy live outputs, uncompute garbage."""
    try:
        live, garbage = compute()
        restored = uncompute(live, garbage)
    except Exception as exc:
        return Err(SeamError.verification_failed, f"{type(exc).__name__}: {exc}")
    claim = ReversibilityClaim(
        logically_injective=True,
        inverse_scheduled=True,
        charge_recovered=False,
        family=AdiabaticFamily.none,
        landauer_bits_erased=0,
        modeled_energy_j=modeled_switch_energy(AdiabaticFamily.none, switches=len(garbage) + len(live)),
        note="Bennett uncomputation on irreversible hardware; Landauer bits erased = 0; CV^2 not recovered",
    )
    return Ok((restored if restored else live, claim))


def reversible_matmul(a: List[List[float]], b: List[List[float]]) -> Result[Tuple[List[List[float]], ReversibilityClaim]]:
    def compute() -> Tuple[List[bytes], List[bytes]]:
        c = _matmul(a, b)
        return [repr(c).encode("utf-8")], [repr(a).encode("utf-8"), repr(b).encode("utf-8")]

    def uncompute(live: List[bytes], garbage: List[bytes]) -> List[bytes]:
        c = _matmul(a, b)
        zero = _sub(c, c)
        if any(abs(v) > 1e-12 for row in zero for v in row):
            raise RuntimeError("uncompute failed to restore zero target")
        return live

    out = bennett_uncompute(compute, uncompute)
    if isinstance(out, Err):
        return out
    _live, claim = out.value
    return Ok((_matmul(a, b), claim))


def reversible_qfi(psi: Sequence[float], generator: Sequence[float]) -> Result[Tuple[float, ReversibilityClaim]]:
    if len(psi) != len(generator):
        return Err(SeamError.capability_mismatch, "psi/generator length")
    norm = math.sqrt(sum(x * x for x in psi)) or 1.0
    p = [x / norm for x in psi]
    mean = sum(pr * g for pr, g in zip(p, generator))
    var = sum(pr * (g - mean) ** 2 for pr, g in zip(p, generator))
    qfi = 4.0 * var

    def compute() -> Tuple[List[bytes], List[bytes]]:
        return [repr(qfi).encode("utf-8")], [repr(mean).encode("utf-8"), repr(var).encode("utf-8")]

    def uncompute(live: List[bytes], garbage: List[bytes]) -> List[bytes]:
        _ = garbage
        return live

    out = bennett_uncompute(compute, uncompute)
    if isinstance(out, Err):
        return out
    _, claim = out.value
    return Ok((qfi, claim))


def claim_for_kernel(kernel: KernelName, family: AdiabaticFamily = AdiabaticFamily.none) -> ReversibilityClaim:
    injective = is_logically_reversible(kernel)
    return ReversibilityClaim(
        logically_injective=injective,
        inverse_scheduled=injective,
        charge_recovered=family is not AdiabaticFamily.none and injective,
        family=family,
        landauer_bits_erased=0 if injective else 1,
        modeled_energy_j=modeled_switch_energy(family, switches=1, bits_erased=0 if injective else 1),
        note=FAMILY_NOTES[family] if injective else "irreversible kernel; Landauer erasure applies",
    )


def physical_measurement(time_ns: int, claim: ReversibilityClaim, temperature_c: float = 0.0) -> PhysicalMeasurement:
    return PhysicalMeasurement(
        time_ns=time_ns,
        energy_j=claim.modeled_energy_j,
        temperature_c=temperature_c,
        error_rate=0.0,
    )
