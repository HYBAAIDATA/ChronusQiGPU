"""Exact-PULVINI adaptation of the Geodesic Tensor Engine.

The July 2026 engine assumed an older floating PhiRecursiveOperator contract.
PYTHIPhiMiner's canonical PULVINI core is stricter: exact Fraction values and
an explicitly reversible unimodular pair transform. This module preserves that
canonical authority while recovering the useful tensor-core, geodesic scheduler,
memory-tier, integrity-gate and mining-window planning surfaces.

Boundaries:
* folding is a reversible representation/custody transform, not compression;
* tensor arithmetic here is exact rational arithmetic;
* geodesic scores are scheduling heuristics only;
* the mining planner may only permute an already-valid nonce window.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction
import math
from typing import Any, Callable, Iterable, Sequence

from .math_folding import PulviniFold, pulvini_fold

PHI = (1.0 + math.sqrt(5.0)) / 2.0


def _fraction(value: int | Fraction) -> Fraction:
    if isinstance(value, float):
        raise TypeError("floating-point values are outside the exact tensor contract")
    return Fraction(value)


@dataclass(frozen=True)
class ExactFoldState:
    values: tuple[Fraction, ...]
    original_length: int
    depth: int
    shape: tuple[int, ...]

    def unfold(self) -> tuple[Fraction, ...]:
        current = self.values
        for _ in range(self.depth):
            if len(current) % 2:
                raise ValueError("corrupt folded state length")
            pairs = tuple((current[i], current[i + 1]) for i in range(0, len(current), 2))
            current = PulviniFold(pairs, len(current)).unfold()
        return current[: self.original_length]


def fold_exact(values: Iterable[int | Fraction], *, depth: int = 1,
               shape: tuple[int, ...] | None = None) -> ExactFoldState:
    depth = int(depth)
    if depth < 0:
        raise ValueError("depth must be non-negative")
    original = tuple(_fraction(v) for v in values)
    current = original
    if shape is None:
        shape = (len(original),)
    if math.prod(shape) != len(original):
        raise ValueError("shape does not match value count")
    for _ in range(depth):
        folded = pulvini_fold(current)
        flat: list[Fraction] = []
        for combined, left in folded.pairs:
            flat.extend((combined, left))
        current = tuple(flat)
    state = ExactFoldState(current, len(original), depth, tuple(int(v) for v in shape))
    if state.unfold() != original:
        raise ArithmeticError("recursive exact fold roundtrip failed")
    return state


@dataclass(frozen=True)
class KernelBoundary:
    start: int = 0
    stop: int | None = None

    def normalize(self, length: int) -> tuple[int, int]:
        start = int(self.start)
        stop = length if self.stop is None else int(self.stop)
        if start < 0 or stop < start or stop > length:
            raise ValueError("kernel boundary outside tensor")
        return start, stop


@dataclass
class TensorCoreMetrics:
    operations: int = 0
    exact_roundtrips: int = 0
    values_processed: int = 0


class PhiTensorCore:
    """Exact rational tensor operations over canonical PULVINI states."""

    def __init__(self) -> None:
        self.metrics = TensorCoreMetrics()

    @staticmethod
    def _slice(state: ExactFoldState, boundary: KernelBoundary | None):
        values = state.unfold()
        if boundary is None:
            return values
        start, stop = boundary.normalize(len(values))
        return values[start:stop]

    def _finish(self, values: Sequence[Fraction], *, depth: int,
                shape: tuple[int, ...]) -> ExactFoldState:
        state = fold_exact(values, depth=depth, shape=shape)
        self.metrics.operations += 1
        self.metrics.exact_roundtrips += 1
        self.metrics.values_processed += len(values)
        return state

    def fma(self, a: ExactFoldState, b: ExactFoldState, c: ExactFoldState, *,
            boundary: KernelBoundary | None = None,
            depth: int | None = None) -> ExactFoldState:
        av, bv, cv = (self._slice(state, boundary) for state in (a, b, c))
        if not (len(av) == len(bv) == len(cv)):
            raise ValueError("FMA inputs have incompatible lengths")
        result = tuple(x * y + z for x, y, z in zip(av, bv, cv))
        return self._finish(result, depth=a.depth if depth is None else int(depth),
                            shape=(len(result),))

    def elementwise(self, a: ExactFoldState, b: ExactFoldState,
                    op: Callable[[Fraction, Fraction], Fraction], *,
                    depth: int | None = None) -> ExactFoldState:
        av, bv = a.unfold(), b.unfold()
        if len(av) != len(bv):
            raise ValueError("elementwise inputs have incompatible lengths")
        result = tuple(_fraction(op(x, y)) for x, y in zip(av, bv))
        return self._finish(result, depth=a.depth if depth is None else int(depth),
                            shape=a.shape)

    def reduce_sum(self, state: ExactFoldState) -> Fraction:
        values = state.unfold()
        self.metrics.operations += 1
        self.metrics.values_processed += len(values)
        return sum(values, Fraction(0))

    def matmul(self, a: ExactFoldState, b: ExactFoldState, *,
               depth: int | None = None) -> ExactFoldState:
        if len(a.shape) != 2 or len(b.shape) != 2:
            raise ValueError("matmul requires rank-2 states")
        m, k = a.shape
        k2, n = b.shape
        if k != k2:
            raise ValueError("matmul inner dimensions differ")
        av, bv = a.unfold(), b.unfold()
        out: list[Fraction] = []
        for i in range(m):
            for j in range(n):
                out.append(sum((av[i * k + p] * bv[p * n + j] for p in range(k)), Fraction(0)))
        return self._finish(out, depth=a.depth if depth is None else int(depth), shape=(m, n))


class ManifoldType(Enum):
    EUCLIDEAN = "euclidean"
    PHI_SCALED = "phi_scaled"
    HYPERBOLIC = "hyperbolic"


@dataclass(frozen=True)
class MetricTensor:
    kind: ManifoldType = ManifoldType.PHI_SCALED
    scale: float = PHI

    def distance(self, a: float, b: float) -> float:
        delta = abs(float(a) - float(b))
        if self.kind is ManifoldType.EUCLIDEAN:
            return delta
        if self.kind is ManifoldType.PHI_SCALED:
            return delta / max(self.scale, 1e-15)
        return math.asinh(delta / max(self.scale, 1e-15))

    def geodesic_step(self, current: float, target: float,
                      fraction: float = 0.5) -> float:
        fraction = max(0.0, min(1.0, float(fraction)))
        return float(current) + (float(target) - float(current)) * fraction


@dataclass(order=True)
class GeodesicTask:
    priority: float
    sequence: int
    task_id: str = field(compare=False)
    location: float = field(compare=False)
    payload: Any = field(compare=False, default=None)


class GeodesicScheduler:
    """Deterministic proximity scheduler; it steers ordering, never validity."""

    def __init__(self, metric: MetricTensor | None = None) -> None:
        self.metric = metric or MetricTensor()
        self.position = 0.0
        self._sequence = 0
        self._tasks: list[GeodesicTask] = []

    def submit(self, task_id: str, location: float, payload: Any = None) -> None:
        self._tasks.append(GeodesicTask(
            self.metric.distance(self.position, float(location)), self._sequence,
            str(task_id), float(location), payload,
        ))
        self._sequence += 1

    def drain(self) -> list[GeodesicTask]:
        ordered: list[GeodesicTask] = []
        pending = list(self._tasks)
        self._tasks.clear()
        while pending:
            best = min(pending, key=lambda task: (
                self.metric.distance(self.position, task.location), task.sequence))
            pending.remove(best)
            best.priority = self.metric.distance(self.position, best.location)
            ordered.append(best)
            self.position = best.location
        return ordered


class MemoryTier(Enum):
    REGISTER = 0
    SRAM = 1
    L2 = 2
    HBM = 3


class PhiMemoryHierarchy:
    """Logical fold-depth tiers; no physical-memory or compression claim."""

    DEFAULT_DEPTH = {
        MemoryTier.REGISTER: 0, MemoryTier.SRAM: 1,
        MemoryTier.L2: 2, MemoryTier.HBM: 3,
    }

    def __init__(self) -> None:
        self._objects: dict[str, tuple[MemoryTier, ExactFoldState]] = {}

    def put(self, key: str, state: ExactFoldState,
            tier: MemoryTier = MemoryTier.HBM) -> None:
        self._objects[str(key)] = (tier, state)

    def get(self, key: str) -> ExactFoldState:
        return self._objects[str(key)][1]

    def move(self, key: str, tier: MemoryTier) -> ExactFoldState:
        _, state = self._objects[str(key)]
        moved = fold_exact(state.unfold(), depth=self.DEFAULT_DEPTH[tier], shape=state.shape)
        self._objects[str(key)] = (tier, moved)
        return moved

    def snapshot(self) -> dict[str, Any]:
        return {key: {"tier": tier.name, "depth": state.depth, "shape": state.shape}
                for key, (tier, state) in self._objects.items()}


class TopologicalIntegrityGate:
    """Exact reconstruction and shape gate after transformed operations."""

    def verify(self, state: ExactFoldState,
               expected: Iterable[int | Fraction] | None = None) -> dict[str, Any]:
        values = state.unfold()
        shape_ok = math.prod(state.shape) == len(values)
        expected_ok = True if expected is None else values == tuple(_fraction(v) for v in expected)
        return {
            "passed": bool(shape_ok and expected_ok),
            "shape_ok": bool(shape_ok),
            "exact_reconstruction": bool(expected_ok),
            "depth": state.depth,
            "representation_only": True,
        }

    def require(self, state: ExactFoldState,
                expected: Iterable[int | Fraction] | None = None) -> None:
        report = self.verify(state, expected)
        if not report["passed"]:
            raise ArithmeticError(f"topological integrity gate failed: {report}")


class GeodesicTensorEngine:
    def __init__(self, metric: MetricTensor | None = None) -> None:
        self.core = PhiTensorCore()
        self.scheduler = GeodesicScheduler(metric)
        self.memory = PhiMemoryHierarchy()
        self.integrity = TopologicalIntegrityGate()

    def fold(self, values: Iterable[int | Fraction], *, depth: int = 1,
             shape=None) -> ExactFoldState:
        original = tuple(values)
        state = fold_exact(original, depth=depth, shape=shape)
        self.integrity.require(state, original)
        return state

    def system_report(self) -> dict[str, Any]:
        return {
            "engine": "GeodesicTensorEngine",
            "arithmetic": "exact_rational",
            "fold_authority": "python_backend.core_modules.math_folding",
            "fold_semantics": "reversible_representation_not_compression",
            "scheduler_semantics": "heuristic_ordering_only",
            "tensor_metrics": self.core.metrics.__dict__.copy(),
            "memory": self.memory.snapshot(),
        }


class GeodesicNoncePlanner:
    """Bounded mining planner that can only permute supplied uint32 nonces."""

    consensus_authority = False

    def __init__(self, metric: MetricTensor | None = None, *, fold_depth: int = 3) -> None:
        self.metric = metric or MetricTensor(ManifoldType.PHI_SCALED)
        self.fold_depth = int(fold_depth)
        if self.fold_depth < 0:
            raise ValueError("fold_depth must be non-negative")
        self.integrity = TopologicalIntegrityGate()
        self.last_report: dict[str, Any] | None = None

    @staticmethod
    def _validate_window(candidates: Iterable[int]) -> list[int]:
        window = list(candidates)
        if len(set(window)) != len(window):
            raise ValueError("candidate window contains duplicates")
        for nonce in window:
            if isinstance(nonce, bool) or not isinstance(nonce, int):
                raise TypeError("candidate window must contain integer nonces")
            if not 0 <= nonce <= 0xFFFFFFFF:
                raise ValueError("nonce outside uint32")
        return window

    def order_window(self, candidates: Iterable[int], *, anchor: int | None = None) -> list[int]:
        window = self._validate_window(candidates)
        if not window:
            self.last_report = {"count": 0, "passed": True, "consensus_authority": False}
            return []
        state = fold_exact(window, depth=self.fold_depth, shape=(len(window),))
        self.integrity.require(state, window)
        origin = int(window[0] if anchor is None else anchor)
        ordered = sorted(enumerate(window),
                         key=lambda item: (self.metric.distance(origin, item[1]), item[0]))
        result = [nonce for _, nonce in ordered]
        if sorted(result) != sorted(window):
            raise ArithmeticError("planner changed nonce membership")
        self.last_report = {
            "count": len(window),
            "fold_depth": self.fold_depth,
            "exact_roundtrip": True,
            "permutation_preserved": True,
            "consensus_authority": False,
            "metric": self.metric.kind.value,
        }
        return result


__all__ = [
    "ExactFoldState", "GeodesicNoncePlanner", "GeodesicScheduler", "GeodesicTask",
    "GeodesicTensorEngine", "KernelBoundary", "ManifoldType", "MemoryTier",
    "MetricTensor", "PhiMemoryHierarchy", "PhiTensorCore", "TensorCoreMetrics",
    "TopologicalIntegrityGate", "fold_exact",
]
