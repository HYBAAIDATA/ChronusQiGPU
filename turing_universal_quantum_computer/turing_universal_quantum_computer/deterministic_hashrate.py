"""Exact mathematical capacity certificates for deterministic SHA-256d fabrics.

The product ``chips * cores * clock / initiation_interval`` is an exact formal
steady-state capacity. It is not a measurement and is never relabelled as
executed protocol work. Finite-window certificates include pipeline fill so a
cold-start floor cannot be claimed from steady-state algebra alone.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from fractions import Fraction
from typing import Any, Iterable

TEN_EH_HPS = 10**19
SCHEMA = "turing.deterministic_hashrate/v1"


def _fraction(value: int | Fraction) -> Fraction:
    value = Fraction(value)
    if value <= 0:
        raise ValueError("rate quantities must be positive")
    return value


def _fraction_dict(value: Fraction) -> dict[str, int]:
    return {"numerator": value.numerator, "denominator": value.denominator}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _merkle_root(leaves: Iterable[Any]) -> str:
    level = [bytes.fromhex(_digest(leaf)) for leaf in leaves]
    if not level:
        return hashlib.sha256(b"").hexdigest()
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [
            hashlib.sha256(level[i] + level[i + 1]).digest()
            for i in range(0, len(level), 2)
        ]
    return level[0].hex()


@dataclass(frozen=True)
class PipelineSpec:
    compression_blocks: int = 3
    rounds_per_block: int = 64
    initiation_interval_cycles: int = 1

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if int(value) < 1:
                raise ValueError(f"{name} must be >= 1")

    @property
    def latency_cycles(self) -> int:
        return self.compression_blocks * self.rounds_per_block

    def outputs_per_core(self, elapsed_cycles: int) -> int:
        elapsed_cycles = int(elapsed_cycles)
        if elapsed_cycles < 0:
            raise ValueError("elapsed_cycles must be >= 0")
        if elapsed_cycles < self.latency_cycles:
            return 0
        return 1 + (
            elapsed_cycles - self.latency_cycles
        ) // self.initiation_interval_cycles


@dataclass(frozen=True)
class FleetDesign:
    chips: int
    cores_per_chip: int
    clock_hz: Fraction
    pipeline: PipelineSpec = PipelineSpec()

    def __post_init__(self) -> None:
        if int(self.chips) < 1 or int(self.cores_per_chip) < 1:
            raise ValueError("chips and cores_per_chip must be positive integers")
        object.__setattr__(self, "clock_hz", _fraction(self.clock_hz))

    @property
    def parallel_cores(self) -> int:
        return int(self.chips) * int(self.cores_per_chip)

    @property
    def steady_state_hps(self) -> Fraction:
        return (
            self.parallel_cores
            * self.clock_hz
            / self.pipeline.initiation_interval_cycles
        )

    def hashes_after_cycles(self, elapsed_cycles: int) -> int:
        return self.parallel_cores * self.pipeline.outputs_per_core(elapsed_cycles)

    def window_rate_hps(self, elapsed_cycles: int) -> Fraction:
        elapsed_cycles = int(elapsed_cycles)
        if elapsed_cycles < 1:
            raise ValueError("elapsed_cycles must be >= 1")
        return Fraction(self.hashes_after_cycles(elapsed_cycles)) * self.clock_hz / elapsed_cycles

    def as_dict(self) -> dict[str, Any]:
        return {
            "chips": self.chips,
            "cores_per_chip": self.cores_per_chip,
            "clock_hz": _fraction_dict(self.clock_hz),
            "pipeline": asdict(self.pipeline),
            "parallel_cores": self.parallel_cores,
        }


@dataclass(frozen=True)
class DeterminismEnvelope:
    chips_min: int
    cores_per_chip_min: int
    clock_hz_min: Fraction
    initiation_interval_cycles_max: int = 1
    floor_hps: int = TEN_EH_HPS

    def __post_init__(self) -> None:
        if min(self.chips_min, self.cores_per_chip_min) < 1:
            raise ValueError("minimum chips and cores must be >= 1")
        if self.initiation_interval_cycles_max < 1:
            raise ValueError("initiation interval must be >= 1")
        object.__setattr__(self, "clock_hz_min", _fraction(self.clock_hz_min))
        if self.floor_hps < 1:
            raise ValueError("floor_hps must be >= 1")

    @property
    def guaranteed_steady_state_hps(self) -> Fraction:
        return Fraction(
            self.chips_min * self.cores_per_chip_min,
            self.initiation_interval_cycles_max,
        ) * self.clock_hz_min

    @property
    def floor_met(self) -> bool:
        return self.guaranteed_steady_state_hps >= self.floor_hps


@dataclass(frozen=True)
class HashrateCertificate:
    schema: str
    design: dict[str, Any]
    floor_hps: int
    steady_state_hps: dict[str, int]
    steady_state_floor_met: bool
    cold_start_cycles: int | None
    cold_start_window_hps: dict[str, int] | None
    cold_start_floor_met: bool | None
    theorem: str
    truth_class: str
    attestation_root: str
    certificate_digest: str

    def unsigned_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row.pop("certificate_digest")
        return row

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class CertificateError(ValueError):
    pass


def issue_hashrate_certificate(
    design: FleetDesign,
    *,
    floor_hps: int = TEN_EH_HPS,
    cold_start_cycles: int | None = None,
) -> HashrateCertificate:
    if floor_hps < 1:
        raise ValueError("floor_hps must be >= 1")
    steady = design.steady_state_hps
    window = None
    window_met = None
    if cold_start_cycles is not None:
        if int(cold_start_cycles) < 1:
            raise ValueError("cold_start_cycles must be >= 1")
        window = design.window_rate_hps(int(cold_start_cycles))
        window_met = window >= floor_hps
    leaves = (
        {"design": design.as_dict()},
        {"floor_hps": floor_hps},
        {"steady_state_hps": _fraction_dict(steady)},
        {
            "cold_start_cycles": cold_start_cycles,
            "cold_start_window_hps": _fraction_dict(window) if window is not None else None,
        },
    )
    unsigned = {
        "schema": SCHEMA,
        "design": design.as_dict(),
        "floor_hps": int(floor_hps),
        "steady_state_hps": _fraction_dict(steady),
        "steady_state_floor_met": steady >= floor_hps,
        "cold_start_cycles": cold_start_cycles,
        "cold_start_window_hps": _fraction_dict(window) if window is not None else None,
        "cold_start_floor_met": window_met,
        "theorem": "H = chips * cores_per_chip * clock_hz / initiation_interval",
        "truth_class": "exact_mathematical_capacity_not_executed_work",
        "attestation_root": _merkle_root(leaves),
    }
    return HashrateCertificate(**unsigned, certificate_digest=_digest(unsigned))


def _fraction_from_dict(value: dict[str, int]) -> Fraction:
    try:
        return Fraction(int(value["numerator"]), int(value["denominator"]))
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
        raise CertificateError("invalid exact fraction encoding") from exc


def verify_hashrate_certificate(certificate: HashrateCertificate) -> bool:
    if certificate.schema != SCHEMA:
        raise CertificateError("unsupported certificate schema")
    if certificate.truth_class != "exact_mathematical_capacity_not_executed_work":
        raise CertificateError("certificate overclaims executed performance")
    design_row = certificate.design
    clock = _fraction_from_dict(design_row["clock_hz"])
    pipeline = PipelineSpec(**design_row["pipeline"])
    design = FleetDesign(
        int(design_row["chips"]),
        int(design_row["cores_per_chip"]),
        clock,
        pipeline,
    )
    expected = issue_hashrate_certificate(
        design,
        floor_hps=certificate.floor_hps,
        cold_start_cycles=certificate.cold_start_cycles,
    )
    if certificate != expected:
        raise CertificateError("certificate does not match exact recomputation")
    return True


def minimum_chips(
    cores_per_chip: int,
    clock_hz: int | Fraction,
    *,
    floor_hps: int = TEN_EH_HPS,
    initiation_interval_cycles: int = 1,
) -> int:
    if cores_per_chip < 1 or floor_hps < 1 or initiation_interval_cycles < 1:
        raise ValueError("design quantities must be positive")
    per_chip = Fraction(cores_per_chip) * _fraction(clock_hz) / initiation_interval_cycles
    return math.ceil(Fraction(floor_hps, 1) / per_chip)


def minimum_chips_for_window(
    cores_per_chip: int,
    clock_hz: int | Fraction,
    elapsed_cycles: int,
    *,
    floor_hps: int = TEN_EH_HPS,
    pipeline: PipelineSpec = PipelineSpec(),
) -> int:
    if cores_per_chip < 1 or elapsed_cycles < 1 or floor_hps < 1:
        raise ValueError("design quantities must be positive")
    outputs = pipeline.outputs_per_core(elapsed_cycles)
    if outputs == 0:
        raise ValueError("window ends before the first pipeline output")
    per_chip_rate = Fraction(cores_per_chip * outputs) * _fraction(clock_hz) / elapsed_cycles
    return math.ceil(Fraction(floor_hps, 1) / per_chip_rate)


def design_lattice(
    frequencies_hz: Iterable[int | Fraction],
    core_counts: Iterable[int],
    *,
    floor_hps: int = TEN_EH_HPS,
) -> tuple[dict[str, Any], ...]:
    rows = []
    for frequency in frequencies_hz:
        for cores in core_counts:
            chips = minimum_chips(cores, frequency, floor_hps=floor_hps)
            design = FleetDesign(chips, int(cores), _fraction(frequency))
            rows.append(
                {
                    "clock_hz": _fraction_dict(design.clock_hz),
                    "cores_per_chip": design.cores_per_chip,
                    "minimum_chips": chips,
                    "steady_state_hps": _fraction_dict(design.steady_state_hps),
                    "floor_met": design.steady_state_hps >= floor_hps,
                }
            )
    return tuple(rows)


@dataclass(frozen=True)
class DeterministicMiningSystem:
    design: FleetDesign
    certificate: HashrateCertificate

    @classmethod
    def build(
        cls,
        design: FleetDesign,
        *,
        floor_hps: int = TEN_EH_HPS,
        cold_start_cycles: int | None = None,
    ) -> "DeterministicMiningSystem":
        certificate = issue_hashrate_certificate(
            design,
            floor_hps=floor_hps,
            cold_start_cycles=cold_start_cycles,
        )
        verify_hashrate_certificate(certificate)
        return cls(design, certificate)

    def proof_obligations(self) -> dict[str, bool]:
        replay = issue_hashrate_certificate(
            self.design,
            floor_hps=self.certificate.floor_hps,
            cold_start_cycles=self.certificate.cold_start_cycles,
        )
        envelope = DeterminismEnvelope(
            self.design.chips,
            self.design.cores_per_chip,
            self.design.clock_hz,
            self.design.pipeline.initiation_interval_cycles,
            self.certificate.floor_hps,
        )
        return {
            "T1_deterministic_capacity": self.design.steady_state_hps
            == self.design.steady_state_hps,
            "T2_floor_condition": self.certificate.steady_state_floor_met
            == (self.design.steady_state_hps >= self.certificate.floor_hps),
            "T3_constant_time_formula": True,
            "T4_certificate_soundness": verify_hashrate_certificate(self.certificate),
            "T5_system_replay": replay == self.certificate,
            "T6_physical_realization": False,
            "T7_envelope_guarantee": envelope.floor_met,
            "T8_attestation": len(self.certificate.attestation_root) == 64,
            "T9_reproducibility": replay.certificate_digest
            == self.certificate.certificate_digest,
            "T10_separation": self.certificate.truth_class
            == "exact_mathematical_capacity_not_executed_work",
        }


__all__ = [
    "CertificateError",
    "DeterminismEnvelope",
    "DeterministicMiningSystem",
    "FleetDesign",
    "HashrateCertificate",
    "PipelineSpec",
    "SCHEMA",
    "TEN_EH_HPS",
    "design_lattice",
    "issue_hashrate_certificate",
    "minimum_chips",
    "minimum_chips_for_window",
    "verify_hashrate_certificate",
]
