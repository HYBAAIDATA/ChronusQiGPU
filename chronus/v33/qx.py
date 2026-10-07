"""Typed, fail-closed QX command model and deterministic reference executor.

QX is the command boundary between Chronus mathematical workloads and execution
substrates.  This module implements the substrate-independent contract.  Hardware
backends may consume the same sealed command buffer, but must preserve its digest,
validation rules, mathematical invariants, and execution provenance.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence

import numpy as np


class QXValidationError(ValueError):
    """Raised when a command buffer violates the QX execution contract."""


class QXCommandType(str, Enum):
    ALLOCATE_CAVITY_REGION = "allocate_cavity_region"
    SET_HAMILTONIAN = "set_hamiltonian"
    EVOLVE = "evolve"
    WEAK_MEASURE = "weak_measure"
    APPLY_CORRECTION = "apply_correction"
    READ_EXPECTATION = "read_expectation"
    SYNCHRONIZE = "synchronize"
    MEMORY_BARRIER = "memory_barrier"
    DESCRIPTOR_SET_BIND = "descriptor_set_bind"


class QXPipelineStage(str, Enum):
    COMPILE = "compile"
    STATE_PREP = "state_prep"
    EVOLUTION = "evolution"
    READOUT = "readout"
    RECONSTRUCT = "reconstruct"


class QXMemoryDomain(str, Enum):
    ALL = "all"
    CAVITY = "cavity"
    CLASSICAL = "classical"


@dataclass(frozen=True)
class QXCommand:
    operation: QXCommandType
    payload: Mapping[str, Any] = field(default_factory=dict)


def _matrix(value: Any, name: str) -> np.ndarray:
    matrix = np.asarray(value, dtype=np.complex128)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1] or matrix.shape[0] == 0:
        raise QXValidationError(f"{name} must be a non-empty square matrix")
    if not np.all(np.isfinite(matrix.real)) or not np.all(np.isfinite(matrix.imag)):
        raise QXValidationError(f"{name} must contain only finite values")
    return np.array(matrix, dtype=np.complex128, order="C", copy=True)


def _require_hermitian(matrix: np.ndarray, name: str, tolerance: float) -> None:
    if not np.allclose(matrix, matrix.conj().T, atol=tolerance, rtol=0.0):
        raise QXValidationError(f"{name} must be Hermitian within atol={tolerance}")


def _canonical(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        array = np.ascontiguousarray(value)
        return {
            "array_dtype": str(array.dtype),
            "array_shape": list(array.shape),
            "array_sha256": hashlib.sha256(array.tobytes(order="C")).hexdigest(),
        }
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _canonical(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise QXValidationError(f"unsupported command payload type: {type(value).__name__}")


def _copy_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    copied: Dict[str, Any] = {}
    for key, value in payload.items():
        copied[key] = np.array(value, copy=True) if isinstance(value, np.ndarray) else copy.deepcopy(value)
    return copied


class QXCommandBuffer:
    """Append-only command buffer that becomes immutable after ``seal``."""

    def __init__(self, hermitian_tolerance: float = 1e-10):
        if hermitian_tolerance <= 0 or not np.isfinite(hermitian_tolerance):
            raise QXValidationError("hermitian_tolerance must be finite and positive")
        self.hermitian_tolerance = float(hermitian_tolerance)
        self._commands: List[QXCommand] = []
        self._sealed = False
        self._digest: Optional[str] = None

    @property
    def commands(self) -> Sequence[QXCommand]:
        return tuple(self._commands)

    @property
    def sealed(self) -> bool:
        return self._sealed

    @property
    def digest(self) -> str:
        if self._digest is None:
            raise QXValidationError("command buffer has not been sealed")
        return self._digest

    def _record(self, operation: QXCommandType, **payload: Any) -> "QXCommandBuffer":
        if self._sealed:
            raise QXValidationError("sealed command buffers are immutable")
        self._commands.append(QXCommand(operation=operation, payload=_copy_payload(payload)))
        return self

    def allocate_cavity_region(self, dimension: int, region_id: str = "primary") -> "QXCommandBuffer":
        if isinstance(dimension, bool) or int(dimension) != dimension or dimension <= 0:
            raise QXValidationError("dimension must be a positive integer")
        if not region_id or not isinstance(region_id, str):
            raise QXValidationError("region_id must be a non-empty string")
        return self._record(
            QXCommandType.ALLOCATE_CAVITY_REGION,
            dimension=int(dimension),
            region_id=region_id,
        )

    def set_hamiltonian(self, hamiltonian: Any) -> "QXCommandBuffer":
        matrix = _matrix(hamiltonian, "hamiltonian")
        _require_hermitian(matrix, "hamiltonian", self.hermitian_tolerance)
        return self._record(QXCommandType.SET_HAMILTONIAN, matrix=matrix)

    def evolve(self, dt: float) -> "QXCommandBuffer":
        if not np.isfinite(dt) or dt <= 0:
            raise QXValidationError("evolution dt must be finite and positive")
        return self._record(QXCommandType.EVOLVE, dt=float(dt))

    def weak_measure(self, observable: Any, epsilon: float, probe_id: str) -> "QXCommandBuffer":
        matrix = _matrix(observable, "observable")
        _require_hermitian(matrix, "observable", self.hermitian_tolerance)
        if not np.isfinite(epsilon) or epsilon <= 0 or epsilon > 0.01:
            raise QXValidationError("weak-measurement epsilon must satisfy 0 < epsilon <= 0.01")
        if not probe_id or not isinstance(probe_id, str):
            raise QXValidationError("probe_id must be a non-empty string")
        return self._record(
            QXCommandType.WEAK_MEASURE,
            observable=matrix,
            epsilon=float(epsilon),
            probe_id=probe_id,
        )

    def apply_correction(self, unitary: Any, correction_id: str) -> "QXCommandBuffer":
        matrix = _matrix(unitary, "correction unitary")
        identity = np.eye(matrix.shape[0], dtype=np.complex128)
        if not np.allclose(matrix.conj().T @ matrix, identity, atol=1e-10, rtol=0.0):
            raise QXValidationError("correction matrix must be unitary within atol=1e-10")
        if not correction_id or not isinstance(correction_id, str):
            raise QXValidationError("correction_id must be a non-empty string")
        return self._record(
            QXCommandType.APPLY_CORRECTION,
            unitary=matrix,
            correction_id=correction_id,
        )

    def read_expectation(self, observable: Any, result_id: str) -> "QXCommandBuffer":
        matrix = _matrix(observable, "observable")
        _require_hermitian(matrix, "observable", self.hermitian_tolerance)
        if not result_id or not isinstance(result_id, str):
            raise QXValidationError("result_id must be a non-empty string")
        return self._record(
            QXCommandType.READ_EXPECTATION,
            observable=matrix,
            result_id=result_id,
        )

    def synchronize(self, event_id: str) -> "QXCommandBuffer":
        if not event_id or not isinstance(event_id, str):
            raise QXValidationError("event_id must be a non-empty string")
        return self._record(QXCommandType.SYNCHRONIZE, event_id=event_id)

    def memory_barrier(self, domain: QXMemoryDomain) -> "QXCommandBuffer":
        try:
            resolved = domain if isinstance(domain, QXMemoryDomain) else QXMemoryDomain(domain)
        except ValueError as exc:
            raise QXValidationError(f"unknown memory domain: {domain}") from exc
        return self._record(QXCommandType.MEMORY_BARRIER, domain=resolved)

    def bind_descriptor_set(self, set_id: str, bindings: Mapping[str, Any]) -> "QXCommandBuffer":
        if not set_id or not isinstance(set_id, str):
            raise QXValidationError("set_id must be a non-empty string")
        if not isinstance(bindings, Mapping):
            raise QXValidationError("descriptor bindings must be a mapping")
        _canonical(bindings)
        return self._record(
            QXCommandType.DESCRIPTOR_SET_BIND,
            set_id=set_id,
            bindings=dict(bindings),
        )

    def seal(self) -> str:
        if not self._commands:
            raise QXValidationError("cannot seal an empty command buffer")
        document = {
            "qx_contract": "1.0",
            "hermitian_tolerance": self.hermitian_tolerance,
            "commands": [
                {"operation": command.operation.value, "payload": _canonical(command.payload)}
                for command in self._commands
            ],
        }
        encoded = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self._digest = hashlib.sha256(encoded).hexdigest()
        self._sealed = True
        return self._digest


@dataclass(frozen=True)
class QXExecutionReport:
    command_digest: str
    backend: str
    precision: str
    dimension: int
    commands_executed: int
    barrier_epoch: int
    event_ids: tuple
    expectations: Mapping[str, float]
    weak_measurements: Mapping[str, float]
    descriptor_sets: Mapping[str, Mapping[str, Any]]
    final_state_sha256: str
    norm_error: float


class QXReferenceExecutor:
    """Deterministic complex128 executor for QX conformance and backend comparison."""

    def __init__(self, invariant_tolerance: float = 1e-10):
        if invariant_tolerance <= 0 or not np.isfinite(invariant_tolerance):
            raise QXValidationError("invariant_tolerance must be finite and positive")
        self.invariant_tolerance = float(invariant_tolerance)

    def execute(self, command_buffer: QXCommandBuffer) -> QXExecutionReport:
        if not command_buffer.sealed:
            raise QXValidationError("execution requires a sealed command buffer")

        dimension: Optional[int] = None
        state: Optional[np.ndarray] = None
        hamiltonian: Optional[np.ndarray] = None
        expectations: Dict[str, float] = {}
        weak_measurements: Dict[str, float] = {}
        descriptor_sets: Dict[str, Mapping[str, Any]] = {}
        event_ids: List[str] = []
        barrier_epoch = 0

        for index, command in enumerate(command_buffer.commands):
            payload = command.payload
            operation = command.operation

            if operation is QXCommandType.ALLOCATE_CAVITY_REGION:
                if dimension is not None:
                    raise QXValidationError("reference executor supports exactly one cavity region")
                dimension = int(payload["dimension"])
                state = np.zeros(dimension, dtype=np.complex128)
                state[0] = 1.0
                continue

            if dimension is None or state is None:
                raise QXValidationError(f"command {index} requires an allocated cavity region")

            if operation is QXCommandType.SET_HAMILTONIAN:
                candidate = _matrix(payload["matrix"], "hamiltonian")
                _require_hermitian(
                    candidate,
                    "hamiltonian",
                    command_buffer.hermitian_tolerance,
                )
                self._require_dimension(candidate, dimension, "hamiltonian")
                hamiltonian = candidate
            elif operation is QXCommandType.EVOLVE:
                if hamiltonian is None:
                    raise QXValidationError("evolve requires a Hamiltonian")
                eigenvalues, eigenvectors = np.linalg.eigh(hamiltonian)
                phases = np.exp(-1j * eigenvalues * float(payload["dt"]))
                state = eigenvectors @ (phases * (eigenvectors.conj().T @ state))
                self._require_normalized(state)
            elif operation is QXCommandType.WEAK_MEASURE:
                observable = _matrix(payload["observable"], "observable")
                self._require_dimension(observable, dimension, "observable")
                value = np.vdot(state, observable @ state)
                if abs(value.imag) > self.invariant_tolerance:
                    raise QXValidationError("Hermitian expectation acquired an imaginary component")
                weak_measurements[str(payload["probe_id"])] = float(value.real)
            elif operation is QXCommandType.APPLY_CORRECTION:
                unitary = _matrix(payload["unitary"], "correction unitary")
                self._require_dimension(unitary, dimension, "correction unitary")
                state = unitary @ state
                self._require_normalized(state)
            elif operation is QXCommandType.READ_EXPECTATION:
                observable = _matrix(payload["observable"], "observable")
                self._require_dimension(observable, dimension, "observable")
                value = np.vdot(state, observable @ state)
                if abs(value.imag) > self.invariant_tolerance:
                    raise QXValidationError("Hermitian expectation acquired an imaginary component")
                expectations[str(payload["result_id"])] = float(value.real)
            elif operation is QXCommandType.SYNCHRONIZE:
                event_ids.append(str(payload["event_id"]))
            elif operation is QXCommandType.MEMORY_BARRIER:
                barrier_epoch += 1
            elif operation is QXCommandType.DESCRIPTOR_SET_BIND:
                descriptor_sets[str(payload["set_id"])] = copy.deepcopy(payload["bindings"])
            else:
                raise QXValidationError(f"unsupported QX command: {operation}")

        if dimension is None or state is None:
            raise QXValidationError("command buffer did not allocate a cavity region")
        norm_error = abs(float(np.vdot(state, state).real) - 1.0)
        self._require_normalized(state)
        state_bytes = np.ascontiguousarray(state, dtype=np.complex128).tobytes(order="C")
        return QXExecutionReport(
            command_digest=command_buffer.digest,
            backend="chronus.qx.reference",
            precision="complex128/float64",
            dimension=dimension,
            commands_executed=len(command_buffer.commands),
            barrier_epoch=barrier_epoch,
            event_ids=tuple(event_ids),
            expectations=dict(expectations),
            weak_measurements=dict(weak_measurements),
            descriptor_sets=descriptor_sets,
            final_state_sha256=hashlib.sha256(state_bytes).hexdigest(),
            norm_error=norm_error,
        )

    @staticmethod
    def _require_dimension(matrix: np.ndarray, dimension: int, name: str) -> None:
        if matrix.shape != (dimension, dimension):
            raise QXValidationError(
                f"{name} shape {matrix.shape} does not match cavity dimension {dimension}"
            )

    def _require_normalized(self, state: np.ndarray) -> None:
        norm_error = abs(float(np.vdot(state, state).real) - 1.0)
        if norm_error > self.invariant_tolerance:
            raise QXValidationError(
                f"state norm invariant failed: error={norm_error:.3e}, "
                f"tolerance={self.invariant_tolerance:.3e}"
            )
