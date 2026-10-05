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
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional, Sequence, Tuple

from .errors import TensorMemoryError, TensorValidationError

#: Conservative default ceiling for a single tensor allocation (bytes).
#: Chosen to be far below typical host RAM while still allowing realistic
#: production workloads; callers may declare a smaller budget explicitly.
DEFAULT_MAX_TENSOR_BYTES = 2 * 1024 * 1024 * 1024  # 2 GiB

#: Largest element count representable on a 64-bit host. Element counts are
#: computed in Python's unbounded integers and *checked* before any narrowing
#: to a platform size (allocation, index arithmetic, device launch) — an
#: over-range shape fails here rather than wrapping downstream.
MAX_TENSOR_ELEMENTS = sys.maxsize


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


class TensorOpKind(str, Enum):
    """Structured operator kinds understood by the tensor semantic IR.

    ``elementwise`` covers arbitrary coordinate-local maps (including ``add``);
    ``contract`` is the axis-named generalization of ``matmul``; the remaining
    kinds are self-describing. Operation *names* remain the wire surface — the
    kind is the typed semantics bound to a name.
    """

    MATMUL = "matmul"
    CONTRACT = "contract"
    FMA = "fma"
    ELEMENTWISE = "elementwise"
    SCALE = "scale"
    TRANSPOSE = "transpose"
    KRON = "kron"
    HADAMARD = "hadamard"
    REDUCE = "reduce"
    ACTIVATION = "activation"


class DependencyScope(str, Enum):
    """How much of an input a single output coordinate may depend on.

    This classification is what the folded-state decoder uses to pick the
    minimal dependency cone for an output region: COORDINATE ops need the same
    flat coordinate in every input, AXIS ops need one full axis fibre, and
    GLOBAL ops may touch the entire input (e.g. a matmul output element reads a
    row of one operand and a column of the other).
    """

    COORDINATE = "coordinate"
    AXIS = "axis"
    GLOBAL = "global"


#: Canonical name → kind binding for the wire-level operation vocabulary.
_NAME_TO_KIND = {
    "matmul": TensorOpKind.MATMUL,
    "contract": TensorOpKind.CONTRACT,
    "fma": TensorOpKind.FMA,
    "add": TensorOpKind.ELEMENTWISE,
    "elementwise": TensorOpKind.ELEMENTWISE,
    "scale": TensorOpKind.SCALE,
    "transpose": TensorOpKind.TRANSPOSE,
    "kron": TensorOpKind.KRON,
    "hadamard": TensorOpKind.HADAMARD,
    "reduce": TensorOpKind.REDUCE,
    "reduce_sum": TensorOpKind.REDUCE,
    "activation": TensorOpKind.ACTIVATION,
}

_DEPENDENCY_SCOPE = {
    TensorOpKind.ELEMENTWISE: DependencyScope.COORDINATE,
    TensorOpKind.HADAMARD: DependencyScope.COORDINATE,
    TensorOpKind.SCALE: DependencyScope.COORDINATE,
    TensorOpKind.FMA: DependencyScope.COORDINATE,
    TensorOpKind.ACTIVATION: DependencyScope.COORDINATE,
    TensorOpKind.TRANSPOSE: DependencyScope.COORDINATE,
    TensorOpKind.REDUCE: DependencyScope.AXIS,
    TensorOpKind.MATMUL: DependencyScope.GLOBAL,
    TensorOpKind.CONTRACT: DependencyScope.GLOBAL,
    TensorOpKind.KRON: DependencyScope.GLOBAL,
}


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
        _require(
            self.size <= MAX_TENSOR_ELEMENTS,
            "element count exceeds the 64-bit addressable maximum",
        )

    @property
    def size(self) -> int:
        total = 1
        for dim in self.dims:
            total *= dim
        return total

    @property
    def rank(self) -> int:
        return len(self.dims)

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
    total = sum(shape.size for shape in shapes) * dtype.itemsize
    if total > sys.maxsize:
        raise TensorValidationError(
            "estimated byte size exceeds the 64-bit addressable maximum"
        )
    return total


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


def _validate_axis_names(
    axes: Tuple[str, ...], *, owner: str, allow_empty: bool = False
) -> Tuple[str, ...]:
    names = tuple(axes)
    if not allow_empty:
        _require(bool(names), f"{owner} must declare at least one axis")
    for name in names:
        _require(
            isinstance(name, str) and bool(name.strip()),
            f"{owner} axis names must be non-empty strings",
        )
    _require(
        len(set(names)) == len(names),
        f"{owner} axis names must be unique within an operand",
    )
    return names


@dataclass(frozen=True)
class TensorOperationSpec:
    """A declared tensor operation: shapes, dtype, exactness, and op count.

    ``op_count`` is the declared number of arithmetic operations for the
    request (e.g. ``2 * m * n * k`` for an ``m x k`` by ``k x n`` matmul).
    It is the *only* source combined with measured elapsed time to derive
    TFLOPs (see :mod:`tensor.runtime`); it must never be derived from, or
    converted into, a hash rate.

    The optional axis fields make the operation's index semantics explicit:

    * ``input_axes`` names every axis of every input (``("i", "k")`` and
      ``("k", "j")`` for a matmul) — axis names shared across inputs denote
      the same index space and must have equal extents.
    * ``output_axes`` names the output's coordinate space; every output axis
      must appear on at least one input.
    * ``contract_axes`` names the contraction pairs — axes shared by inputs
      and *absent* from the output (e.g. ``("k",)``).

    When axes are declared, the kind's shape algebra is fully checked: shared
    axis extents must agree, contracted axes must not reach the output, and a
    general ``contract`` computes its output coordinate space as the
    non-contracted input axes. Without axes the kind still enforces its
    rank/dim algebra (invalid ranks and mismatched dims fail in
    ``__post_init__``, before any allocation).
    """

    name: str
    input_shapes: Tuple[TensorShape, ...]
    output_shape: TensorShape
    dtype: Precision
    exactness_mode: ExactnessMode
    op_count: int
    op_kind: Optional[TensorOpKind] = None
    input_axes: Optional[Tuple[Tuple[str, ...], ...]] = None
    output_axes: Optional[Tuple[str, ...]] = None
    contract_axes: Optional[Tuple[str, ...]] = None

    def __post_init__(self) -> None:
        _require(bool(self.name.strip()), "operation name must be non-empty")
        _require(len(self.input_shapes) > 0, "at least one input shape is required")
        _require(
            isinstance(self.op_count, int) and not isinstance(self.op_count, bool),
            "op_count must be an int",
        )
        _require(self.op_count >= 0, "op_count must be >= 0")
        if self.op_kind is not None:
            _require(
                isinstance(self.op_kind, TensorOpKind),
                "op_kind must be a TensorOpKind",
            )
        self._validate_axes()
        self._validate_shape_algebra()

    # -- semantic IR -------------------------------------------------------

    @property
    def kind(self) -> Optional[TensorOpKind]:
        """The structured kind for this operation, or ``None`` when opaque."""
        if self.op_kind is not None:
            return self.op_kind
        return _NAME_TO_KIND.get(self.name)

    @property
    def dependency_scope(self) -> Optional[DependencyScope]:
        """Input dependency breadth of one output coordinate (kind-derived)."""
        kind = self.kind
        return _DEPENDENCY_SCOPE.get(kind) if kind is not None else None

    @property
    def contracted_axes(self) -> Tuple[str, ...]:
        """Axes shared between inputs that are absent from the output space.

        Uses the declared ``contract_axes`` when given; otherwise derives them
        from declared axis names (shared by >= 2 inputs, not an output axis).
        """
        if self.contract_axes is not None:
            return tuple(self.contract_axes)
        if self.input_axes is None or self.output_axes is None:
            return ()
        out = set(self.output_axes)
        counts: dict[str, int] = {}
        for operand_axes in self.input_axes:
            for name in operand_axes:
                counts[name] = counts.get(name, 0) + 1
        return tuple(sorted(n for n, c in counts.items() if c >= 2 and n not in out))

    def _validate_axes(self) -> None:
        if self.input_axes is None and self.output_axes is None and self.contract_axes is None:
            return
        _require(
            self.input_axes is not None,
            "output_axes/contract_axes require declared input_axes",
        )
        _require(
            len(self.input_axes) == len(self.input_shapes),
            "input_axes must have one axis tuple per input shape",
        )
        axis_dim: dict[str, int] = {}
        for index, (axes, shape) in enumerate(zip(self.input_axes, self.input_shapes)):
            names = _validate_axis_names(axes, owner=f"input_axes[{index}]")
            _require(
                len(names) == shape.rank,
                f"input_axes[{index}] has {len(names)} axes for rank {shape.rank}",
            )
            for axis_name, dim in zip(names, shape.dims):
                prior = axis_dim.setdefault(axis_name, dim)
                _require(
                    prior == dim,
                    f"axis {axis_name!r} has inconsistent extents {prior} vs {dim}",
                )
        if self.output_axes is not None:
            names = _validate_axis_names(self.output_axes, owner="output_axes")
            _require(
                len(names) == self.output_shape.rank,
                "output_axes must match the output rank",
            )
            for axis_name, dim in zip(names, self.output_shape.dims):
                prior = axis_dim.get(axis_name)
                _require(
                    prior is not None,
                    f"output axis {axis_name!r} does not appear on any input",
                )
                _require(
                    prior == dim,
                    f"output axis {axis_name!r} extent {dim} differs from input extent {prior}",
                )
        if self.contract_axes is not None:
            names = _validate_axis_names(self.contract_axes, owner="contract_axes")
            in_names = {n for operand in self.input_axes for n in operand}
            for axis_name in names:
                count = sum(1 for operand in self.input_axes if axis_name in operand)
                _require(
                    count >= 2,
                    f"contract axis {axis_name!r} must appear on at least two inputs",
                )
                _require(axis_name in in_names, f"contract axis {axis_name!r} unknown")
            if self.output_axes is not None:
                overlap = set(names) & set(self.output_axes)
                _require(
                    not overlap,
                    f"contract axes {sorted(overlap)} cannot appear in the output space",
                )

    def _validate_shape_algebra(self) -> None:
        """Fail-closed rank/dim algebra for every structured op kind."""
        kind = self.kind
        if kind is None:
            return  # opaque operation: validated by the backend at execute time
        dims = [shape.dims for shape in self.input_shapes]
        out = self.output_shape.dims
        if kind is TensorOpKind.MATMUL:
            _require(len(dims) == 2, "matmul requires exactly two inputs")
            _require(
                len(dims[0]) == 2 and len(dims[1]) == 2,
                "matmul requires two rank-2 inputs",
            )
            _require(
                dims[0][1] == dims[1][0],
                f"matmul inner dims differ: {dims[0][1]} vs {dims[1][0]}",
            )
            _require(
                out == (dims[0][0], dims[1][1]),
                f"matmul output must be ({dims[0][0]}, {dims[1][1]}), got {out}",
            )
        elif kind is TensorOpKind.CONTRACT:
            _require(
                self.input_axes is not None and self.output_axes is not None,
                "contract requires declared input_axes and output_axes",
            )
            _require(
                bool(self.contracted_axes),
                "contract requires at least one contracted axis",
            )
            expected = tuple(n for n in self._merged_input_axes() if n not in self.contracted_axes)
            _require(
                tuple(sorted(self.output_axes)) == tuple(sorted(expected)),
                "contract output axes must be exactly the non-contracted input axes",
            )
        elif kind in (TensorOpKind.ELEMENTWISE, TensorOpKind.HADAMARD):
            _require(
                len(dims) == 2 and dims[0] == dims[1],
                f"{kind.value} requires two inputs of equal shape",
            )
            _require(
                out == dims[0],
                f"{kind.value} output shape must equal the input shape",
            )
        elif kind is TensorOpKind.FMA:
            _require(
                len(dims) == 3 and dims[0] == dims[1] == dims[2],
                "fma requires three inputs of equal shape (a * b + c)",
            )
            _require(out == dims[0], "fma output shape must equal the input shape")
        elif kind is TensorOpKind.SCALE:
            _require(len(dims) == 2, "scale requires a tensor and a scalar input")
            _require(
                self.input_shapes[1].size == 1,
                "scale's second input must be a single-element scalar",
            )
            _require(out == dims[0], "scale output shape must equal the tensor shape")
        elif kind is TensorOpKind.TRANSPOSE:
            _require(len(dims) == 1, "transpose takes a single input")
            _require(
                sorted(out) == sorted(dims[0]),
                "transpose output dims must be a permutation of the input dims",
            )
            if self.input_axes is not None and self.output_axes is not None:
                _require(
                    tuple(sorted(self.output_axes)) == tuple(sorted(self.input_axes[0])),
                    "transpose output axes must be a permutation of the input axes",
                )
                expected_dims = tuple(
                    dims[0][self.input_axes[0].index(a)] for a in self.output_axes
                )
                _require(
                    out == expected_dims,
                    f"transpose axes imply output dims {expected_dims}, got {out}",
                )
        elif kind is TensorOpKind.KRON:
            _require(len(dims) == 2, "kron requires exactly two inputs")
            _require(
                len(dims[0]) == len(dims[1]),
                "kron requires inputs of equal rank",
            )
            expected = tuple(a * b for a, b in zip(dims[0], dims[1]))
            _require(
                out == expected,
                f"kron output dims must be the pairwise product {expected}, got {out}",
            )
        elif kind is TensorOpKind.REDUCE:
            _require(len(dims) == 1, "reduce takes a single input")
            _require(
                self.input_axes is not None and self.output_axes is not None,
                "reduce requires declared input_axes and output_axes",
            )
            kept = self.output_axes
            expected_dims = tuple(
                dims[0][self.input_axes[0].index(a)] for a in kept
            )
            _require(
                out == expected_dims,
                f"reduce output dims must be {expected_dims} for kept axes, got {out}",
            )
        elif kind is TensorOpKind.ACTIVATION:
            _require(len(dims) == 1, "activation takes a single input")
            _require(
                out == dims[0],
                "activation is shape-preserving: output must equal the input shape",
            )

    def _merged_input_axes(self) -> Tuple[str, ...]:
        merged: list[str] = []
        for operand in self.input_axes or ():
            for name in operand:
                if name not in merged:
                    merged.append(name)
        return tuple(merged)


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
    "TensorOpKind",
    "DependencyScope",
    "MAX_TENSOR_ELEMENTS",
    "TensorRequest",
    "TensorMeasurement",
    "TensorResult",
]
