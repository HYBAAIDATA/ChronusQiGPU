"""Production tensor execution compatibility surfaces.

These classes preserve the July Geodesic/Tensor API concepts while routing
through explicit NumPy reference execution unless a separately qualified
accelerator backend is selected. No hardware route is inferred from a class
name.
"""

from __future__ import annotations

import heapq
import math
import time
from dataclasses import dataclass, field
from typing import Any, Iterable

import numpy as np

from chronus.tensor.folded_state import ExactFoldState


@dataclass(frozen=True)
class KernelBoundary:
    start: int
    stop: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.stop < self.start:
            raise ValueError("invalid kernel boundary")


@dataclass(frozen=True)
class IntegrityVerdict:
    passed: bool
    max_abs_error: float
    shape_match: bool
    dtype_match: bool


class TopologicalIntegrityGate:
    """Operation-output verification gate with explicit tolerance."""

    def __init__(self, tolerance: float = 1e-10) -> None:
        if tolerance < 0:
            raise ValueError("tolerance must be non-negative")
        self.tolerance = tolerance
        self.checks_performed = 0
        self.checks_passed = 0

    def verify(self, actual: np.ndarray, expected: np.ndarray) -> IntegrityVerdict:
        self.checks_performed += 1
        a, e = np.asarray(actual), np.asarray(expected)
        shape_match = a.shape == e.shape
        dtype_match = a.dtype == e.dtype
        if not shape_match:
            return IntegrityVerdict(False, float("inf"), False, dtype_match)
        error = float(np.max(np.abs(a - e))) if a.size else 0.0
        passed = bool(error <= self.tolerance)
        if passed:
            self.checks_passed += 1
        return IntegrityVerdict(passed, error, shape_match, dtype_match)


class PhiTensorCore:
    """Explicit tensor operations with shape-safe reference execution."""

    SUPPORTED = frozenset({"add", "hadamard", "scale", "matmul", "kron", "reduce_sum"})

    def __init__(self, core_id: int = 0, integrity_gate: TopologicalIntegrityGate | None = None) -> None:
        self.core_id = int(core_id)
        self.integrity_gate = integrity_gate or TopologicalIntegrityGate()

    def execute(self, operation: str, *values: np.ndarray, scalar: float | complex | None = None) -> dict:
        op = operation.lower()
        if op not in self.SUPPORTED:
            raise ValueError(f"unsupported tensor operation: {operation}")
        arrays = [np.asarray(v) for v in values]
        if not arrays:
            raise ValueError("at least one tensor input is required")
        t0 = time.perf_counter_ns()
        if op == "add":
            if len(arrays) != 2 or arrays[0].shape != arrays[1].shape:
                raise ValueError("add requires two identically shaped tensors")
            result = arrays[0] + arrays[1]
        elif op == "hadamard":
            if len(arrays) != 2 or arrays[0].shape != arrays[1].shape:
                raise ValueError("hadamard requires two identically shaped tensors")
            result = arrays[0] * arrays[1]
        elif op == "scale":
            if len(arrays) != 1 or scalar is None:
                raise ValueError("scale requires one tensor and scalar")
            result = arrays[0] * scalar
        elif op == "matmul":
            if len(arrays) != 2 or arrays[0].ndim != 2 or arrays[1].ndim != 2:
                raise ValueError("matmul requires two rank-2 tensors")
            if arrays[0].shape[1] != arrays[1].shape[0]:
                raise ValueError("matmul inner dimensions do not agree")
            result = arrays[0] @ arrays[1]
        elif op == "kron":
            if len(arrays) != 2 or arrays[0].ndim not in (1, 2) or arrays[1].ndim not in (1, 2):
                raise ValueError("kron supports rank-1 or rank-2 tensors")
            result = np.kron(arrays[0], arrays[1])
        else:
            if len(arrays) != 1:
                raise ValueError("reduce_sum requires one tensor")
            result = np.asarray(arrays[0].sum())
        elapsed = time.perf_counter_ns() - t0
        return {
            "output": result,
            "elapsed_ns": elapsed,
            "backend": "numpy-reference",
            "core_id": self.core_id,
            "operation": op,
        }


@dataclass(frozen=True)
class MetricTensor:
    matrix: np.ndarray

    @classmethod
    def euclidean(cls, dimensions: int) -> "MetricTensor":
        return cls(np.eye(dimensions, dtype=np.float64))

    @classmethod
    def phi_scaled(cls, dimensions: int) -> "MetricTensor":
        phi = (1.0 + 5.0**0.5) / 2.0
        return cls(np.eye(dimensions, dtype=np.float64) * phi)

    @classmethod
    def hyperbolic(cls, dimensions: int) -> "MetricTensor":
        diag = np.ones(dimensions, dtype=np.float64)
        if dimensions:
            diag[-1] = max(1.0, float(dimensions))
        return cls(np.diag(diag))

    def distance(self, a: np.ndarray, b: np.ndarray) -> float:
        delta = np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64)
        if delta.ndim != 1 or self.matrix.shape != (delta.size, delta.size):
            raise ValueError("metric and vectors have incompatible dimensions")
        return float(math.sqrt(max(0.0, float(delta @ self.matrix @ delta))))

    def geodesic_step(self, a: np.ndarray, b: np.ndarray, fraction: float) -> np.ndarray:
        if not 0.0 <= fraction <= 1.0:
            raise ValueError("fraction must be in [0,1]")
        av, bv = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
        if av.shape != bv.shape:
            raise ValueError("vectors must have the same shape")
        return av + fraction * (bv - av)

    def walk_manifold(self, a: np.ndarray, b: np.ndarray, steps: int) -> list[np.ndarray]:
        if steps < 1:
            raise ValueError("steps must be positive")
        return [self.geodesic_step(a, b, i / steps) for i in range(steps + 1)]


@dataclass(order=True)
class _Scheduled:
    priority: tuple[float, int]
    task: Any = field(compare=False)


class GeodesicScheduler:
    """Deterministic ready queue ordered by declared locality and insertion."""

    def __init__(self) -> None:
        self._queue: list[_Scheduled] = []
        self._seq = 0

    def submit(self, task: Any, distance: float = 0.0) -> None:
        if distance < 0 or not math.isfinite(distance):
            raise ValueError("distance must be finite and non-negative")
        heapq.heappush(self._queue, _Scheduled((float(distance), self._seq), task))
        self._seq += 1

    def pop(self) -> Any:
        if not self._queue:
            raise IndexError("scheduler is empty")
        return heapq.heappop(self._queue).task

    def __len__(self) -> int:
        return len(self._queue)


class PhiMemoryHierarchy:
    """Dtype-preserving resident folded-state registry.

    Tier labels are residency labels only. No physical HBM/SRAM capacity or
    compression ratio is inferred from them.
    """

    TIERS = ("register", "sram", "l2", "hbm")

    def __init__(self) -> None:
        self._storage: dict[str, dict[str, ExactFoldState]] = {}

    def store(self, key: str, value: np.ndarray, tier: str = "hbm") -> ExactFoldState:
        if tier not in self.TIERS:
            raise ValueError("unknown memory tier")
        if not key:
            raise ValueError("key is required")
        state = ExactFoldState.from_array(np.asarray(value))
        self._storage.setdefault(key, {})[tier] = state
        return state

    def state(self, key: str, tier: str = "hbm") -> ExactFoldState:
        return self._storage[key][tier]

    def load(self, key: str, tier: str = "hbm") -> np.ndarray:
        return self.state(key, tier).unfold_array()

    def load_rows(self, key: str, start: int, stop: int, tier: str = "hbm") -> np.ndarray:
        return self.state(key, tier).unfold_rows(start, stop)

    def promote(self, key: str, source: str, target: str) -> None:
        if source not in self.TIERS or target not in self.TIERS:
            raise ValueError("unknown memory tier")
        self._storage.setdefault(key, {})[target] = self._storage[key][source]

    demote = promote


@dataclass(frozen=True)
class KernelLaunchConfig:
    operation: str
    distance: float = 0.0


class PhiGPU:
    """Compatibility facade over verified software tensor execution."""

    def __init__(self, num_cores: int = 4) -> None:
        if num_cores < 1:
            raise ValueError("num_cores must be positive")
        self.cores = [PhiTensorCore(i) for i in range(num_cores)]
        self.scheduler = GeodesicScheduler()
        self.memory = PhiMemoryHierarchy()

    def launch_kernel(self, requests: Iterable[tuple[KernelLaunchConfig, tuple[np.ndarray, ...], dict]]) -> list[dict]:
        for request in requests:
            config, values, kwargs = request
            self.scheduler.submit((config, values, kwargs), config.distance)
        results: list[dict] = []
        i = 0
        while len(self.scheduler):
            config, values, kwargs = self.scheduler.pop()
            results.append(self.cores[i % len(self.cores)].execute(config.operation, *values, **kwargs))
            i += 1
        return results

    def get_system_report(self) -> dict:
        return {
            "execution_backend": "numpy-reference",
            "physical_accelerator_measured": False,
            "cores": len(self.cores),
            "resident_keys": list(self.memory._storage),
        }


class HybridGPU:
    """Compatibility router that never fabricates an accelerator route."""

    def __init__(self, software: PhiGPU | None = None, accelerator: Any | None = None) -> None:
        self.software = software or PhiGPU()
        self.accelerator = accelerator

    def route_workload(self, operation: str, *, require_accelerator: bool = False) -> dict:
        available = bool(
            self.accelerator is not None
            and getattr(self.accelerator, "is_available", lambda: False)()
        )
        if require_accelerator and not available:
            raise RuntimeError("requested tensor accelerator is unavailable")
        return {
            "route": "accelerator" if available else "numpy-reference",
            "reason": None if available else "ACCELERATOR_UNAVAILABLE",
            "operation": operation,
        }


@dataclass(frozen=True)
class EnergyComparison:
    baseline_joules: float
    candidate_joules: float
    delta_joules: float
    reduction_fraction: float | None


class EnergyModel:
    """Evidence-only energy comparison from caller-supplied measurements.

    No default savings percentage is embedded. The caller supplies measured
    compute and movement energy for the same workload and environment.
    """

    @staticmethod
    def compare(
        *,
        baseline_compute_joules: float,
        baseline_movement_joules: float,
        candidate_compute_joules: float,
        candidate_movement_joules: float,
    ) -> EnergyComparison:
        values = (
            baseline_compute_joules,
            baseline_movement_joules,
            candidate_compute_joules,
            candidate_movement_joules,
        )
        if any((not math.isfinite(float(v)) or float(v) < 0.0) for v in values):
            raise ValueError("energy inputs must be finite non-negative measurements")
        baseline = float(baseline_compute_joules) + float(baseline_movement_joules)
        candidate = float(candidate_compute_joules) + float(candidate_movement_joules)
        reduction = None if baseline == 0.0 else (baseline - candidate) / baseline
        return EnergyComparison(
            baseline_joules=baseline,
            candidate_joules=candidate,
            delta_joules=baseline - candidate,
            reduction_fraction=reduction,
        )


@dataclass(frozen=True)
class BackendProfile:
    operation: str
    backend: str
    size_class: int
    elapsed_ns: int
    verified: bool


class ProfiledHybridRouter:
    """Select the fastest verified observed route for an operation/size class."""

    def __init__(self) -> None:
        self._profiles: list[BackendProfile] = []

    def record(
        self,
        *,
        operation: str,
        backend: str,
        size_class: int,
        elapsed_ns: int,
        verified: bool,
    ) -> BackendProfile:
        if not operation or not backend:
            raise ValueError("operation and backend are required")
        if size_class < 0 or elapsed_ns <= 0:
            raise ValueError("size_class must be non-negative and elapsed_ns positive")
        profile = BackendProfile(
            operation=operation.lower(),
            backend=backend,
            size_class=int(size_class),
            elapsed_ns=int(elapsed_ns),
            verified=bool(verified),
        )
        self._profiles.append(profile)
        return profile

    def select(self, operation: str, size_class: int) -> dict:
        eligible = [
            p
            for p in self._profiles
            if p.operation == operation.lower()
            and p.size_class == int(size_class)
            and p.verified
        ]
        if not eligible:
            return {
                "route": "numpy-reference",
                "reason": "NO_VERIFIED_PROFILE",
                "profiled": False,
            }
        best = min(eligible, key=lambda p: (p.elapsed_ns, p.backend))
        return {
            "route": best.backend,
            "reason": "FASTEST_VERIFIED_OBSERVATION",
            "profiled": True,
            "elapsed_ns": best.elapsed_ns,
            "size_class": best.size_class,
        }
