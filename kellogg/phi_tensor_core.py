"""Kellogg phi tensor core — folded-domain ALU and manifold metric.

The tensor plane of the Geodesic Tensor Engine. :class:`PhiTensorCore` performs
FMA, matrix multiplication, unary/binary elementwise work and reductions on
:class:`aethel.phi_fold.NumericFoldState` operands. Boundary reads use Aethel's
true selective-unfold path; results are folded back and measured.

The July tensor-core evidence surface is preserved without breaking the modern
API: operations still return their result directly, while ``last_metrics`` and
``get_aggregate_metrics()`` expose measured per-operation wall time, declared
FLOP count and throughput. ``reduce_sum`` and binary ``elementwise`` are kept as
compatibility capabilities.

:class:`MetricTensor` carries a discrete Riemannian metric ``g_ij`` with
``euclidean`` / ``phi_scaled`` / ``hyperbolic`` factories, ``distance()``,
``geodesic_step()``, and ``walk_manifold()``.
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional, Sequence, Tuple

import numpy as np

from aethel.phi_fold import (
    KernelBoundary,
    NumericFoldState,
    phi_fold,
    phi_unfold,
    reconstruction_error,
    unfold_partial,
)

logger = logging.getLogger("kellogg.phi_tensor_core")


class TensorCoreError(ValueError):
    """A tensor-core operand, boundary, or shape contract was violated."""


class PrecisionMode(Enum):
    """July precision vocabulary retained as an execution declaration."""

    FP64 = "fp64"
    FP32 = "fp32"
    FP16 = "fp16"
    FP8 = "fp8"
    FP4 = "fp4"


@dataclass(frozen=True)
class TensorOpRecord:
    """Measured evidence for one tensor-core operation."""

    op: str
    input_norm: float
    output_norm: float
    reconstruction_error: float
    boundary: Optional[Tuple[int, int]]
    result_depth: int
    elapsed_ns: int = 0
    flops: int = 0
    throughput_tflops: float = 0.0
    precision: str = PrecisionMode.FP64.value
    core_id: int = 0


def _boundary_slice(state: NumericFoldState, boundary: Optional[KernelBoundary]) -> np.ndarray:
    if boundary is None:
        return phi_unfold(state).ravel()
    return unfold_partial(state, boundary)


class PhiTensorCore:
    """Folded-domain ALU with measured operation evidence."""

    def __init__(
        self,
        result_depth: int = 1,
        fold_depth: int = 1,
        *,
        core_id: int = 0,
        precision: PrecisionMode = PrecisionMode.FP64,
    ) -> None:
        if result_depth < 0 or fold_depth < 0:
            raise TensorCoreError("fold depths must be >= 0")
        if core_id < 0:
            raise TensorCoreError("core_id must be non-negative")
        self.result_depth = int(result_depth)
        self.fold_depth = int(fold_depth)
        self.core_id = int(core_id)
        self.precision = PrecisionMode(precision)
        self.op_log: List[TensorOpRecord] = []
        self.total_flops = 0
        self.total_time_ns = 0

    @property
    def last_metrics(self) -> Optional[TensorOpRecord]:
        return self.op_log[-1] if self.op_log else None

    @staticmethod
    def _max_foldable_depth(size: int, requested: int) -> int:
        """Return the deepest legal fold for ``size`` values.

        ``phi_fold`` requires every retained segment entering a fold step to
        contain at least two values.  Tensor reductions legitimately produce a
        single scalar, so the evidence/result representation automatically
        falls back to depth zero rather than failing an otherwise valid op.
        """
        if size < 1:
            raise TensorCoreError("tensor operation produced an empty result")
        depth = 0
        retained = int(size)
        phi_sq = (1.0 + math.sqrt(5.0)) / 2.0 + 1.0
        while depth < requested and retained >= 2:
            complement = max(1, int(np.rint(retained / phi_sq)))
            retained -= complement
            depth += 1
        return depth

    def _fold_result(self, result: np.ndarray) -> NumericFoldState:
        array = np.asarray(result, dtype=np.float64)
        depth = self._max_foldable_depth(array.size, self.result_depth)
        return phi_fold(array, depth=depth)

    def _record(
        self,
        op: str,
        inputs: Sequence[np.ndarray],
        result: np.ndarray,
        result_state: NumericFoldState,
        boundary: Optional[KernelBoundary],
        *,
        started_ns: int,
        flops: int,
    ) -> TensorOpRecord:
        result_flat = np.asarray(result, dtype=np.float64).ravel()
        in_norm = (
            float(np.sqrt(sum(float(np.sum(np.square(i))) for i in inputs))) if inputs else 0.0
        )
        out_norm = float(np.linalg.norm(result_flat)) if result_flat.size else 0.0
        error = reconstruction_error(np.asarray(result), result_state)
        elapsed_ns = max(1, time.perf_counter_ns() - started_ns)
        record = TensorOpRecord(
            op=op,
            input_norm=in_norm,
            output_norm=out_norm,
            reconstruction_error=error,
            boundary=(boundary.offset, boundary.length) if boundary else None,
            result_depth=result_state.depth,
            elapsed_ns=elapsed_ns,
            flops=max(0, int(flops)),
            throughput_tflops=(max(0, int(flops)) / elapsed_ns) * 1e-3,
            precision=self.precision.value,
            core_id=self.core_id,
        )
        self.op_log.append(record)
        self.total_flops += record.flops
        self.total_time_ns += record.elapsed_ns
        return record

    def fma(
        self,
        a: NumericFoldState,
        b: NumericFoldState,
        c: NumericFoldState,
        boundary: Optional[KernelBoundary] = None,
    ) -> NumericFoldState:
        """Fused multiply-add over the boundary slice: ``a * b + c``."""
        started = time.perf_counter_ns()
        slices = [_boundary_slice(s, boundary) for s in (a, b, c)]
        sizes = {s.size for s in slices}
        if len(sizes) != 1:
            raise TensorCoreError(f"fma operands must slice to equal lengths, got {sizes}")
        result = slices[0] * slices[1] + slices[2]
        state = self._fold_result(result)
        self._record("fma", slices, result, state, boundary, started_ns=started, flops=2 * result.size)
        return state

    def matmul(
        self,
        a: NumericFoldState,
        b: NumericFoldState,
        boundary: Optional[KernelBoundary] = None,
    ) -> NumericFoldState:
        """Matrix product; boundary selects the flat output range returned."""
        started = time.perf_counter_ns()
        a_mat = phi_unfold(a)
        b_mat = phi_unfold(b)
        if a_mat.ndim != 2 or b_mat.ndim != 2:
            raise TensorCoreError("matmul requires 2-D fold states")
        if a_mat.shape[1] != b_mat.shape[0]:
            raise TensorCoreError(f"matmul shape mismatch: {a_mat.shape} x {b_mat.shape}")
        product = a_mat @ b_mat
        flops = 2 * a_mat.shape[0] * a_mat.shape[1] * b_mat.shape[1]
        if boundary is not None:
            flat = product.ravel()
            if boundary.stop > flat.size:
                raise TensorCoreError(
                    f"boundary [{boundary.offset}, {boundary.stop}) exceeds product size {flat.size}"
                )
            product = flat[boundary.slice]
        state = self._fold_result(np.asarray(product))
        self._record(
            "matmul",
            [a_mat.ravel(), b_mat.ravel()],
            np.asarray(product).ravel(),
            state,
            boundary,
            started_ns=started,
            flops=flops,
        )
        return state

    def elementwise(
        self,
        a: NumericFoldState,
        fn_or_b,
        boundary: Optional[KernelBoundary] = None,
        op_name: str = "elementwise",
        *,
        op: Optional[Callable[[np.ndarray, np.ndarray], np.ndarray]] = None,
    ) -> NumericFoldState:
        """Unary modern or binary July-compatible elementwise operation.

        Modern form:: ``elementwise(a, lambda x: ...)``
        July form:: ``elementwise(a, b, boundary, op=lambda x, y: ...)``
        The binary default is addition, matching the July callable default.
        """
        started = time.perf_counter_ns()
        left = _boundary_slice(a, boundary)
        if isinstance(fn_or_b, NumericFoldState):
            right = _boundary_slice(fn_or_b, boundary)
            if left.shape != right.shape:
                raise TensorCoreError("binary elementwise operands must have equal slice shapes")
            binary = op or (lambda x, y: x + y)
            result = np.asarray(binary(left, right), dtype=np.float64)
            inputs = [left, right]
        elif callable(fn_or_b):
            if op is not None:
                raise TensorCoreError("binary op is only valid when the second operand is folded state")
            result = np.asarray(fn_or_b(left), dtype=np.float64)
            inputs = [left]
        else:
            raise TensorCoreError("elementwise requires a callable or NumericFoldState second operand")
        if result.shape != left.shape:
            raise TensorCoreError(f"{op_name} must preserve shape: {left.shape} -> {result.shape}")
        state = self._fold_result(result)
        self._record(
            op_name,
            inputs,
            result.ravel(),
            state,
            boundary,
            started_ns=started,
            flops=result.size,
        )
        return state

    def reduce(
        self,
        a: NumericFoldState,
        fn: Callable[[np.ndarray], float] = np.sum,
        boundary: Optional[KernelBoundary] = None,
        op_name: str = "reduce",
    ) -> float:
        """Reduce the boundary slice to a scalar."""
        started = time.perf_counter_ns()
        operand = _boundary_slice(a, boundary)
        value = float(fn(operand))
        result = np.array([value], dtype=np.float64)
        state = self._fold_result(result)
        self._record(
            op_name,
            [operand],
            result,
            state,
            boundary,
            started_ns=started,
            flops=max(1, operand.size),
        )
        return value

    def reduce_sum(
        self, a: NumericFoldState, boundary: Optional[KernelBoundary] = None
    ) -> float:
        """July-compatible sum reduction."""
        return self.reduce(a, np.sum, boundary, op_name="reduce_sum")

    def get_aggregate_metrics(self) -> dict:
        """Aggregate the measured operation ledger."""
        operations = {}
        for record in self.op_log:
            operations[record.op] = operations.get(record.op, 0) + 1
        return {
            "core_id": self.core_id,
            "precision": self.precision.value,
            "total_operations": len(self.op_log),
            "total_flops": self.total_flops,
            "total_time_ns": self.total_time_ns,
            "avg_throughput_tflops": (
                (self.total_flops / self.total_time_ns) * 1e-3 if self.total_time_ns else 0.0
            ),
            "integrity_passed": all(r.reconstruction_error == 0.0 for r in self.op_log),
            "max_reconstruction_error": max(
                (r.reconstruction_error for r in self.op_log), default=0.0
            ),
            "operations_by_type": operations,
            "truth_class": "measured_host_execution",
        }


class ManifoldType(Enum):
    """Factory family for :class:`MetricTensor`."""

    EUCLIDEAN = "euclidean"
    PHI_SCALED = "phi_scaled"
    HYPERBOLIC = "hyperbolic"


@dataclass
class MetricTensor:
    """Discrete metric ``g_ij`` over an n-dimensional coordinate patch."""

    manifold: ManifoldType
    dim: int
    _factory: str = field(default="euclidean")

    def _g(self, x: np.ndarray) -> np.ndarray:
        if self._factory == "euclidean":
            return np.eye(self.dim)
        if self._factory == "phi_scaled":
            phi = (1.0 + math.sqrt(5.0)) / 2.0
            return np.diag([phi ** (2 * k) for k in range(self.dim)])
        xn = abs(float(x[-1])) if self.dim else 1.0
        xn = max(xn, 1e-12)
        return np.eye(self.dim) / (xn * xn)

    @property
    def g_ij(self) -> np.ndarray:
        """Metric tensor at the canonical unit coordinate for introspection."""
        return self._g(np.ones(self.dim, dtype=np.float64))

    @classmethod
    def euclidean(cls, dim: int) -> "MetricTensor":
        return cls(ManifoldType.EUCLIDEAN, _checked_dim(dim), "euclidean")

    @classmethod
    def phi_scaled(cls, dim: int) -> "MetricTensor":
        return cls(ManifoldType.PHI_SCALED, _checked_dim(dim), "phi_scaled")

    @classmethod
    def hyperbolic(cls, dim: int) -> "MetricTensor":
        return cls(ManifoldType.HYPERBOLIC, _checked_dim(dim), "hyperbolic")

    def distance(self, a: Sequence[float], b: Sequence[float]) -> float:
        va, vb = self._vec(a), self._vec(b)
        mid = 0.5 * (va + vb)
        d = vb - va
        g = self._g(mid)
        return float(np.sqrt(max(d @ g @ d, 0.0)))

    def geodesic_step(
        self, x: Sequence[float], direction: Sequence[float], step: float
    ) -> np.ndarray:
        vx = self._vec(x)
        vd = self._vec(direction)
        g = self._g(vx)
        norm = math.sqrt(max(float(vd @ g @ vd), 1e-30))
        return vx + (step / norm) * vd

    def walk_manifold(
        self, start: Sequence[float], steps: int, direction: Sequence[float], step: float
    ) -> List[np.ndarray]:
        if steps < 1:
            raise TensorCoreError("walk_manifold requires at least one step")
        points = [self._vec(start)]
        for _ in range(steps - 1):
            points.append(self.geodesic_step(points[-1], direction, step))
        return points

    def _vec(self, v: Sequence[float]) -> np.ndarray:
        arr = np.asarray(v, dtype=np.float64)
        if arr.size != self.dim:
            raise TensorCoreError(f"metric is {self.dim}-dimensional; got vector of {arr.size}")
        return arr


def _checked_dim(dim: int) -> int:
    if not isinstance(dim, int) or dim < 1:
        raise TensorCoreError(f"metric dimension must be a positive int, got {dim!r}")
    return dim


__all__ = [
    "ManifoldType",
    "MetricTensor",
    "PhiTensorCore",
    "PrecisionMode",
    "TensorCoreError",
    "TensorOpRecord",
]
