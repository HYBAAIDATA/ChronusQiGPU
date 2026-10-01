"""Compression-aware tensor and quantum-operator execution for Kellogg.

The July compressed-tensor API is retained with corrected complex-value and
coherent-interference semantics. Tensor-train and MPS truncation are explicit
lossy representations with measured errors. ``NONE`` is the lossless control.
No method claims physical quantum hardware, physical compression or consensus
authority.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Sequence

import numpy as np

from .tensor_network import TensorNetworkError, TensorTrain, mps_decompose


class CompressedTensorError(ValueError):
    """A compressed-tensor or quantum-operator contract was violated."""


class CompressionScheme(Enum):
    NONE = "none"
    TENSOR_TRAIN = "tensor_train"
    MPS = "mps"
    PULVINI_FOLD = "pulvini_fold"


class Precision(Enum):
    FP64 = "float64"
    FP32 = "float32"
    COMPLEX128 = "complex128"
    COMPLEX64 = "complex64"


class OperatorType(Enum):
    UNITARY = "unitary"
    KRAUS = "kraus"
    MIXING = "mixing"
    PROJECTIVE = "projective"


def _finite_array(value: Any) -> np.ndarray:
    arr = np.asarray(value)
    if arr.size == 0 or arr.dtype.kind not in "biufc":
        raise CompressedTensorError("tensor must be non-empty and numeric")
    if not np.all(np.isfinite(arr)):
        raise CompressedTensorError("tensor must contain only finite values")
    return arr.astype(np.complex128 if np.iscomplexobj(arr) else np.float64, copy=False)


def _precision_for(array: np.ndarray, requested: Precision | None) -> Precision:
    if requested is not None:
        return Precision(requested)
    return Precision.COMPLEX128 if np.iscomplexobj(array) else Precision.FP64


@dataclass
class CompressedTensor:
    raw_storage: Any
    compression_scheme: CompressionScheme
    logical_shape: tuple[int, ...]
    precision: Precision
    original_dtype: str
    reconstruction_error: float = 0.0
    fidelity_guarantee: float = 1.0
    entropy_estimate: float = 0.0
    trace_norm: float = 0.0
    ranks: tuple[int, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def storage_bytes(self) -> int:
        if isinstance(self.raw_storage, np.ndarray):
            return int(self.raw_storage.nbytes)
        if isinstance(self.raw_storage, Sequence):
            return sum(int(np.asarray(value).nbytes) for value in self.raw_storage)
        return 0

    @property
    def logical_bytes(self) -> int:
        return math.prod(self.logical_shape) * np.dtype(self.original_dtype).itemsize

    @property
    def compression_ratio(self) -> float:
        return self.logical_bytes / max(1, self.storage_bytes)

    def metadata_dict(self) -> dict[str, Any]:
        return {
            "compression_scheme": self.compression_scheme.value,
            "logical_shape": list(self.logical_shape),
            "precision": self.precision.value,
            "original_dtype": self.original_dtype,
            "storage_bytes": self.storage_bytes,
            "logical_bytes": self.logical_bytes,
            "representation_ratio": self.compression_ratio,
            "reconstruction_error": self.reconstruction_error,
            "fidelity_guarantee": self.fidelity_guarantee,
            "entropy_estimate": self.entropy_estimate,
            "trace_norm": self.trace_norm,
            "ranks": list(self.ranks),
            "claim_boundary": "representation accounting; not physical compression",
            **self.metadata,
        }


@dataclass
class QuantumState:
    tensor: CompressedTensor
    norm: float = 1.0
    phase_metadata: dict[str, Any] = field(default_factory=dict)

    def metadata_dict(self) -> dict[str, Any]:
        return {
            "norm": self.norm,
            "phase_metadata": dict(self.phase_metadata),
            "tensor": self.tensor.metadata_dict(),
        }


@dataclass
class QuantumOperator:
    op_type: OperatorType
    kernel: np.ndarray | None = None
    kraus_operators: Sequence[np.ndarray] = ()
    mixing_channel: np.ndarray | None = None
    mixing_probability: float = 0.0
    measurement_basis: np.ndarray | None = None
    compression_aware: bool = True
    error_bound: float = 0.0

    def metadata_dict(self) -> dict[str, Any]:
        return {
            "op_type": self.op_type.value,
            "kernel_shape": list(np.asarray(self.kernel).shape) if self.kernel is not None else [],
            "n_kraus": len(self.kraus_operators),
            "compression_aware": self.compression_aware,
            "error_bound": self.error_bound,
            "mixing_probability": self.mixing_probability,
        }


@dataclass
class ExpertRouter:
    routing_fn: Callable[[np.ndarray], Sequence[tuple[int, complex]]]
    n_experts: int = 0
    top_k: int = 0

    def route(self, density: np.ndarray) -> tuple[list[int], list[complex]]:
        routed = list(self.routing_fn(density))
        if self.top_k > 0:
            routed = sorted(routed, key=lambda item: abs(item[1]), reverse=True)[: self.top_k]
        if self.n_experts and any(not 0 <= int(index) < self.n_experts for index, _ in routed):
            raise CompressedTensorError("router returned an expert outside its declared range")
        return [int(index) for index, _ in routed], [complex(weight) for _, weight in routed]


@dataclass(frozen=True)
class MeasurementResult:
    outcome: int
    probabilities: np.ndarray
    post_measurement_state: QuantumState | None = None


@dataclass(frozen=True)
class EngineConfig:
    max_quantum_dim: int = 2**16
    default_precision: Precision | None = None
    default_compression: CompressionScheme = CompressionScheme.TENSOR_TRAIN
    default_max_rank: int = 64
    default_tolerance: float = 0.0
    cptp_tolerance: float = 1e-10
    interference_tolerance: float = 1e-12
    require_finite: bool = True


class QuantumCompressedTensorEngine:
    """Kellogg compression-aware operator engine on a classical substrate."""

    def __init__(self, config: EngineConfig | None = None) -> None:
        self.config = config or EngineConfig()
        if self.config.max_quantum_dim < 1 or self.config.default_max_rank < 1:
            raise CompressedTensorError("engine dimensions and ranks must be positive")

    def allocate_compressed_tensor(
        self,
        shape: tuple[int, ...],
        precision: Precision | None = None,
        scheme: CompressionScheme | None = None,
    ) -> CompressedTensor:
        if not shape or any(int(v) < 1 for v in shape):
            raise CompressedTensorError("shape dimensions must be positive")
        chosen = precision or self.config.default_precision or Precision.FP64
        dtype = np.dtype(chosen.value)
        return self.load_tensor_from_host(
            np.zeros(shape, dtype=dtype), scheme=scheme or CompressionScheme.NONE
        )

    def load_tensor_from_host(
        self,
        host_tensor: np.ndarray,
        scheme: CompressionScheme | None = None,
        depth: int | None = None,
        *,
        max_rank: int | None = None,
        tolerance: float | None = None,
    ) -> CompressedTensor:
        del depth
        array = _finite_array(host_tensor)
        if array.size > self.config.max_quantum_dim:
            raise CompressedTensorError(
                f"dimension {array.size} exceeds max_quantum_dim {self.config.max_quantum_dim}"
            )
        chosen = CompressionScheme(scheme or self.config.default_compression)
        precision = _precision_for(array, self.config.default_precision)
        rank = max_rank or self.config.default_max_rank
        tol = self.config.default_tolerance if tolerance is None else float(tolerance)
        if chosen is CompressionScheme.NONE:
            storage: Any = array.copy()
            ranks: tuple[int, ...] = ()
            error = 0.0
        elif chosen is CompressionScheme.TENSOR_TRAIN:
            train = TensorTrain(array, max_rank=rank, tolerance=tol)
            storage = [core.copy() for core in train.cores]
            ranks = tuple(train.ranks)
            error = train.relative_error(array)
        elif chosen is CompressionScheme.MPS:
            log_dim = math.log2(array.size)
            if not log_dim.is_integer():
                raise CompressedTensorError("MPS requires a flattened power-of-two state size")
            storage = mps_decompose(array.reshape(-1), int(log_dim), rank)
            train = TensorTrain.from_cores(storage)
            ranks = tuple(train.ranks)
            reconstructed = train.reconstruct().reshape(array.shape)
            denominator = float(np.linalg.norm(array.ravel()))
            numerator = float(np.linalg.norm((array - reconstructed).ravel()))
            error = numerator / denominator if denominator else numerator
        elif chosen is CompressionScheme.PULVINI_FOLD:
            raise CompressedTensorError(
                "PULVINI_FOLD custody is owned by Aethel; use its bridge before loading Kellogg"
            )
        else:  # pragma: no cover - Enum closes this path
            raise CompressedTensorError(f"unsupported compression scheme: {chosen}")
        return CompressedTensor(
            raw_storage=storage,
            compression_scheme=chosen,
            logical_shape=tuple(int(v) for v in array.shape),
            precision=precision,
            original_dtype=array.dtype.str,
            reconstruction_error=error,
            fidelity_guarantee=max(0.0, 1.0 - error),
            entropy_estimate=self._entropy(array),
            trace_norm=self._trace_norm(array),
            ranks=ranks,
        )

    def decompress_to_registers(self, tensor: CompressedTensor) -> np.ndarray:
        if tensor.compression_scheme is CompressionScheme.NONE:
            return np.asarray(tensor.raw_storage).copy().reshape(tensor.logical_shape)
        if tensor.compression_scheme is CompressionScheme.TENSOR_TRAIN:
            return TensorTrain.from_cores(
                tensor.raw_storage, original_shape=tensor.logical_shape
            ).reconstruct()
        if tensor.compression_scheme is CompressionScheme.MPS:
            return TensorTrain.from_cores(tensor.raw_storage).reconstruct().reshape(
                tensor.logical_shape
            )
        raise CompressedTensorError(f"unsupported compression scheme: {tensor.compression_scheme}")

    def recompress_from_registers(
        self, registers: np.ndarray, tensor: CompressedTensor
    ) -> CompressedTensor:
        return self.load_tensor_from_host(
            registers,
            scheme=tensor.compression_scheme,
            max_rank=max(tensor.ranks, default=self.config.default_max_rank),
            tolerance=self.config.default_tolerance,
        )

    def apply_quantum_operator(
        self, state: QuantumState, operator: QuantumOperator
    ) -> QuantumState:
        raw = self.decompress_to_registers(state.tensor)
        density = self._as_density(raw)
        op_type = OperatorType(operator.op_type)
        if op_type is OperatorType.UNITARY:
            unitary = _finite_array(operator.kernel).astype(complex)
            self._require_square(unitary, density.shape[0], "unitary")
            residual = np.linalg.norm(unitary.conj().T @ unitary - np.eye(unitary.shape[0]))
            if residual > self.config.cptp_tolerance:
                raise CompressedTensorError(f"unitary residual {residual:.3e} exceeds tolerance")
            output = unitary @ density @ unitary.conj().T
        elif op_type is OperatorType.KRAUS:
            if not operator.kraus_operators:
                raise CompressedTensorError("Kraus operator list cannot be empty")
            output = np.zeros_like(density, dtype=complex)
            completeness = np.zeros_like(density, dtype=complex)
            for value in operator.kraus_operators:
                kraus = _finite_array(value).astype(complex)
                self._require_square(kraus, density.shape[0], "Kraus")
                output += kraus @ density @ kraus.conj().T
                completeness += kraus.conj().T @ kraus
            if np.linalg.norm(completeness - np.eye(density.shape[0])) > self.config.cptp_tolerance:
                raise CompressedTensorError("Kraus operators are not trace preserving")
        elif op_type is OperatorType.MIXING:
            probability = float(operator.mixing_probability)
            if not 0.0 <= probability <= 1.0:
                raise CompressedTensorError("mixing probability must lie in [0, 1]")
            channel = (
                np.eye(density.shape[0], dtype=complex) / density.shape[0]
                if operator.mixing_channel is None
                else _finite_array(operator.mixing_channel).astype(complex)
            )
            self._require_square(channel, density.shape[0], "mixing channel")
            output = (1.0 - probability) * density + probability * channel
        else:
            basis = (
                np.eye(density.shape[0], dtype=complex)
                if operator.measurement_basis is None
                else _finite_array(operator.measurement_basis).astype(complex)
            )
            self._require_square(basis, density.shape[0], "measurement basis")
            output = np.zeros_like(density, dtype=complex)
            for column in basis.T:
                projector = np.outer(column, column.conj())
                output += projector @ density @ projector
        output = self._enforce_density(output)
        compressed = self.load_tensor_from_host(
            output,
            scheme=state.tensor.compression_scheme,
            max_rank=max(state.tensor.ranks, default=self.config.default_max_rank),
        )
        phase = dict(state.phase_metadata)
        phase["last_operator"] = op_type.value
        return QuantumState(compressed, norm=float(np.trace(output).real), phase_metadata=phase)

    def interfere_states(
        self, states: Sequence[QuantumState], weights: Sequence[complex]
    ) -> QuantumState:
        if not states or len(states) != len(weights):
            raise CompressedTensorError("states and weights must be non-empty and equal length")
        vectors = []
        for state in states:
            vector = self.decompress_to_registers(state.tensor)
            if vector.ndim != 1:
                raise CompressedTensorError(
                    "coherent interference requires state vectors, not density matrices"
                )
            vectors.append(vector.astype(complex))
        if len({vector.shape for vector in vectors}) != 1:
            raise CompressedTensorError("interfering state vectors must have equal dimensions")
        weighted = (complex(weight) * vector for weight, vector in zip(weights, vectors))
        combined = sum(weighted, np.zeros_like(vectors[0]))
        norm = float(np.linalg.norm(combined))
        if norm <= self.config.interference_tolerance:
            raise CompressedTensorError("destructive interference eliminated the state")
        combined /= norm
        compressed = self.load_tensor_from_host(
            combined,
            scheme=states[0].tensor.compression_scheme,
            max_rank=max(states[0].tensor.ranks, default=self.config.default_max_rank),
        )
        return QuantumState(
            compressed,
            norm=1.0,
            phase_metadata={"interference_weights": [str(complex(w)) for w in weights]},
        )

    def measure_state(
        self,
        state: QuantumState,
        basis: np.ndarray | None = None,
        *,
        rng: np.random.Generator | None = None,
    ) -> MeasurementResult:
        raw = self.decompress_to_registers(state.tensor)
        density = self._as_density(raw)
        transform = (
            np.eye(density.shape[0], dtype=complex)
            if basis is None
            else _finite_array(basis).astype(complex)
        )
        self._require_square(transform, density.shape[0], "measurement basis")
        probabilities = np.real(np.diag(transform.conj().T @ density @ transform))
        probabilities = np.clip(probabilities, 0.0, None)
        total = float(probabilities.sum())
        if total <= self.config.interference_tolerance:
            raise CompressedTensorError("measurement probabilities sum to zero")
        probabilities /= total
        generator = rng or np.random.default_rng()
        outcome = int(generator.choice(len(probabilities), p=probabilities))
        vector = transform[:, outcome]
        collapsed = np.outer(vector, vector.conj())
        compressed = self.load_tensor_from_host(
            collapsed,
            scheme=state.tensor.compression_scheme,
            max_rank=max(state.tensor.ranks, default=self.config.default_max_rank),
        )
        return MeasurementResult(
            outcome,
            probabilities,
            QuantumState(compressed, norm=1.0, phase_metadata={"measurement": outcome}),
        )

    def engine_metadata(self) -> dict[str, Any]:
        return {
            "engine": "QuantumCompressedTensorEngine",
            "owner": "kellogg",
            "schemes": [scheme.value for scheme in CompressionScheme],
            "max_quantum_dim": self.config.max_quantum_dim,
            "truth_class": "mathematical_software_execution",
            "consensus_authority": False,
            "physical_hardware_claim": False,
        }

    @staticmethod
    def _require_square(matrix: np.ndarray, dimension: int, label: str) -> None:
        if matrix.ndim != 2 or matrix.shape != (dimension, dimension):
            raise CompressedTensorError(f"{label} must have shape {(dimension, dimension)}")

    @staticmethod
    def _as_density(array: np.ndarray) -> np.ndarray:
        arr = _finite_array(array).astype(complex)
        if arr.ndim == 1:
            norm = float(np.linalg.norm(arr))
            if norm == 0:
                raise CompressedTensorError("state vector norm must be positive")
            vector = arr / norm
            return np.outer(vector, vector.conj())
        if arr.ndim != 2 or arr.shape[0] != arr.shape[1]:
            raise CompressedTensorError("state must be a vector or square density matrix")
        return QuantumCompressedTensorEngine._enforce_density(arr)

    @staticmethod
    def _enforce_density(density: np.ndarray) -> np.ndarray:
        hermitian = (density + density.conj().T) / 2.0
        values, vectors = np.linalg.eigh(hermitian)
        values = np.clip(values.real, 0.0, None)
        total = float(values.sum())
        if total <= 0:
            raise CompressedTensorError("density matrix has no positive trace")
        return (vectors * (values / total)) @ vectors.conj().T

    @staticmethod
    def _entropy(array: np.ndarray) -> float:
        try:
            density = QuantumCompressedTensorEngine._as_density(array)
        except CompressedTensorError:
            return 0.0
        values = np.linalg.eigvalsh(density).real
        values = values[values > 1e-15]
        return max(0.0, float(-np.sum(values * np.log2(values))))

    @staticmethod
    def _trace_norm(array: np.ndarray) -> float:
        if array.ndim == 2 and array.shape[0] == array.shape[1]:
            return float(np.sum(np.linalg.svd(array, compute_uv=False)))
        return float(np.linalg.norm(array.ravel()))


CompressedQuantumState = QuantumState


__all__ = [
    "CompressedQuantumState",
    "CompressedTensor",
    "CompressedTensorError",
    "CompressionScheme",
    "EngineConfig",
    "ExpertRouter",
    "MeasurementResult",
    "OperatorType",
    "Precision",
    "QuantumCompressedTensorEngine",
    "QuantumOperator",
    "QuantumState",
]
