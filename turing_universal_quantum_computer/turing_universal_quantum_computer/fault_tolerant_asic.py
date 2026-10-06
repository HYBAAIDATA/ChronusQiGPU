"""Evidence-scoped engineering model for a fault-tolerant quantum ASIC stack.

This module implements the computable contracts in the supplied quantum-ASIC
specification. It is a deterministic planning, validation, and readiness
surface; it does not claim that a physical QPU, refrigerator, decoder ASIC, or
fault-tolerant machine exists. Hardware readiness requires measured evidence.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from fractions import Fraction
from typing import Any, Mapping

SCHEMA = "turing.quantum_asic/v1"


def _positive(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and > 0")
    return value


def _nonnegative(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and >= 0")
    return value


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


class EvidenceState(str, Enum):
    MODELLED = "modelled"
    SIMULATED = "simulated"
    MEASURED = "measured"
    INDEPENDENTLY_REPRODUCED = "independently_reproduced"


@dataclass(frozen=True)
class RefrigerationStage:
    name: str
    temperature_k: float
    cooling_power_w: float

    def __post_init__(self) -> None:
        _positive("temperature_k", self.temperature_k)
        _nonnegative("cooling_power_w", self.cooling_power_w)


DEFAULT_REFRIGERATION_STAGES = (
    RefrigerationStage("room", 300.0, 0.0),
    RefrigerationStage("ln2", 77.0, 0.0),
    RefrigerationStage("lhe", 4.2, 1.0),
    RefrigerationStage("pulse_tube", 0.8, 0.2),
    RefrigerationStage("still", 0.7, 0.02),
    RefrigerationStage("cold_plate", 0.1, 0.001),
    RefrigerationStage("mixing_chamber", 0.01, 1e-6),
)


@dataclass(frozen=True)
class DilutionRefrigerator:
    stages: tuple[RefrigerationStage, ...] = DEFAULT_REFRIGERATION_STAGES
    wall_power_w: float = 10_000.0

    def __post_init__(self) -> None:
        if len(self.stages) < 2:
            raise ValueError("at least two refrigeration stages are required")
        _positive("wall_power_w", self.wall_power_w)
        temperatures = [stage.temperature_k for stage in self.stages]
        if temperatures != sorted(temperatures, reverse=True):
            raise ValueError("refrigeration stages must be ordered hot to cold")

    @property
    def coldest(self) -> RefrigerationStage:
        return self.stages[-1]

    def cooling_power(self, temperature_k: float, exponent: float = 2.0) -> float:
        temperature_k = _positive("temperature_k", temperature_k)
        exponent = _positive("exponent", exponent)
        cold = self.coldest
        return cold.cooling_power_w * (temperature_k / cold.temperature_k) ** exponent

    @staticmethod
    def minimum_work(heat_w: float, hot_k: float, cold_k: float) -> float:
        heat_w = _nonnegative("heat_w", heat_w)
        hot_k = _positive("hot_k", hot_k)
        cold_k = _positive("cold_k", cold_k)
        if hot_k <= cold_k:
            raise ValueError("hot_k must exceed cold_k")
        return heat_w * (hot_k / cold_k - 1.0)

    def wiring_heat(self, physical_lines: int, heat_per_line_w: float) -> float:
        if int(physical_lines) < 0:
            raise ValueError("physical_lines must be >= 0")
        return int(physical_lines) * _nonnegative("heat_per_line_w", heat_per_line_w)

    def line_capacity(self, heat_per_line_w: float, reserve_fraction: float = 0.2) -> int:
        heat_per_line_w = _positive("heat_per_line_w", heat_per_line_w)
        if not 0 <= reserve_fraction < 1:
            raise ValueError("reserve_fraction must be in [0,1)")
        usable = self.coldest.cooling_power_w * (1.0 - reserve_fraction)
        return math.floor(usable / heat_per_line_w)


@dataclass(frozen=True)
class TransmonCoherence:
    frequency_hz: float = 5e9
    q_tls: float = 1e6
    q_quasiparticle: float = 1e7
    q_radiation: float = 1e8
    q_purcell: float = 1e6
    pure_dephasing_s: float = 300e-6

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            _positive(name, value)

    @property
    def quality_factor(self) -> float:
        inverse = sum(
            1.0 / value
            for value in (
                self.q_tls,
                self.q_quasiparticle,
                self.q_radiation,
                self.q_purcell,
            )
        )
        return 1.0 / inverse

    @property
    def t1_seconds(self) -> float:
        return self.quality_factor / (2.0 * math.pi * self.frequency_hz)

    @property
    def t2_seconds(self) -> float:
        return 1.0 / (1.0 / (2.0 * self.t1_seconds) + 1.0 / self.pure_dephasing_s)

    def operations(self, gate_time_s: float) -> int:
        return math.floor(self.t1_seconds / _positive("gate_time_s", gate_time_s))


@dataclass(frozen=True)
class SurfaceCode:
    distance: int = 21
    physical_error_rate: float = 1e-3
    threshold: float = 1e-2
    prefactor: float = 0.03

    def __post_init__(self) -> None:
        if self.distance < 3 or self.distance % 2 == 0:
            raise ValueError("distance must be an odd integer >= 3")
        for name in ("physical_error_rate", "threshold", "prefactor"):
            _positive(name, getattr(self, name))

    @property
    def physical_qubits(self) -> int:
        return 2 * self.distance**2 - 1

    @property
    def correctable_errors(self) -> int:
        return (self.distance - 1) // 2

    @property
    def logical_error_rate(self) -> float:
        ratio = self.physical_error_rate / self.threshold
        return self.prefactor * ratio ** ((self.distance + 1) / 2)

    @classmethod
    def minimum_distance(
        cls,
        physical_error_rate: float,
        target_logical_error: float,
        threshold: float = 1e-2,
        max_distance: int = 999,
    ) -> int:
        if physical_error_rate >= threshold:
            raise ValueError("physical error rate must be below threshold")
        _positive("target_logical_error", target_logical_error)
        for distance in range(3, max_distance + 1, 2):
            model = cls(distance, physical_error_rate, threshold)
            if model.logical_error_rate <= target_logical_error:
                return distance
        raise ValueError("target logical error was not reached within max_distance")


@dataclass(frozen=True)
class WiringBudget:
    wires_per_qubit: float = 6.0
    heat_per_line_w: float = 10e-9
    multiplexing: float = 1.0
    reserve_fraction: float = 0.2

    def __post_init__(self) -> None:
        _positive("wires_per_qubit", self.wires_per_qubit)
        _positive("heat_per_line_w", self.heat_per_line_w)
        _positive("multiplexing", self.multiplexing)
        if not 0 <= self.reserve_fraction < 1:
            raise ValueError("reserve_fraction must be in [0,1)")

    def effective_lines(self, qubits: int) -> int:
        if int(qubits) < 0:
            raise ValueError("qubits must be >= 0")
        return math.ceil(int(qubits) * self.wires_per_qubit / self.multiplexing)

    def maximum_qubits(self, cooling_power_w: float) -> int:
        usable = _positive("cooling_power_w", cooling_power_w) * (1 - self.reserve_fraction)
        lines = math.floor(usable / self.heat_per_line_w)
        return math.floor(lines * self.multiplexing / self.wires_per_qubit)


@dataclass(frozen=True)
class Decoder:
    code_distance: int = 21
    cycle_time_s: float = 1e-6
    throughput_bits_s: float = 1e11
    latency_s: float = 0.5e-6
    window_cycles: int = 1

    def __post_init__(self) -> None:
        if self.code_distance < 3:
            raise ValueError("code_distance must be >= 3")
        if self.window_cycles < 1:
            raise ValueError("window_cycles must be >= 1")
        for name in ("cycle_time_s", "throughput_bits_s", "latency_s"):
            _positive(name, getattr(self, name))

    @property
    def syndrome_bits_per_cycle(self) -> int:
        return 2 * (self.code_distance - 1) ** 2

    @property
    def required_input_rate(self) -> float:
        return self.syndrome_bits_per_cycle / self.cycle_time_s

    @property
    def graph_vertices(self) -> int:
        return self.syndrome_bits_per_cycle * self.window_cycles

    @property
    def mwpm_complexity_upper_bound(self) -> int:
        return self.graph_vertices**3

    @property
    def ready(self) -> bool:
        return (
            self.throughput_bits_s >= self.required_input_rate
            and self.latency_s < self.cycle_time_s
        )


@dataclass(frozen=True)
class TransmonQubit:
    charging_energy_hz: float = 200e6
    josephson_energy_hz: float = 10e9
    anharmonicity_hz: float = -300e6
    frequency_01_hz: float = 5e9
    gate_1q_s: float = 30e-9
    gate_2q_s: float = 200e-9
    readout_s: float = 700e-9
    error_1q: float = 1e-3
    error_2q: float = 1e-2

    def __post_init__(self) -> None:
        for name in (
            "charging_energy_hz",
            "josephson_energy_hz",
            "frequency_01_hz",
            "gate_1q_s",
            "gate_2q_s",
            "readout_s",
            "error_1q",
            "error_2q",
        ):
            _positive(name, getattr(self, name))
        if self.anharmonicity_hz >= 0:
            raise ValueError("transmon anharmonicity_hz must be negative")

    @property
    def ej_ec_ratio(self) -> float:
        return self.josephson_energy_hz / self.charging_energy_hz

    def report(self, coherence: TransmonCoherence) -> dict[str, Any]:
        return {
            "ej_ec_ratio": self.ej_ec_ratio,
            "transmon_regime": self.ej_ec_ratio >= 20,
            "operations_1q_per_t1": coherence.operations(self.gate_1q_s),
            "operations_2q_per_t1": coherence.operations(self.gate_2q_s),
        }


@dataclass(frozen=True)
class TunableCoupler:
    max_coupling_hz: float = 100e6
    residual_coupling_hz: float = 1e6
    tuning_time_s: float = 10e-9

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            _positive(name, value)
        if self.residual_coupling_hz > self.max_coupling_hz:
            raise ValueError("residual coupling cannot exceed maximum coupling")

    def residual_zz_hz(self, anharmonicity_hz: float) -> float:
        return self.residual_coupling_hz**2 / abs(_positive("anharmonicity_hz", anharmonicity_hz))


@dataclass(frozen=True)
class ReadoutResonator:
    frequency_hz: float = 7e9
    linewidth_hz: float = 1e6
    dispersive_shift_hz: float = 1e6
    integration_time_s: float = 700e-9
    thermal_occupancy: float = 0.01
    multiplexed_qubits: int = 10

    def __post_init__(self) -> None:
        for name in (
            "frequency_hz",
            "linewidth_hz",
            "dispersive_shift_hz",
            "integration_time_s",
            "thermal_occupancy",
        ):
            _positive(name, getattr(self, name))
        if self.multiplexed_qubits < 1:
            raise ValueError("multiplexed_qubits must be >= 1")

    @property
    def snr_proxy(self) -> float:
        return (
            self.dispersive_shift_hz
            * math.sqrt(self.integration_time_s / self.linewidth_hz)
            / self.thermal_occupancy
        )


@dataclass(frozen=True)
class QuantumChipLayout:
    die_width_mm: float = 10.0
    die_height_mm: float = 10.0
    qubit_pitch_mm: float = 0.5
    readout_multiplexing: int = 10

    def __post_init__(self) -> None:
        for name in ("die_width_mm", "die_height_mm", "qubit_pitch_mm"):
            _positive(name, getattr(self, name))
        if self.readout_multiplexing < 1:
            raise ValueError("readout_multiplexing must be >= 1")

    @property
    def qubit_capacity(self) -> int:
        return math.floor(self.die_width_mm / self.qubit_pitch_mm) * math.floor(
            self.die_height_mm / self.qubit_pitch_mm
        )

    @property
    def readout_lines(self) -> int:
        return math.ceil(self.qubit_capacity / self.readout_multiplexing)


@dataclass(frozen=True)
class SyndromeExtraction:
    cnot_layers: int = 8
    cnot_time_s: float = 100e-9
    readout_time_s: float = 700e-9
    reset_time_s: float = 200e-9

    def __post_init__(self) -> None:
        if self.cnot_layers < 1:
            raise ValueError("cnot_layers must be >= 1")
        for name in ("cnot_time_s", "readout_time_s", "reset_time_s"):
            _positive(name, getattr(self, name))

    @property
    def cycle_time_s(self) -> float:
        return self.cnot_layers * self.cnot_time_s + self.readout_time_s + self.reset_time_s


@dataclass(frozen=True)
class LogicalQubit:
    code: SurfaceCode = field(default_factory=SurfaceCode)
    cycle_time_s: float = 1e-6
    logical_gate_cycles: int = 10
    magic_state_patches: int = 100

    def __post_init__(self) -> None:
        _positive("cycle_time_s", self.cycle_time_s)
        if self.logical_gate_cycles < 1 or self.magic_state_patches < 1:
            raise ValueError("logical gate cycles and magic-state patches must be >= 1")

    @property
    def gate_time_s(self) -> float:
        return self.cycle_time_s * self.logical_gate_cycles

    @property
    def logical_lifetime_s(self) -> float:
        return self.cycle_time_s / self.code.logical_error_rate


@dataclass(frozen=True)
class RoomTemperatureControl:
    awg_channels: int
    fpga_count: int
    fpga_clock_hz: float = 500e6
    network_bits_s: float = 100e9

    def __post_init__(self) -> None:
        if self.awg_channels < 1 or self.fpga_count < 1:
            raise ValueError("AWG channels and FPGA count must be >= 1")
        _positive("fpga_clock_hz", self.fpga_clock_hz)
        _positive("network_bits_s", self.network_bits_s)


@dataclass(frozen=True)
class CryoCMOS:
    qubits_per_tile: int = 100
    power_per_tile_w: float = 10e-3
    cooling_power_4k_w: float = 1.0
    reserve_fraction: float = 0.2
    profile: str = "current_reference_10_mw"

    def __post_init__(self) -> None:
        if self.qubits_per_tile < 1:
            raise ValueError("qubits_per_tile must be >= 1")
        _positive("power_per_tile_w", self.power_per_tile_w)
        _positive("cooling_power_4k_w", self.cooling_power_4k_w)
        if not 0 <= self.reserve_fraction < 1:
            raise ValueError("reserve_fraction must be in [0,1)")
        profiles = {
            "current_reference_10_mw": 10e-3,
            "five_year_target_5_mw": 5e-3,
            "ten_year_target_1_mw": 1e-3,
        }
        if self.profile not in profiles:
            raise ValueError("unknown cryo-CMOS evidence profile")
        if self.power_per_tile_w != profiles[self.profile]:
            raise ValueError("power_per_tile_w must match the declared profile")

    @classmethod
    def five_year_target(cls) -> "CryoCMOS":
        return cls(power_per_tile_w=5e-3, profile="five_year_target_5_mw")

    @classmethod
    def ten_year_target(cls) -> "CryoCMOS":
        return cls(power_per_tile_w=1e-3, profile="ten_year_target_1_mw")

    def tiles(self, qubits: int) -> int:
        if int(qubits) < 1:
            raise ValueError("qubits must be >= 1")
        return math.ceil(int(qubits) / self.qubits_per_tile)

    def power_w(self, qubits: int) -> float:
        return self.tiles(qubits) * self.power_per_tile_w

    def supports(self, qubits: int) -> bool:
        budget = self.cooling_power_4k_w * (1 - self.reserve_fraction)
        return self.power_w(qubits) <= budget


@dataclass(frozen=True)
class RSFQ:
    clock_hz: float = 50e9
    power_per_gate_w: float = 10e-9
    gate_density_mm2: float = 1e4

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            _positive(name, value)

    def power_w(self, gates: int) -> float:
        if int(gates) < 0:
            raise ValueError("gates must be >= 0")
        return int(gates) * self.power_per_gate_w


@dataclass(frozen=True)
class SignalChain:
    attenuation_db: tuple[float, ...] = (20.0, 20.0, 10.0)
    amplifier_gain_db: float = 20.0
    amplifier_noise_temperature_k: float = 0.5

    def __post_init__(self) -> None:
        if not self.attenuation_db:
            raise ValueError("at least one attenuation stage is required")
        for value in self.attenuation_db:
            _nonnegative("attenuation_db", value)
        _nonnegative("amplifier_gain_db", self.amplifier_gain_db)
        _positive("amplifier_noise_temperature_k", self.amplifier_noise_temperature_k)

    @property
    def total_attenuation_db(self) -> float:
        return sum(self.attenuation_db)

    @property
    def net_gain_db(self) -> float:
        return self.amplifier_gain_db - self.total_attenuation_db


@dataclass(frozen=True)
class ApplicationResource:
    name: str
    logical_qubits: int
    physical_qubits: int
    logical_depth: int
    estimated_runtime_s: float
    evidence_state: EvidenceState = EvidenceState.MODELLED
    notes: str = "resource estimate; not an executed algorithm"

    def __post_init__(self) -> None:
        if min(self.logical_qubits, self.physical_qubits, self.logical_depth) < 1:
            raise ValueError("application resource counts must be >= 1")
        _positive("estimated_runtime_s", self.estimated_runtime_s)


APPLICATIONS: Mapping[str, ApplicationResource] = {
    "shor_rsa_2048": ApplicationResource(
        "shor_rsa_2048", 2048, 20_000_000, 3_000_000_000, 28_800
    ),
    "grover_aes_256": ApplicationResource(
        "grover_aes_256", 3000, 2_643_000, 100_000_000_000, 1_000_000
    ),
    "chemistry_femoco": ApplicationResource(
        "chemistry_femoco", 100, 88_100, 10_000_000_000, 100_000
    ),
    "qaoa": ApplicationResource("qaoa", 1000, 881_000, 100_000, 10_000),
    "boson_sampling": ApplicationResource(
        "boson_sampling",
        100,
        100,
        1000,
        1e-3,
        notes="photonic estimate; not a transmon surface-code workload",
    ),
}


@dataclass(frozen=True)
class ScalingResult:
    logical_qubits: int
    code_distance: int
    physical_qubits: int
    qubits_per_refrigerator: int
    refrigerators: int
    total_wall_power_w: float
    total_cost_usd: float
    runtime_s: float
    evidence_state: EvidenceState = EvidenceState.MODELLED


@dataclass(frozen=True)
class ScalingModel:
    qubits_per_refrigerator: Mapping[str, int] = field(
        default_factory=lambda: {"current": 100, "cryo_cmos": 10_000, "scaled": 100_000}
    )
    power_per_refrigerator_w: float = 10_000.0
    cost_per_refrigerator_usd: float = 1_000_000.0

    def calculate(
        self,
        logical_qubits: int,
        code_distance: int,
        refrigerator_technology: str,
        logical_depth: int | None = None,
        logical_gate_time_s: float = 10e-6,
    ) -> ScalingResult:
        if logical_qubits < 1 or logical_depth is not None and logical_depth < 1:
            raise ValueError("logical qubits and depth must be >= 1")
        if refrigerator_technology not in self.qubits_per_refrigerator:
            raise ValueError("unknown refrigerator technology")
        code = SurfaceCode(code_distance)
        physical = logical_qubits * code.physical_qubits
        capacity = self.qubits_per_refrigerator[refrigerator_technology]
        refrigerators = math.ceil(physical / capacity)
        depth = logical_depth if logical_depth is not None else logical_qubits * 1_000_000
        return ScalingResult(
            logical_qubits,
            code_distance,
            physical,
            capacity,
            refrigerators,
            refrigerators * self.power_per_refrigerator_w,
            refrigerators * self.cost_per_refrigerator_usd,
            depth * _positive("logical_gate_time_s", logical_gate_time_s),
        )


@dataclass(frozen=True)
class ThresholdEvaluation:
    physical_error_below_threshold: bool
    physical_qubit_minimum: bool
    coherence_budget: bool
    decoder_budget: bool

    @property
    def all_crossed(self) -> bool:
        return all(asdict(self).values())


@dataclass(frozen=True)
class EvidenceRecord:
    category: str
    state: EvidenceState
    artifact_digest: str
    source: str
    observed_at: str

    def __post_init__(self) -> None:
        if not self.category.strip() or not self.source.strip() or not self.observed_at.strip():
            raise ValueError("evidence category, source, and observed_at are required")
        digest = self.artifact_digest.lower()
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise ValueError("artifact_digest must be a 64-character SHA-256 hex digest")


SOFTWARE_EVIDENCE = ("software_tests", "independent_model_review")
PHYSICAL_EVIDENCE = (
    "cryogenic_measurements",
    "qubit_chip_measurements",
    "decoder_hardware_measurements",
    "control_stack_measurements",
    "logical_qubit_demonstration",
    "application_execution",
)


@dataclass(frozen=True)
class ProductionEvidence:
    records: tuple[EvidenceRecord, ...] = ()

    def __post_init__(self) -> None:
        categories = [record.category for record in self.records]
        if len(categories) != len(set(categories)):
            raise ValueError("evidence categories must be unique")

    def record(self, category: str) -> EvidenceRecord | None:
        return next((item for item in self.records if item.category == category), None)

    @property
    def software_model_ready(self) -> bool:
        tests = self.record("software_tests")
        review = self.record("independent_model_review")
        return bool(
            tests
            and tests.state in {EvidenceState.MEASURED, EvidenceState.INDEPENDENTLY_REPRODUCED}
            and review
            and review.state is EvidenceState.INDEPENDENTLY_REPRODUCED
        )

    @property
    def physical_stack_ready(self) -> bool:
        if not self.software_model_ready:
            return False
        return all(
            (record := self.record(category)) is not None
            and record.state
            in {EvidenceState.MEASURED, EvidenceState.INDEPENDENTLY_REPRODUCED}
            for category in PHYSICAL_EVIDENCE
        )

    @property
    def missing(self) -> tuple[str, ...]:
        required = SOFTWARE_EVIDENCE + PHYSICAL_EVIDENCE
        return tuple(category for category in required if self.record(category) is None)


MATHEMATICAL_EVIDENCE = (
    "software_tests",
    "independent_model_review",
    "unitarity_verification",
    "normalization_verification",
    "error_correction_invariants",
    "deterministic_replay",
    "deterministic_hashrate_verification",
)


@dataclass(frozen=True)
class MathematicalEvidence:
    """Hash-addressed proof evidence for the executable abstraction."""

    records: tuple[EvidenceRecord, ...] = ()

    def __post_init__(self) -> None:
        categories = [record.category for record in self.records]
        if len(categories) != len(set(categories)):
            raise ValueError("mathematical evidence categories must be unique")

    def record(self, category: str) -> EvidenceRecord | None:
        return next((item for item in self.records if item.category == category), None)

    @property
    def production_ready(self) -> bool:
        for category in MATHEMATICAL_EVIDENCE:
            record = self.record(category)
            if record is None:
                return False
            if category == "independent_model_review":
                if record.state is not EvidenceState.INDEPENDENTLY_REPRODUCED:
                    return False
            elif record.state not in {
                EvidenceState.MEASURED,
                EvidenceState.INDEPENDENTLY_REPRODUCED,
            }:
                return False
        return True

    @property
    def missing(self) -> tuple[str, ...]:
        return tuple(
            category
            for category in MATHEMATICAL_EVIDENCE
            if self.record(category) is None
        )


@dataclass(frozen=True)
class QuantumAsicStack:
    refrigerator: DilutionRefrigerator = field(default_factory=DilutionRefrigerator)
    coherence: TransmonCoherence = field(default_factory=TransmonCoherence)
    transmon: TransmonQubit = field(default_factory=TransmonQubit)
    coupler: TunableCoupler = field(default_factory=TunableCoupler)
    readout: ReadoutResonator = field(default_factory=ReadoutResonator)
    chip: QuantumChipLayout = field(default_factory=QuantumChipLayout)
    surface_code: SurfaceCode = field(default_factory=SurfaceCode)
    syndrome: SyndromeExtraction = field(default_factory=SyndromeExtraction)
    decoder: Decoder = field(default_factory=Decoder)
    logical: LogicalQubit = field(default_factory=LogicalQubit)
    cryo_cmos: CryoCMOS = field(default_factory=CryoCMOS)
    rsfq: RSFQ = field(default_factory=RSFQ)
    signal_chain: SignalChain = field(default_factory=SignalChain)

    def __post_init__(self) -> None:
        if self.logical.code != self.surface_code:
            raise ValueError("logical qubit and stack must use the same surface code")
        if not math.isclose(self.decoder.cycle_time_s, self.logical.cycle_time_s):
            raise ValueError("decoder and logical qubit cycle times must match")

    def thresholds(self, physical_qubits: int) -> ThresholdEvaluation:
        return ThresholdEvaluation(
            self.surface_code.physical_error_rate < self.surface_code.threshold,
            int(physical_qubits) >= 100_000,
            self.coherence.t2_seconds > 10 * self.decoder.cycle_time_s,
            self.decoder.ready and self.decoder.throughput_bits_s >= 1e12,
        )

    def application(self, name: str) -> ApplicationResource:
        try:
            return APPLICATIONS[name]
        except KeyError as exc:
            raise ValueError(f"unknown application {name!r}") from exc

    def report(
        self,
        *,
        physical_qubits: int = 10_000,
        evidence: ProductionEvidence | None = None,
    ) -> dict[str, Any]:
        evidence = evidence or ProductionEvidence()
        thresholds = self.thresholds(physical_qubits)
        production_ready = evidence.physical_stack_ready and thresholds.all_crossed
        payload = {
            "schema": SCHEMA,
            "truth_class": "deterministic_engineering_model",
            "physical_qpu_present": evidence.physical_stack_ready,
            "physical_qubits_requested": int(physical_qubits),
            "refrigerator": {
                "coldest_temperature_k": self.refrigerator.coldest.temperature_k,
                "coldest_cooling_power_w": self.refrigerator.coldest.cooling_power_w,
            },
            "transmon": self.transmon.report(self.coherence),
            "surface_code": {
                "distance": self.surface_code.distance,
                "physical_per_logical": self.surface_code.physical_qubits,
                "logical_error_rate_model": self.surface_code.logical_error_rate,
            },
            "decoder": {
                "required_input_rate": self.decoder.required_input_rate,
                "configured_throughput": self.decoder.throughput_bits_s,
                "latency_s": self.decoder.latency_s,
                "ready_for_configured_patch": self.decoder.ready,
            },
            "chip": {
                "modelled_capacity": self.chip.qubit_capacity,
                "readout_lines": self.chip.readout_lines,
            },
            "thresholds": {**asdict(thresholds), "all_crossed": thresholds.all_crossed},
            "production": {
                "software_model_ready": evidence.software_model_ready,
                "physical_stack_ready": production_ready,
                "missing_evidence": evidence.missing,
            },
            "claim_boundary": (
                "software model only; physical readiness requires independently measured "
                "refrigeration, QPU, decoder, control, logical-qubit, and application evidence"
            ),
        }
        return {**payload, "report_digest": _digest(payload)}


@dataclass(frozen=True)
class VerificationBundle:
    checks: Mapping[str, bool]
    artifacts: Mapping[str, Any]
    evidence: MathematicalEvidence

    @property
    def verified(self) -> bool:
        return bool(self.checks) and all(self.checks.values())


class FirstPrinciplesVerifier:
    """Execute exact first-principles invariants and issue replayable evidence."""

    @staticmethod
    def _record(category: str, artifact: Any) -> EvidenceRecord:
        return EvidenceRecord(
            category=category,
            state=EvidenceState.MEASURED,
            artifact_digest=_digest(artifact),
            source="PureQuantumMathASIC.FirstPrinciplesVerifier",
            observed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )

    def verify(
        self,
        stack: QuantumAsicStack,
        *,
        header76: bytes = bytes(range(76)),
    ) -> VerificationBundle:
        from .strict_quantum import (
            certify_work_window,
            rational_rotation,
            state_from_bytes,
            verify_certificate,
        )
        from .backends.base import Program
        from .deterministic_hashrate import verify_hashrate_certificate
        from .exact_field_registry import verify_q_zeta_8_registry
        from .surface_code_exact import verify_surface_code_algebra
        from .verify import verify_program_unitarity

        unitary = rational_rotation()
        clifford_program = Program(2).then("h", 0).then("s", 1).then("cnot", 0, 1)
        clifford_unitarity = verify_program_unitarity(clifford_program)
        initial = state_from_bytes(b"first-principles-quantum", dimension=2)
        evolved = initial.apply(unitary)
        probabilities = evolved.born_probabilities()
        certificate_a = certify_work_window(header76, 0, 32)
        certificate_b = certify_work_window(header76, 0, 32)
        code = stack.surface_code
        surface_proof = verify_surface_code_algebra(code.distance)
        distance_31_proof = verify_surface_code_algebra(31)
        field_proof = verify_q_zeta_8_registry()
        deterministic_system = PureQuantumMathASIC(stack).deterministic_hashrate_system()
        hashrate_certificate = deterministic_system.certificate
        heterogeneous_certificate = (
            PureQuantumMathASIC(stack).heterogeneous_hashrate_certificate()
        )

        artifacts = {
            "unitarity_verification": {
                "rational_rotation_field": "Q(i)",
                "rational_rotation_error_sq": str(unitary.unitary_error()),
                "canonical_field": field_proof.canonical_field,
                "field_registry_digest": field_proof.proof_digest,
                "t_phase_norm_is_one": field_proof.t_phase_norm_is_one,
                "clifford_program_digest": clifford_unitarity.program_digest,
                "clifford_checked_pairs": clifford_unitarity.checked_pairs,
                "clifford_state": clifford_unitarity.state,
                "clifford_reason": clifford_unitarity.reason,
            },
            "normalization_verification": {
                "initial_norm_sq": str(initial.norm_sq),
                "evolved_norm_sq": str(evolved.norm_sq),
                "born_sum": str(sum(probabilities)),
            },
            "error_correction_invariants": {
                "distance": code.distance,
                "physical_symbols": code.physical_qubits,
                "correctable_weight": code.correctable_errors,
                "logical_error_rate_model_admitted_to_exact_bundle": False,
                "css_pairs_checked": surface_proof.mixed_pairs_checked,
                "css_noncommuting_pairs": surface_proof.noncommuting_pairs,
                "logical_anticommutation": surface_proof.logicals_anticommute,
                "surface_code_proof_digest": surface_proof.proof_digest,
                "surface_code_convention": surface_proof.convention,
                "distance_31_pairs_checked": distance_31_proof.mixed_pairs_checked,
                "distance_31_correction_bound": distance_31_proof.correction_bound,
                "distance_31_proof_digest": distance_31_proof.proof_digest,
            },
            "deterministic_replay": {
                "certificate_digest": _digest(certificate_a),
                "identical": certificate_a == certificate_b,
                "certificate_valid": verify_certificate(certificate_a),
            },
            "deterministic_hashrate_verification": {
                "certificate_digest": hashrate_certificate.certificate_digest,
                "steady_state_floor_met": hashrate_certificate.steady_state_floor_met,
                "cold_start_floor_met": hashrate_certificate.cold_start_floor_met,
                "truth_class": hashrate_certificate.truth_class,
                "heterogeneous_certificate_digest": (
                    heterogeneous_certificate.certificate_digest
                ),
                "heterogeneous_floor_met": heterogeneous_certificate.floor_met,
            },
        }
        checks = {
            "unitarity_verification": (
                unitary.unitary_error() == 0
                and clifford_unitarity.verified
                and field_proof.verified
            ),
            "normalization_verification": (
                initial.norm_sq == evolved.norm_sq and sum(probabilities) == 1
            ),
            "error_correction_invariants": (
                code.physical_qubits == 2 * code.distance**2 - 1
                and code.correctable_errors == (code.distance - 1) // 2
                and surface_proof.verified
                and surface_proof.correction_bound == code.correctable_errors
                and distance_31_proof.verified
                and distance_31_proof.correction_bound == 15
            ),
            "deterministic_replay": (
                certificate_a == certificate_b and verify_certificate(certificate_a)
            ),
            "deterministic_hashrate_verification": (
                verify_hashrate_certificate(hashrate_certificate)
                and hashrate_certificate.steady_state_floor_met
                and hashrate_certificate.cold_start_floor_met is True
                and heterogeneous_certificate.floor_met
            ),
        }
        checks["software_tests"] = all(checks.values())
        artifacts["software_tests"] = {
            "verifier": "turing.pure_quantum_math_asic.self_check/v1",
            "checks": dict(checks),
        }
        records = tuple(
            self._record(category, artifacts[category])
            for category in (
                "software_tests",
                "unitarity_verification",
                "normalization_verification",
                "error_correction_invariants",
                "deterministic_replay",
                "deterministic_hashrate_verification",
            )
            if checks[category]
        )
        return VerificationBundle(checks, artifacts, MathematicalEvidence(records))


@dataclass(frozen=True)
class PureQuantumMathASIC:
    """First-principles quantum-mathematics implementation.

    The Hamiltonian, state, code, decoder, thermodynamic, and control terms are
    mathematical operators and constraints. They form an executable abstract
    machine; they are not assertions that physical transmons or cryogenics are
    required by the implementation.
    """

    stack: QuantumAsicStack = field(default_factory=QuantumAsicStack)

    def deterministic_hashrate_system(
        self,
        *,
        cold_start_cycles: int = 1_000_000_000,
    ):
        """Build the exact 10 EH/s mathematical-capacity certificate.

        The default uses 1,000,001 formal chips so a one-second cold-start
        window at 1 GHz clears the floor after the 192-cycle pipeline fill.
        """
        from .deterministic_hashrate import DeterministicMiningSystem, FleetDesign

        design = FleetDesign(1_000_001, 10_000, Fraction(1_000_000_000))
        return DeterministicMiningSystem.build(
            design,
            cold_start_cycles=cold_start_cycles,
        )

    def verify_first_principles(self) -> VerificationBundle:
        return FirstPrinciplesVerifier().verify(self.stack)

    def heterogeneous_hashrate_certificate(self):
        """Issue the exact sum-of-classes capacity certificate."""
        from .deterministic_hashrate import (
            FleetClass,
            HeterogeneousFleet,
            PipelineSpec,
            issue_heterogeneous_fleet_certificate,
        )

        fleet = HeterogeneousFleet(
            (
                FleetClass(
                    "fully_packed",
                    500_000,
                    10_000,
                    Fraction(1_000_000_000),
                    PipelineSpec.fully_packed(),
                ),
                FleetClass(
                    "serialized_three_block",
                    1_500_000,
                    10_000,
                    Fraction(1_000_000_000),
                    PipelineSpec.serialized_three_block(),
                ),
            )
        )
        return issue_heterogeneous_fleet_certificate(fleet)

    def report(
        self,
        *,
        logical_scale: int = 10_000,
        evidence: MathematicalEvidence | None = None,
    ) -> dict[str, Any]:
        if int(logical_scale) < 1:
            raise ValueError("logical_scale must be >= 1")
        evidence = evidence or MathematicalEvidence()
        code = self.stack.surface_code
        payload = {
            "schema": "turing.pure_quantum_math_asic/v1",
            "truth_class": "pure_quantum_mathematical_abstraction",
            "physical_qpu_present": False,
            "logical_scale": int(logical_scale),
            "formal_hilbert_dimension": f"2^{int(logical_scale)}",
            "first_principles": {
                "state_space": "Hilbert space over exact/symbolic amplitudes",
                "evolution": "unitary operator or verified exact special form",
                "measurement": "Born-rule projection on declared observables",
                "error_correction": "surface-code algebra and syndrome constraints",
                "decoder": "graph-theoretic correction operator",
                "thermodynamics": "resource-bound constraint algebra",
            },
            "surface_code_invariants": {
                "distance": code.distance,
                "physical_symbols_per_logical": code.physical_qubits,
                "correctable_error_weight": code.correctable_errors,
                "logical_error_model": code.logical_error_rate,
            },
            "production": {
                "mathematical_abstraction_ready": evidence.production_ready,
                "missing_evidence": evidence.missing,
                "hardware_evidence_required": False,
            },
            "claim_boundary": (
                "executable pure-mathematics abstraction; no physical-QPU or "
                "fabricated-silicon claim"
            ),
        }
        return {**payload, "report_digest": _digest(payload)}


__all__ = [
    "APPLICATIONS",
    "ApplicationResource",
    "CryoCMOS",
    "Decoder",
    "DilutionRefrigerator",
    "EvidenceRecord",
    "EvidenceState",
    "FirstPrinciplesVerifier",
    "LogicalQubit",
    "MATHEMATICAL_EVIDENCE",
    "MathematicalEvidence",
    "ProductionEvidence",
    "PureQuantumMathASIC",
    "QuantumAsicStack",
    "QuantumChipLayout",
    "RSFQ",
    "ReadoutResonator",
    "RefrigerationStage",
    "RoomTemperatureControl",
    "SCHEMA",
    "ScalingModel",
    "ScalingResult",
    "SignalChain",
    "SurfaceCode",
    "SyndromeExtraction",
    "ThresholdEvaluation",
    "VerificationBundle",
    "TransmonCoherence",
    "TransmonQubit",
    "TunableCoupler",
    "WiringBudget",
]
