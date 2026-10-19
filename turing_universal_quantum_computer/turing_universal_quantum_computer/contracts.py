"""Immutable, canonical contracts for TURING's additive public API v1.

Programs use the existing native IR; no SDK object or float angle is passed
through the exact boundary. Parameters identify an explicit finite family of
native programs, NOT arbitrary-angle quantum rotations.
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from itertools import product
import json
from math import isfinite, prod
from typing import Any, Callable, Mapping, cast
from .backends.base import Program, Operation
from .exceptions import ParameterValidationError, ResultValidationError

API_SCHEMA = "turing.public_api.v1"
COMPILER_VERSION = "turing.native_admission.v1"


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: object) -> str:
    return sha256(canonical_json(value).encode()).hexdigest()


def snapshot_program(program: Program) -> Program:
    if not isinstance(program, Program):
        raise ParameterValidationError("expected a native Program")
    if type(program.n_qubits) is not int or program.n_qubits < 1:
        raise ParameterValidationError("width must be a positive integer, not bool")
    ops = []
    for op in program.operations:
        if not isinstance(op, Operation) or any(type(q) is not int for q in op.qubits):
            raise ParameterValidationError("invalid native operation")
        ops.append(Operation(op.gate, tuple(op.qubits)))
    return Program(program.n_qubits, tuple(ops))


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class ParameterSpec:
    name: str
    values: tuple[float, ...]
    lower_bound: float | None = None
    upper_bound: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ParameterValidationError("parameter name must be nonempty")
        try:
            vals = tuple(self.values)
        except TypeError as error:
            raise ParameterValidationError(
                "finite domain must be an iterable of numbers"
            ) from error
        if not vals or any(type(v) not in (int, float) or not isfinite(v) for v in vals):
            raise ParameterValidationError(
                "native finite domain must contain finite numeric values"
            )
        vals = tuple(float(v) for v in vals)
        if len(set(vals)) != len(vals):
            raise ParameterValidationError("duplicate domain values")
        for bound in (self.lower_bound, self.upper_bound):
            if bound is not None and (type(bound) not in (int, float) or not isfinite(bound)):
                raise ParameterValidationError("bounds must be finite")
        if (
            self.lower_bound is not None
            and self.upper_bound is not None
            and self.lower_bound > self.upper_bound
        ):
            raise ParameterValidationError("inverted bounds")
        if any(
            (self.lower_bound is not None and v < self.lower_bound)
            or (self.upper_bound is not None and v > self.upper_bound)
            for v in vals
        ):
            raise ParameterValidationError("domain outside bounds")
        object.__setattr__(self, "values", vals)


@dataclass(frozen=True)
class ParameterBindings:
    names: tuple[str, ...] = ()
    values: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        try:
            names, values = tuple(self.names), tuple(self.values)
        except TypeError as error:
            raise ParameterValidationError("names and values must be iterable") from error
        if (
            len(names) != len(values)
            or any(not isinstance(n, str) or not n for n in names)
            or len(set(names)) != len(names)
        ):
            raise ParameterValidationError("names must be unique and match values")
        if any(type(v) not in (int, float) or not isfinite(v) for v in values):
            raise ParameterValidationError("values must be finite real numbers")
        object.__setattr__(self, "names", names)
        object.__setattr__(self, "values", tuple(float(v) for v in values))

    def validate(self, schema: tuple[ParameterSpec, ...]) -> None:
        if self.names != tuple(s.name for s in schema):
            raise ParameterValidationError("parameter identity/order mismatch")
        if any(v not in s.values for s, v in zip(schema, self.values)):
            raise ParameterValidationError("value outside declared finite domain")

    @classmethod
    def from_mapping(
        cls, schema: tuple[ParameterSpec, ...], values: Mapping[str, float]
    ) -> ParameterBindings:
        if set(values) != {s.name for s in schema}:
            raise ParameterValidationError("missing or extra named parameters")
        binding = cls(tuple(s.name for s in schema), tuple(values[s.name] for s in schema))
        binding.validate(schema)
        return binding


@dataclass(frozen=True)
class CircuitIR:
    program: Program
    parameters: tuple[ParameterSpec, ...] = ()
    bindings: ParameterBindings = ParameterBindings()
    family_hash: str | None = None
    ir_version: str = "turing.native_program.v1"

    def __post_init__(self) -> None:
        object.__setattr__(self, "program", snapshot_program(self.program))
        object.__setattr__(self, "parameters", tuple(self.parameters))
        self.bindings.validate(self.parameters)
        if self.ir_version != "turing.native_program.v1":
            raise ParameterValidationError("unsupported IR schema")


@dataclass(frozen=True)
class FiniteAnsatz:
    parameters: tuple[ParameterSpec, ...]
    programs: tuple[Program, ...]

    def __post_init__(self) -> None:
        specs = tuple(self.parameters)
        if len({s.name for s in specs}) != len(specs):
            raise ParameterValidationError("duplicate parameter names")
        programs = tuple(snapshot_program(p) for p in self.programs)
        if len(programs) != prod(len(s.values) for s in specs):
            raise ParameterValidationError("one program required for every finite-domain point")
        if len({p.n_qubits for p in programs}) != 1:
            raise ParameterValidationError("all family members must have the same width")
        object.__setattr__(self, "parameters", specs)
        object.__setattr__(self, "programs", programs)

    @classmethod
    def from_builder(
        cls,
        parameters: tuple[ParameterSpec, ...],
        builder: Callable[[ParameterBindings], Program],
        *,
        max_candidates: int = 4096,
    ) -> FiniteAnsatz:
        parameters = tuple(parameters)
        if type(max_candidates) is not int or max_candidates < 1:
            raise ParameterValidationError("max_candidates must be positive")
        if prod(len(s.values) for s in parameters) > max_candidates:
            raise ParameterValidationError("finite ansatz exceeds materialisation budget")
        names = tuple(s.name for s in parameters)
        return cls(
            parameters,
            tuple(
                builder(ParameterBindings(names, values))
                for values in product(*(s.values for s in parameters))
            ),
        )

    def candidates(self) -> tuple[ParameterBindings, ...]:
        return tuple(
            ParameterBindings(tuple(s.name for s in self.parameters), v)
            for v in product(*(s.values for s in self.parameters))
        )

    def source_hash(self) -> str:
        return digest(
            {
                "schema": API_SCHEMA,
                "parameters": [
                    {
                        "name": s.name,
                        "values": s.values,
                        "lower": s.lower_bound,
                        "upper": s.upper_bound,
                    }
                    for s in self.parameters
                ],
                "programs": [p.to_dict() for p in self.programs],
            }
        )

    def bind(self, parameters: ParameterBindings) -> CircuitIR:
        parameters.validate(self.parameters)
        index = self.candidates().index(parameters)
        return CircuitIR(self.programs[index], self.parameters, parameters, self.source_hash())


@dataclass(frozen=True)
class BackendCapabilities:
    backend_id: str
    max_qubits: int = 10_000
    max_amplitudes: int = 1 << 20
    execution_kind: str = "turing_vqc"
    supported_backends: tuple[str, ...] = ("exact_algebraic", "stabilizer")
    supports_finite_parameters: bool = True
    supports_continuous_angles: bool = False
    supports_dynamic_control: bool = False
    supports_pulse_control: bool = False
    supports_fault_tolerant_execution: bool = False
    supports_physical_qpu: bool = False
    supports_parameter_batches: bool = False
    observable_kinds: tuple[str, ...] = ("single_qubit_z",)
    job_persistence: str = "in_memory_process_local"


@dataclass(frozen=True)
class CompiledArtifact:
    ir: CircuitIR
    backend_id: str
    config_json: str
    source_hash: str
    layout: tuple[tuple[int, int], ...]
    implementation_hash: str
    compiler_version: str = COMPILER_VERSION
    api_schema: str = API_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "layout", tuple(tuple(pair) for pair in self.layout))
        expected = tuple((q, q) for q in range(self.ir.program.n_qubits))
        if self.layout != expected:
            raise ParameterValidationError("v1 native compiler requires an identity layout")
        if self.source_hash != self.ir.program.digest():
            raise ParameterValidationError("source digest mismatch")
        if self.compiler_version != COMPILER_VERSION or self.api_schema != API_SCHEMA:
            raise ParameterValidationError("unsupported compiler/API version")
        if not isinstance(json.loads(self.config_json), dict):
            raise ParameterValidationError("invalid compiler configuration")

    @property
    def parameter_names(self) -> tuple[str, ...]:
        return self.ir.bindings.names

    @property
    def artifact_hash(self) -> str:
        return digest(
            {
                "source": self.source_hash,
                "backend": self.backend_id,
                "compiler": self.compiler_version,
                "implementation": self.implementation_hash,
                "schema": self.api_schema,
                "config": json.loads(self.config_json),
                "layout": self.layout,
                "parameters": self.ir.bindings.values,
                "names": self.parameter_names,
                "parameter_schema": [
                    {
                        "name": p.name,
                        "values": p.values,
                        "lower": p.lower_bound,
                        "upper": p.upper_bound,
                    }
                    for p in self.ir.parameters
                ],
                "family": self.ir.family_hash,
            }
        )


@dataclass(frozen=True)
class PauliZ:
    qubit: int

    def __post_init__(self) -> None:
        if type(self.qubit) is not int or self.qubit < 0:
            raise ParameterValidationError("observable qubit must be a nonnegative integer")


@dataclass(frozen=True)
class ExecutionRequest:
    artifact: CompiledArtifact
    parameters: ParameterBindings = ParameterBindings()
    observable: PauliZ | None = None
    readout: tuple[int, ...] | None = None

    def __post_init__(self) -> None:
        self.parameters.validate(self.artifact.ir.parameters)
        if self.parameters != self.artifact.ir.bindings:
            raise ParameterValidationError("artifact is bound; recompile changed parameter values")
        if self.observable is not None and (
            not isinstance(self.observable, PauliZ)
            or self.observable.qubit >= self.artifact.ir.program.n_qubits
        ):
            raise ParameterValidationError("unsupported or out-of-range observable")
        if self.readout is not None:
            readout = tuple(self.readout)
            if (
                not readout
                or len(set(readout)) != len(readout)
                or any(
                    type(q) is not int or not 0 <= q < self.artifact.ir.program.n_qubits
                    for q in readout
                )
            ):
                raise ParameterValidationError("invalid readout")
            object.__setattr__(self, "readout", readout)

    @property
    def request_hash(self) -> str:
        return digest(
            {
                "artifact": self.artifact.artifact_hash,
                "observable": None if self.observable is None else self.observable.qubit,
                "readout": self.readout,
            }
        )


@dataclass(frozen=True)
class JobResult:
    job_id: str
    request_hash: str
    report_json: str

    def report(self) -> dict[str, Any]:
        return cast(
            dict[str, Any], json.loads(self.report_json)
        )  # fresh copy, never mutable shared evidence


@dataclass(frozen=True)
class Estimate:
    value: float
    standard_error: float
    shots: int | None
    observable: PauliZ
    uncertainty_method: str
    exact_value: str
    exact_coefficients: tuple[str, str]
    job_result: JobResult

    def __post_init__(self) -> None:
        if not isfinite(self.value) or not isfinite(self.standard_error) or self.standard_error < 0:
            raise ResultValidationError("non-finite/invalid estimate")


@dataclass(frozen=True)
class Evaluation:
    parameters: ParameterBindings
    estimate: Estimate


@dataclass(frozen=True)
class OptimizationResult:
    parameters: ParameterBindings
    objective_value: float
    converged: bool
    iterations: int
    termination_reason: str
    history: tuple[Evaluation, ...]
    search_domain: str = "declared_finite_ansatz_only"
