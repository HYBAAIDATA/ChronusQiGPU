"""Typed, fail-closed production contracts for tensor operations.

Every record here is a frozen dataclass that validates itself in
``__post_init__``. Invalid input raises :class:`tensor.errors.TensorValidationError`
immediately; nothing is silently coerced, repaired, truncated, or padded.

These records are the stable logical surface for the ``tensor`` package:
operation specs, requests, results, backend identity, provenance, residual
bounds, memory budgets, and truth class. They are backend-neutral — nothing
in this module imports NumPy, Chronus/OpenCL, or any hardware library.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional, Sequence, Tuple

from .errors import TensorMemoryError, TensorValidationError

#: Conservative default ceiling for a single tensor allocation (bytes).
#: Chosen to be far below typical host RAM while still allowing realistic
#: production workloads; callers may declare a smaller budget explicitly.
DEFAULT_MAX_TENSOR_BYTES = 2 * 1024 * 1024 * 1024  # 2 GiB


class ExactnessMode(str, Enum):
    """Whether an operation is exact or an explicitly-approved approximation."""

    EXACT = "exact"
    LOSSY_APPROX = "lossy_approx"


class TruthClass(str, Enum):
    """How a reported number is allowed to be interpreted downstream."""

    MEASURED = "measured"
    DECLARED = "declared"
    SIMULATED = "simulated"


class Precision(str, Enum):
    """Supported tensor element dtypes."""

    FLOAT32 = "float32"
    FLOAT64 = "float64"
    COMPLEX64 = "complex64"
    COMPLEX128 = "complex128"
    EXACT_RATIONAL = "exact_rational"  # kellogg.exact_tensor Q(sqrt2)+iQ(sqrt2)

    @property
    def is_exact(self) -> bool:
        return self is Precision.EXACT_RATIONAL

    @property
    def itemsize(self) -> int:
        return {
            Precision.FLOAT32: 4,
            Precision.FLOAT64: 8,
            Precision.COMPLEX64: 8,
            Precision.COMPLEX128: 16,
            Precision.EXACT_RATIONAL: 0,  # unbounded; must not be memory-estimated
        }[self]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise TensorValidationError(message)


@dataclass(frozen=True)
class TensorShape:
    """A validated, immutable tensor shape."""

    dims: Tuple[int, ...]

    def __post_init__(self) -> None:
        _require(isinstance(self.dims, tuple), "dims must be a tuple")
        _require(len(self.dims) > 0, "dims must be non-empty")
        for dim in self.dims:
            _require(isinstance(dim, int) and not isinstance(dim, bool), "dims must be ints")
            _require(dim > 0, "every dimension must be > 0")

    @property
    def size(self) -> int:
        total = 1
        for dim in self.dims:
            total *= dim
        return total

    def __iter__(self):
        return iter(self.dims)


@dataclass(frozen=True)
class MemoryBudget:
    """A declared, conservative memory ceiling for one operation."""

    max_bytes: int = DEFAULT_MAX_TENSOR_BYTES

    def __post_init__(self) -> None:
        _require(
            isinstance(self.max_bytes, int) and not isinstance(self.max_bytes, bool),
            "max_bytes must be an int",
        )
        _require(self.max_bytes > 0, "max_bytes must be > 0")

    def check(self, estimated_bytes: int) -> None:
        """Fail closed when an estimate exceeds the declared budget."""
        if estimated_bytes > self.max_bytes:
            raise TensorMemoryError(
                f"estimated {estimated_bytes} bytes exceeds memory budget "
                f"{self.max_bytes} bytes"
            )


def estimate_bytes(shapes: Sequence[TensorShape], dtype: Precision) -> int:
    """Conservative byte estimate for a set of shapes at a given dtype.

    Exact-rational tensors have unbounded per-element size (arbitrary
    precision ``Fraction``s), so they cannot be estimated here; callers must
    use ``kellogg.exact_tensor`` resource bounds instead and this function
    fails closed rather than under-reporting.
    """
    if dtype.is_exact:
        raise TensorValidationError(
            "exact-rational tensors cannot be memory-estimated by byte size; "
            "use the kellogg exact-tensor resource bounds instead"
        )
    return sum(shape.size for shape in shapes) * dtype.itemsize


@dataclass(frozen=True)
class ResidualBounds:
    """Residual-error evidence required for any lossy approximation."""

    max_residual: float = 0.0
    measured_residual: Optional[float] = None
    opt_in: bool = False

    def __post_init__(self) -> None:
        _require(
            math.isfinite(self.max_residual) and self.max_residual >= 0,
            "max_residual must be finite and >= 0",
        )
        if self.measured_residual is not None:
            _require(
                math.isfinite(self.measured_residual) and self.measured_residual >= 0,
                "measured_residual must be finite and >= 0",
            )

    def require_for(self, exactness_mode: ExactnessMode) -> None:
        """Fail closed unless lossy truncation carries explicit opt-in evidence."""
        if exactness_mode is not ExactnessMode.LOSSY_APPROX:
            return
        if not self.opt_in:
            raise TensorValidationError(
                "lossy truncation requires explicit opt-in (ResidualBounds.opt_in=True)"
            )
        if self.measured_residual is None:
            raise TensorValidationError("lossy truncation requires measured residual evidence")
        if self.measured_residual > self.max_residual:
            raise TensorValidationError(
                f"measured residual {self.measured_residual} exceeds declared bound "
                f"{self.max_residual}"
            )


@dataclass(frozen=True)
class BackendIdentity:
    """Identity of the backend that executed (or would execute) an operation."""

    name: str
    backend_class: str  # "reference" | "hardware" | "simulator"
    device_id: str
    version: str = "0"

    def __post_init__(self) -> None:
        _require(bool(self.name.strip()), "backend name must be non-empty")
        _require(
            self.backend_class in ("reference", "hardware", "simulator"),
            "backend_class must be one of: reference, hardware, simulator",
        )
        _require(bool(self.device_id.strip()), "device_id must be non-empty")


@dataclass(frozen=True)
class ModelIdentity:
    """Identity of a model/version associated with a tensor operation."""

    model_id: str
    model_version: str = "0"

    def __post_init__(self) -> None:
        _require(bool(self.model_id.strip()), "model_id must be non-empty")


@dataclass(frozen=True)
class ProvenanceRecord:
    """Evidence binding a result to the request, backend, and model that produced it."""

    operation: str
    backend: BackendIdentity
    model: ModelIdentity
    input_digest: str
    output_digest: str
    created_at_ns: int = field(default_factory=time.time_ns)

    def __post_init__(self) -> None:
        _require(bool(self.operation.strip()), "operation must be non-empty")
        _require(bool(self.input_digest.strip()), "input_digest must be non-empty")
        _require(bool(self.output_digest.strip()), "output_digest must be non-empty")

    def as_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "backend": self.backend.name,
            "backend_class": self.backend.backend_class,
            "device_id": self.backend.device_id,
            "model_id": self.model.model_id,
            "model_version": self.model.model_version,
            "input_digest": self.input_digest,
            "output_digest": self.output_digest,
            "created_at_ns": self.created_at_ns,
        }


@dataclass(frozen=True)
class TensorOperationSpec:
    """A declared tensor operation: shapes, dtype, exactness, and op count.

    ``op_count`` is the declared number of arithmetic operations for the
    request (e.g. ``2 * m * n * k`` for an ``m x k`` by ``k x n`` matmul).
    It is the *only* source combined with measured elapsed time to derive
    TFLOPs (see :mod:`tensor.runtime`); it must never be derived from, or
    converted into, a hash rate.
    """

    name: str
    input_shapes: Tuple[TensorShape, ...]
    output_shape: TensorShape
    dtype: Precision
    exactness_mode: ExactnessMode
    op_count: int

    def __post_init__(self) -> None:
        _require(bool(self.name.strip()), "operation name must be non-empty")
        _require(len(self.input_shapes) > 0, "at least one input shape is required")
        _require(
            isinstance(self.op_count, int) and not isinstance(self.op_count, bool),
            "op_count must be an int",
        )
        _require(self.op_count >= 0, "op_count must be >= 0")


@dataclass(frozen=True)
class TensorRequest:
    """A validated request to execute a :class:`TensorOperationSpec`."""

    operation: TensorOperationSpec
    memory_budget: MemoryBudget = field(default_factory=MemoryBudget)
    residual_bounds: ResidualBounds = field(default_factory=ResidualBounds)
    backend_required: Optional[str] = None
    timeout_ns: Optional[int] = None
    deterministic: bool = True
    allow_fallback: bool = False

    def __post_init__(self) -> None:
        if self.backend_required is not None:
            _require(bool(self.backend_required.strip()), "backend_required must be non-empty")
        if self.timeout_ns is not None:
            _require(
                isinstance(self.timeout_ns, int) and self.timeout_ns > 0,
                "timeout_ns must be a positive int",
            )
        self.residual_bounds.require_for(self.operation.exactness_mode)
        if not self.operation.dtype.is_exact:
            estimated = estimate_bytes(
                (*self.operation.input_shapes, self.operation.output_shape),
                self.operation.dtype,
            )
            self.memory_budget.check(estimated)


@dataclass(frozen=True)
class TensorMeasurement:
    """Measured tensor operations over a wall-clock interval.

    ``tflops`` is derived strictly from ``operations`` (a declared op count)
    and ``elapsed_ns`` (measured elapsed time). It is never combined with,
    or converted into, a hash rate (H/s).
    """

    operations: int
    elapsed_ns: int
    backend: str
    model_id: str = ""
    fallback_used: bool = False
    fallback_reason: str = ""

    def __post_init__(self) -> None:
        _require(self.operations >= 0, "operations must be >= 0")
        _require(self.elapsed_ns > 0, "elapsed_ns must be > 0")
        _require(bool(self.backend.strip()), "backend must be non-empty")
        if self.fallback_used:
            _require(bool(self.fallback_reason.strip()), "a recorded fallback needs a reason")

    @property
    def tflops(self) -> float:
        return self.operations * 1_000_000_000.0 / self.elapsed_ns / 1e12

    def as_dict(self) -> dict[str, Any]:
        return {
            "operations": self.operations,
            "elapsed_ns": self.elapsed_ns,
            "backend": self.backend,
            "model_id": self.model_id,
            "fallback_used": self.fallback_used,
            "fallback_reason": self.fallback_reason,
            "measured_tensor_tflops": self.tflops,
            "truth_class": TruthClass.MEASURED.value,
            "hashrate_hps": None,
        }


@dataclass(frozen=True)
class TensorResult:
    """The outcome of executing a :class:`TensorRequest`."""

    request: TensorRequest
    data: Any
    measurement: TensorMeasurement
    provenance: ProvenanceRecord
    truth_class: TruthClass = TruthClass.MEASURED

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "operation": self.request.operation.name,
            "measurement": self.measurement.as_dict(),
            "provenance": self.provenance.as_dict(),
            "truth_class": self.truth_class.value,
        }


__all__ = [
    "DEFAULT_MAX_TENSOR_BYTES",
    "ExactnessMode",
    "TruthClass",
    "Precision",
    "TensorShape",
    "MemoryBudget",
    "estimate_bytes",
    "ResidualBounds",
    "BackendIdentity",
    "ModelIdentity",
    "ProvenanceRecord",
    "TensorOperationSpec",
    "TensorRequest",
    "TensorMeasurement",
    "TensorResult",
]
