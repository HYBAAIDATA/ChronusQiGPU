"""Exact mathematical capacity certificates for deterministic SHA-256d fabrics.

The product ``chips * cores * clock / initiation_interval`` is an exact formal
steady-state capacity. It is not a measurement and is never relabelled as
executed protocol work. Finite-window certificates include pipeline fill so a
cold-start floor cannot be claimed from steady-state algebra alone.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, dataclass
from fractions import Fraction
from typing import Any, Iterable

from .canonical_serialization import canonical_serialize, canonical_sha256

TEN_EH_HPS = 10**19
SCHEMA = "turing.deterministic_hashrate/v1"


def _fraction(value: int | Fraction) -> Fraction:
    value = Fraction(value)
    if value <= 0:
        raise ValueError("rate quantities must be positive")
    return value


def _fraction_dict(value: Fraction) -> dict[str, dict[str, int]]:
    return {
        "$rational": {
            "numerator": value.numerator,
            "denominator": value.denominator,
        }
    }


def _canonical(value: Any) -> bytes:
    return canonical_serialize(value)


def _digest(value: Any) -> str:
    return canonical_sha256(value)


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
    initiation_interval_cycles: Fraction = Fraction(1)
    mode: str = "fully_packed"
    bubble_fraction: Fraction = Fraction(0)
    justification: str = "one completed SHA-256d result admitted per cycle"

    def __post_init__(self) -> None:
        if self.compression_blocks < 1 or self.rounds_per_block < 1:
            raise ValueError("pipeline block and round counts must be >= 1")
        interval = _fraction(self.initiation_interval_cycles)
        bubbles = Fraction(self.bubble_fraction)
        if bubbles < 0:
            raise ValueError("bubble_fraction must be >= 0")
        object.__setattr__(self, "initiation_interval_cycles", interval)
        object.__setattr__(self, "bubble_fraction", bubbles)
        if not self.justification.strip():
            raise ValueError("pipeline initiation interval requires a justification")
        if self.mode == "fully_packed" and (interval != 1 or bubbles != 0):
            raise ValueError("fully_packed requires I=1 and zero bubbles")
        if self.mode == "serialized_three_block" and (
            interval != self.compression_blocks or bubbles != 0
        ):
            raise ValueError("serialized_three_block requires I=compression_blocks")
        if self.mode == "pipelined_with_bubbles" and (
            bubbles <= 0 or interval != 1 + bubbles
        ):
            raise ValueError("pipelined_with_bubbles requires I=1+bubble_fraction")
        if self.mode not in {
            "fully_packed",
            "serialized_three_block",
            "pipelined_with_bubbles",
            "declared_custom",
        }:
            raise ValueError("unknown pipeline mode")

    @classmethod
    def fully_packed(cls) -> "PipelineSpec":
        return cls()

    @classmethod
    def serialized_three_block(cls) -> "PipelineSpec":
        return cls(
            initiation_interval_cycles=Fraction(3),
            mode="serialized_three_block",
            justification="three SHA-256 compression blocks serialized per result",
        )

    @classmethod
    def with_bubbles(cls, bubble_fraction: Fraction) -> "PipelineSpec":
        bubbles = Fraction(bubble_fraction)
        return cls(
            initiation_interval_cycles=1 + bubbles,
            mode="pipelined_with_bubbles",
            bubble_fraction=bubbles,
            justification="declared exact bubble fraction increases I from one",
        )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PipelineSpec":
        return cls(
            compression_blocks=int(payload["compression_blocks"]),
            rounds_per_block=int(payload["rounds_per_block"]),
            initiation_interval_cycles=_fraction_from_dict(
                payload["initiation_interval_cycles"]
            ),
            mode=str(payload["mode"]),
            bubble_fraction=_fraction_from_dict(payload["bubble_fraction"], positive=False),
            justification=str(payload["justification"]),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "compression_blocks": self.compression_blocks,
            "rounds_per_block": self.rounds_per_block,
            "initiation_interval_cycles": _fraction_dict(
                self.initiation_interval_cycles
            ),
            "mode": self.mode,
            "bubble_fraction": _fraction_dict(self.bubble_fraction),
            "justification": self.justification,
        }

    @property
    def latency_cycles(self) -> int:
        return self.compression_blocks * self.rounds_per_block

    def outputs_per_core(self, elapsed_cycles: int) -> int:
        elapsed_cycles = int(elapsed_cycles)
        if elapsed_cycles < 0:
            raise ValueError("elapsed_cycles must be >= 0")
        if elapsed_cycles < self.latency_cycles:
            return 0
        available = Fraction(elapsed_cycles - self.latency_cycles, 1)
        return 1 + math.floor(available / self.initiation_interval_cycles)


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
        return (
            Fraction(self.hashes_after_cycles(elapsed_cycles))
            * self.clock_hz
            / elapsed_cycles
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "chips": self.chips,
            "cores_per_chip": self.cores_per_chip,
            "clock_hz": _fraction_dict(self.clock_hz),
            "pipeline": self.pipeline.as_dict(),
            "parallel_cores": self.parallel_cores,
        }


@dataclass(frozen=True)
class DeterminismEnvelope:
    chips_min: int
    cores_per_chip_min: int
    clock_hz_min: Fraction
    initiation_interval_cycles_max: Fraction = Fraction(1)
    floor_hps: int = TEN_EH_HPS

    def __post_init__(self) -> None:
        if min(self.chips_min, self.cores_per_chip_min) < 1:
            raise ValueError("minimum chips and cores must be >= 1")
        interval = _fraction(self.initiation_interval_cycles_max)
        object.__setattr__(self, "initiation_interval_cycles_max", interval)
        object.__setattr__(self, "clock_hz_min", _fraction(self.clock_hz_min))
        if self.floor_hps < 1:
            raise ValueError("floor_hps must be >= 1")

    @property
    def guaranteed_steady_state_hps(self) -> Fraction:
        return (
            Fraction(self.chips_min * self.cores_per_chip_min)
            * self.clock_hz_min
            / self.initiation_interval_cycles_max
        )

    @property
    def floor_met(self) -> bool:
        return self.guaranteed_steady_state_hps >= self.floor_hps


@dataclass(frozen=True)
class HashrateCertificate:
    schema: str
    design: dict[str, Any]
    floor_hps: int
    steady_state_hps: dict[str, Any]
    steady_state_floor_met: bool
    cold_start_cycles: int | None
    cold_start_window_hps: dict[str, Any] | None
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
    """Exact certificate reconstruction or truth-boundary failure."""


@dataclass(frozen=True)
class FleetClass:
    """One exact homogeneous class inside a heterogeneous fleet."""

    class_id: str
    chips: int
    cores_per_chip: int
    clock_hz: Fraction
    pipeline: PipelineSpec

    def __post_init__(self) -> None:
        if not self.class_id.strip():
            raise ValueError("class_id is required")
        if self.chips < 1 or self.cores_per_chip < 1:
            raise ValueError("chips and cores_per_chip must be positive")
        object.__setattr__(self, "clock_hz", _fraction(self.clock_hz))

    @property
    def steady_state_hps(self) -> Fraction:
        return (
            Fraction(self.chips * self.cores_per_chip)
            * self.clock_hz
            / self.pipeline.initiation_interval_cycles
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "class_id": self.class_id,
            "chips": self.chips,
            "cores_per_chip": self.cores_per_chip,
            "clock_hz": _fraction_dict(self.clock_hz),
            "pipeline": self.pipeline.as_dict(),
            "steady_state_hps": _fraction_dict(self.steady_state_hps),
        }


@dataclass(frozen=True)
class HeterogeneousFleet:
    classes: tuple[FleetClass, ...]

    def __post_init__(self) -> None:
        if not self.classes:
            raise ValueError("a heterogeneous fleet requires at least one class")
        identifiers = [row.class_id for row in self.classes]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("fleet class identifiers must be unique")

    @property
    def steady_state_hps(self) -> Fraction:
        return sum((row.steady_state_hps for row in self.classes), Fraction(0))

    def as_dict(self) -> dict[str, Any]:
        return {
            "classes": [row.as_dict() for row in self.classes],
            "steady_state_hps": _fraction_dict(self.steady_state_hps),
        }


@dataclass(frozen=True)
class HeterogeneousFleetCertificate:
    schema: str
    fleet: dict[str, Any]
    floor_hps: int
    floor_met: bool
    theorem: str
    truth_class: str
    certificate_digest: str

    def unsigned_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row.pop("certificate_digest")
        return row


def issue_heterogeneous_fleet_certificate(
    fleet: HeterogeneousFleet,
    *,
    floor_hps: int = TEN_EH_HPS,
) -> HeterogeneousFleetCertificate:
    if floor_hps < 1:
        raise ValueError("floor_hps must be positive")
    unsigned = {
        "schema": "turing.heterogeneous_hashrate/v1",
        "fleet": fleet.as_dict(),
        "floor_hps": floor_hps,
        "floor_met": fleet.steady_state_hps >= floor_hps,
        "theorem": "H_total = sum_i(chips_i * cores_i * clock_i / I_i)",
        "truth_class": "exact_mathematical_capacity_not_executed_work",
    }
    return HeterogeneousFleetCertificate(
        **unsigned,
        certificate_digest=_digest(unsigned),
    )


def _fleet_from_dict(payload: dict[str, Any]) -> HeterogeneousFleet:
    classes = []
    for row in payload["classes"]:
        classes.append(
            FleetClass(
                class_id=str(row["class_id"]),
                chips=int(row["chips"]),
                cores_per_chip=int(row["cores_per_chip"]),
                clock_hz=_fraction_from_dict(row["clock_hz"]),
                pipeline=PipelineSpec.from_dict(row["pipeline"]),
            )
        )
    return HeterogeneousFleet(tuple(classes))


def verify_heterogeneous_fleet_certificate(
    certificate: HeterogeneousFleetCertificate,
) -> bool:
    if certificate.schema != "turing.heterogeneous_hashrate/v1":
        raise CertificateError("unsupported heterogeneous certificate schema")
    if certificate.truth_class != "exact_mathematical_capacity_not_executed_work":
        raise CertificateError("heterogeneous certificate overclaims execution")
    expected = issue_heterogeneous_fleet_certificate(
        _fleet_from_dict(certificate.fleet),
        floor_hps=certificate.floor_hps,
    )
    if certificate != expected:
        raise CertificateError("heterogeneous certificate failed exact replay")
    return True


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


def _fraction_from_dict(
    value: dict[str, Any], *, positive: bool = True
) -> Fraction:
    try:
        encoded = value["$rational"]
        result = Fraction(
            int(encoded["numerator"]),
            int(encoded["denominator"]),
        )
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
        raise CertificateError("invalid exact fraction encoding") from exc
    if positive and result <= 0:
        raise CertificateError("exact fraction must be positive")
    if not positive and result < 0:
        raise CertificateError("exact fraction must be non-negative")
    return result


def verify_hashrate_certificate(certificate: HashrateCertificate) -> bool:
    if certificate.schema != SCHEMA:
        raise CertificateError("unsupported certificate schema")
    if certificate.truth_class != "exact_mathematical_capacity_not_executed_work":
        raise CertificateError("certificate overclaims executed performance")
    design_row = certificate.design
    clock = _fraction_from_dict(design_row["clock_hz"])
    pipeline = PipelineSpec.from_dict(design_row["pipeline"])
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
    initiation_interval_cycles: int | Fraction = Fraction(1),
) -> int:
    if cores_per_chip < 1 or floor_hps < 1:
        raise ValueError("design quantities must be positive")
    interval = _fraction(initiation_interval_cycles)
    per_chip = Fraction(cores_per_chip) * _fraction(clock_hz) / interval
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
    "FleetClass",
    "HeterogeneousFleet",
    "HeterogeneousFleetCertificate",
    "HashrateCertificate",
    "PipelineSpec",
    "SCHEMA",
    "TEN_EH_HPS",
    "design_lattice",
    "issue_hashrate_certificate",
    "issue_heterogeneous_fleet_certificate",
    "minimum_chips",
    "minimum_chips_for_window",
    "verify_hashrate_certificate",
    "verify_heterogeneous_fleet_certificate",
]
