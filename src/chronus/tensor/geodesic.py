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
        if not math.isfinite(tolerance) or tolerance < 0:
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
        if a.dtype.kind in "iu" and e.dtype.kind in "iu":
            # Fixed-width subtraction can overflow and turn a large error negative.
            delta = np.abs(a.astype(object) - e.astype(object))
        elif a.dtype.kind == "b" and e.dtype.kind == "b":
            delta = np.not_equal(a, e)
        else:
            delta = np.abs(a - e)
        error = float(np.max(delta)) if a.size else 0.0
        passed = bool(dtype_match and np.all(np.isfinite(a)) and np.all(np.isfinite(e))
                      and error <= self.tolerance)
        if passed:
            self.checks_passed += 1
        return IntegrityVerdict(passed, error, shape_match, dtype_match)

    def verify_float32_matmul(
        self, actual: np.ndarray, left: np.ndarray, right: np.ndarray
    ) -> IntegrityVerdict:
        """Check GPU float32 GEMM against a bounded componentwise Higham bound.

        Conservatively gamma_(2k) = 2k*u/(1-2k*u), u=2**-24,
        covering non-fused multiplication followed by accumulation. The operands are the exact
        float32 input values promoted to float64 for the reference product.
        This tests output numerical integrity; it does NOT certify hardware,
        prove an error-free algorithm, or supply a speedup observation.
        """
        self.checks_performed += 1
        a, b, result = np.asarray(left), np.asarray(right), np.asarray(actual)
        shape_ok = bool(
            a.ndim == 2 and b.ndim == 2 and result.ndim == 2
            and a.shape[1] == b.shape[0]
            and result.shape == (a.shape[0], b.shape[1])
        )
        dtype_ok = bool(
            a.dtype == np.dtype("float32")
            and b.dtype == np.dtype("float32")
            and result.dtype == np.dtype("float32")
        )
        if not shape_ok or not dtype_ok:
            return IntegrityVerdict(False, float("inf"), shape_ok, dtype_ok)
        k = a.shape[1]
        unit_roundoff = 2.0 ** -24
        if not k or 2 * k * unit_roundoff >= 1.0 or result.size > 16_777_216:
            return IntegrityVerdict(False, float("inf"), shape_ok, dtype_ok)
        if not (np.all(np.isfinite(a)) and np.all(np.isfinite(b))
                and np.all(np.isfinite(result))):
            return IntegrityVerdict(False, float("inf"), shape_ok, dtype_ok)
        aa, bb = a.astype(np.float64), b.astype(np.float64)
        with np.errstate(over="ignore", invalid="ignore"):
            reference = aa @ bb
            magnitude = np.abs(aa) @ np.abs(bb)
            gamma_k = (2 * k * unit_roundoff) / (1.0 - 2 * k * unit_roundoff)
            # Reference float64 GEMM also rounds; its error budget is
            # explicitly included rather than assumed to be exact.
            gamma64 = (2 * k * 2.0 ** -53) / (1.0 - 2 * k * 2.0 ** -53)
            # Purely relative error bounds exclude floating-point
            # underflow. Each non-fused multiply/add may incur an
            # absolute subnormal rounding error. This allowance does
            # not admit flush-to-zero on ordinary subnormal products.
            eta = float(np.nextafter(np.float32(0), np.float32(1)))
            bound = (gamma_k + gamma64) * magnitude + (2 * k * eta)
            difference = np.abs(result.astype(np.float64) - reference)
        if not (np.all(np.isfinite(reference)) and np.all(np.isfinite(bound))
                and np.all(np.isfinite(difference))):
            return IntegrityVerdict(False, float("inf"), shape_ok, dtype_ok)
        error = float(np.max(difference)) if difference.size else 0.0
        passed = bool(np.all(difference <= bound))
        if passed:
            self.checks_passed += 1
        return IntegrityVerdict(passed, error, shape_ok, dtype_ok)


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
        # Recover the input/output memory and finite-data gates from the archived
        # Chronos ONE iGPU v3.10 tensor_runtime.py. This is a host reference
        # execution budget, not a claimed physical SRAM/HBM measurement.
        max_elements = 1_000_000
        if any(a.size > max_elements or not np.issubdtype(a.dtype, np.number)
               or not np.isfinite(a).all() for a in arrays):
            raise ValueError("reference tensor input exceeds finite numeric policy")
        if op == "kron" and len(arrays) == 2 and arrays[0].size * arrays[1].size > max_elements:
            raise ValueError("reference tensor Kronecker output exceeds element budget")
        if op == "matmul" and len(arrays) == 2 and arrays[0].ndim == arrays[1].ndim == 2 and arrays[0].shape[0] * arrays[1].shape[1] > max_elements:
            raise ValueError("reference tensor matrix output exceeds element budget")
        if op == "scale" and scalar is not None and not np.isfinite(scalar):
            raise ValueError("reference tensor scale must be finite")
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
        if result.size > max_elements or not np.isfinite(result).all():
            raise ValueError("reference tensor output exceeds finite numeric policy")
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

    def __init__(self, capacity_bytes: dict[str, int] | None = None) -> None:
        self._storage: dict[str, dict[str, ExactFoldState]] = {}
        self.capacity_bytes = dict(capacity_bytes or {})
        if any(tier not in self.TIERS or type(limit) is not int or limit < 1
               for tier, limit in self.capacity_bytes.items()):
            raise ValueError("tier capacity must name a valid tier and positive byte count")
        self._hits = 0
        self._misses = 0
        self._promotions = 0

    def _check_capacity(self, key: str, state: ExactFoldState, tier: str) -> None:
        used = sum(len(states[tier].folded) for name, states in self._storage.items()
                   if name != key and tier in states)
        if tier in self.capacity_bytes and used + len(state.folded) > self.capacity_bytes[tier]:
            raise MemoryError("folded residency exceeds configured tier byte budget")

    def telemetry(self) -> dict:
        return {"scope": "software_residency_not_physical_cache", "hits": self._hits,
                "misses": self._misses, "tier_transfers": self._promotions,
                "resident_bytes": {tier: sum(len(states[tier].folded) for states in self._storage.values()
                                             if tier in states) for tier in self.TIERS},
                "capacity_bytes": dict(self.capacity_bytes)}

    def store(self, key: str, value: np.ndarray, tier: str = "hbm") -> ExactFoldState:
        if tier not in self.TIERS:
            raise ValueError("unknown memory tier")
        if not key:
            raise ValueError("key is required")
        state = ExactFoldState.from_array(np.asarray(value))
        self._check_capacity(key, state, tier)
        self._storage.setdefault(key, {})[tier] = state
        return state

    def state(self, key: str, tier: str = "hbm") -> ExactFoldState:
        try:
            state = self._storage[key][tier]
        except KeyError:
            self._misses += 1
            raise
        self._hits += 1
        return state

    def load(self, key: str, tier: str = "hbm") -> np.ndarray:
        return self.state(key, tier).unfold_array()

    def load_rows(self, key: str, start: int, stop: int, tier: str = "hbm") -> np.ndarray:
        return self.state(key, tier).unfold_rows(start, stop)

    def promote(self, key: str, source: str, target: str) -> None:
        if source not in self.TIERS or target not in self.TIERS:
            raise ValueError("unknown memory tier")
        state = self.state(key, source)
        self._check_capacity(key, state, target)
        self._storage.setdefault(key, {})[target] = state
        self._promotions += 1

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
