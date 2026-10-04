"""Exact-PULVINI Geodesic Tensor Engine for PYTHIPhiMiner.

This is the production adaptation of the July 2026 Geodesic Tensor Engine.
The repository's canonical PULVINI authority is the exact ``Fraction``-based
unimodular pair transform in :mod:`python_backend.core_modules.math_folding`.

Truth boundaries
----------------
* PULVINI folding is a reversible representation/custody transform. No byte,
  HBM, or physical compression ratio is inferred from fold depth.
* Tensor arithmetic in this module is exact rational arithmetic.
* ``unfold_partial`` reconstructs only requested indices and does not build the
  complete original tensor as an intermediate.
* Geodesic scores are scheduling/routing heuristics only.
* ``EnergyModel`` is a declared architectural model, never measured telemetry.
* ``PhiGPU`` is a virtual exact-compute control plane. Physical acceleration is
  owned by Chronus and exposed through the ``tensor`` backend contract.
* ``HybridGPU`` is a routing/control facade; it never simulates a hardware path.
* Mining planners may only permute an already-valid nonce window.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction
from functools import lru_cache
import math
from typing import Any, Callable, Iterable, Sequence

from .math_folding import PulviniFold, pulvini_fold

PHI = (1.0 + math.sqrt(5.0)) / 2.0


def _hash_fractions(values) -> str:
    import hashlib

    digest = hashlib.sha256()
    for value in values:
        digest.update(repr(value).encode("utf-8"))
        digest.update(b"\x00")
    return digest.hexdigest()


def _fraction(value: int | Fraction) -> Fraction:
    if isinstance(value, bool):
        return Fraction(int(value))
    if isinstance(value, float):
        raise TypeError("floating-point values are outside the exact tensor contract")
    return Fraction(value)


@dataclass(frozen=True)
class KernelBoundary:
    """Half-open flat-index boundary for selective tensor reconstruction."""

    start: int = 0
    stop: int | None = None

    @property
    def slice_start(self) -> int:
        return self.start

    @property
    def slice_end(self) -> int | None:
        return self.stop

    @property
    def slice_size(self) -> int | None:
        if self.stop is None:
            return None
        return self.stop - self.start

    def normalize(self, length: int) -> tuple[int, int]:
        start = int(self.start)
        stop = length if self.stop is None else int(self.stop)
        if start < 0 or stop < start or stop > length:
            raise ValueError("kernel boundary outside tensor")
        return start, stop


@dataclass(frozen=True)
class PartialUnfoldStats:
    requested_values: int
    source_values_read: int
    depth: int
    full_length: int
    cone_indices: tuple[int, ...] = ()

    @property
    def reconstructed_fraction(self) -> float:
        if self.full_length == 0:
            return 0.0
        return self.requested_values / self.full_length

    @property
    def dependency_cone(self) -> tuple[int, ...]:
        """Sorted folded-state source indices the decode actually read."""
        return self.cone_indices


@dataclass(frozen=True)
class ExactFoldState:
    values: tuple[Fraction, ...]
    original_length: int
    depth: int
    shape: tuple[int, ...]
    content_hash: str = ""

    def __post_init__(self) -> None:
        if not self.content_hash:
            object.__setattr__(
                self,
                "content_hash",
                self._digest_header() + _hash_fractions(self.values),
            )

    def _digest_header(self) -> str:
        import hashlib

        digest = hashlib.sha256()
        digest.update(repr(tuple(self.shape)).encode("utf-8"))
        digest.update(int(self.original_length).to_bytes(8, "little"))
        digest.update(int(self.depth).to_bytes(8, "little"))
        return digest.hexdigest() + ":"

    def verify_content_hash(self) -> bool:
        """Recompute the content digest; False means custody was altered."""
        return bool(self.content_hash) and self.content_hash == (
            self._digest_header() + _hash_fractions(self.values)
        )

    def unfold(self) -> tuple[Fraction, ...]:
        """Canonical full inverse, retained as the reference implementation."""
        current = self.values
        for _ in range(self.depth):
            if len(current) % 2:
                raise ValueError("corrupt folded state length")
            pairs = tuple((current[i], current[i + 1]) for i in range(0, len(current), 2))
            current = PulviniFold(pairs, len(current)).unfold()
        return current[: self.original_length]

    def unfold_partial(self, boundary: KernelBoundary) -> tuple[Fraction, ...]:
        return unfold_partial(self, boundary)

    def unfold_partial_with_stats(
        self, boundary: KernelBoundary
    ) -> tuple[tuple[Fraction, ...], PartialUnfoldStats]:
        return unfold_partial_with_stats(self, boundary)


def fold_exact(
    values: Iterable[int | Fraction],
    *,
    depth: int = 1,
    shape: tuple[int, ...] | None = None,
) -> ExactFoldState:
    depth = int(depth)
    if depth < 0:
        raise ValueError("depth must be non-negative")
    original = tuple(_fraction(v) for v in values)
    current = original
    if shape is None:
        shape = (len(original),)
    shape = tuple(int(v) for v in shape)
    if math.prod(shape) != len(original):
        raise ValueError("shape does not match value count")
    for _ in range(depth):
        folded = pulvini_fold(current)
        flat: list[Fraction] = []
        for combined, left in folded.pairs:
            flat.extend((combined, left))
        current = tuple(flat)
    state = ExactFoldState(current, len(original), depth, shape)
    if state.unfold() != original:
        raise ArithmeticError("recursive exact fold roundtrip failed")
    return state


def unfold_partial_with_stats(
    state: ExactFoldState, boundary: KernelBoundary
) -> tuple[tuple[Fraction, ...], PartialUnfoldStats]:
    """Reconstruct only a requested flat slice from an exact folded state.

    One PULVINI pair stores ``(combined=a+b, left=a)``. Therefore one inverse
    level is ``x[2p]=folded[2p+1]`` and
    ``x[2p+1]=folded[2p]-folded[2p+1]``. Applying this relation recursively to
    only requested indices avoids materialising the full tensor. Memoisation
    shares dependencies, and returned statistics make the bounded work testable.
    """
    start, stop = boundary.normalize(state.original_length)
    values, stats = unfold_values_at(state, range(start, stop))
    return values, stats


def unfold_values_at(
    state: ExactFoldState, indices: Iterable[int]
) -> tuple[tuple[Fraction, ...], PartialUnfoldStats]:
    """Reconstruct an arbitrary set of flat indices and expose its cone.

    One memoized recovery pass serves every requested index, so shared
    dependencies are read once. ``PartialUnfoldStats.cone_indices`` is the
    sorted set of folded-state source positions the decode touched — the
    exact dependency cone of the requested outputs.
    """
    flat_indices = [int(i) for i in indices]
    source_indices: set[int] = set()

    @lru_cache(maxsize=None)
    def recover(level: int, index: int) -> Fraction:
        if index < 0 or index >= len(state.values):
            raise ValueError("corrupt folded state index")
        if level == 0:
            source_indices.add(index)
            return state.values[index]
        if index % 2 == 0:
            return recover(level - 1, index + 1)
        return recover(level - 1, index - 1) - recover(level - 1, index)

    values = tuple(recover(state.depth, index) for index in flat_indices)
    stats = PartialUnfoldStats(
        requested_values=len(flat_indices),
        source_values_read=len(source_indices),
        depth=state.depth,
        full_length=state.original_length,
        cone_indices=tuple(sorted(source_indices)),
    )
    return values, stats


def unfold_region(
    state: ExactFoldState, slices: tuple[object, ...]
) -> tuple[tuple[Fraction, ...], PartialUnfoldStats, tuple[int, ...]]:
    """Reconstruct a shaped region (per-axis box) and return its cone.

    ``slices`` is one ``slice`` (or ``int``) per axis of ``state.shape``.
    Returns ``(values_in_region_order, stats, region_shape)`` — the values in
    C-order region layout plus the measured dependency cone.
    """
    if len(slices) != len(state.shape):
        raise ValueError(
            f"region has {len(slices)} entries for a rank-{len(state.shape)} tensor"
        )
    region_shape: list[int] = []
    per_axis: list[list[int]] = []
    strides = _strides(state.shape)
    for axis, (dim, spec) in enumerate(zip(state.shape, slices)):
        if isinstance(spec, slice):
            if (spec.step or 1) != 1:
                raise ValueError("region decode supports unit-step slices only")
            for bound in (spec.start, spec.stop):
                if bound is not None and (
                    int(bound) > int(dim) or int(bound) < -int(dim)
                ):
                    raise ValueError(
                        f"region axis {axis} slice {spec!r} is outside dim {dim}"
                    )
            start, stop, _ = spec.indices(int(dim))
            if start < 0 or stop > int(dim) or stop < start:
                raise ValueError(f"region axis {axis} slice outside dim {dim}")
            coords = list(range(start, stop))
        elif isinstance(spec, int) and not isinstance(spec, bool):
            pos = int(spec) % int(dim)
            coords = [pos]
        else:
            raise ValueError(f"unsupported region specifier {spec!r} on axis {axis}")
        if not coords:
            raise ValueError("region is empty")
        per_axis.append(coords)
        region_shape.append(len(coords))
    import itertools as _it

    flat_indices = [
        sum(coord * stride for coord, stride in zip(point, strides))
        for point in _it.product(*per_axis)
    ]
    values, stats = unfold_values_at(state, flat_indices)
    return values, stats, tuple(region_shape)


def _strides(shape: tuple[int, ...]) -> tuple[int, ...]:
    strides: list[int] = []
    running = 1
    for dim in reversed(shape):
        strides.append(running)
        running *= int(dim)
    return tuple(reversed(strides))


def unfold_partial(state: ExactFoldState, boundary: KernelBoundary) -> tuple[Fraction, ...]:
    return unfold_partial_with_stats(state, boundary)[0]


@dataclass
class TensorCoreMetrics:
    operations: int = 0
    exact_roundtrips: int = 0
    values_processed: int = 0
    partial_unfolds: int = 0
    partial_values_requested: int = 0
    partial_source_values_read: int = 0


class PhiTensorCore:
    """Exact rational tensor operations over canonical PULVINI states."""

    def __init__(self) -> None:
        self.metrics = TensorCoreMetrics()

    def _slice(
        self, state: ExactFoldState, boundary: KernelBoundary | None
    ) -> tuple[Fraction, ...]:
        if boundary is None:
            return state.unfold()
        values, stats = state.unfold_partial_with_stats(boundary)
        self.metrics.partial_unfolds += 1
        self.metrics.partial_values_requested += stats.requested_values
        self.metrics.partial_source_values_read += stats.source_values_read
        return values

    def _finish(
        self, values: Sequence[Fraction], *, depth: int, shape: tuple[int, ...]
    ) -> ExactFoldState:
        state = fold_exact(values, depth=depth, shape=shape)
        self.metrics.operations += 1
        self.metrics.exact_roundtrips += 1
        self.metrics.values_processed += len(values)
        return state

    def fma(
        self,
        a: ExactFoldState,
        b: ExactFoldState,
        c: ExactFoldState,
        *,
        boundary: KernelBoundary | None = None,
        depth: int | None = None,
    ) -> ExactFoldState:
        av, bv, cv = (self._slice(state, boundary) for state in (a, b, c))
        if not (len(av) == len(bv) == len(cv)):
            raise ValueError("FMA inputs have incompatible lengths")
        result = tuple(x * y + z for x, y, z in zip(av, bv, cv))
        return self._finish(
            result,
            depth=a.depth if depth is None else int(depth),
            shape=(len(result),),
        )

    def elementwise(
        self,
        a: ExactFoldState,
        b: ExactFoldState,
        op: Callable[[Fraction, Fraction], Fraction],
        *,
        boundary: KernelBoundary | None = None,
        depth: int | None = None,
    ) -> ExactFoldState:
        av, bv = self._slice(a, boundary), self._slice(b, boundary)
        if len(av) != len(bv):
            raise ValueError("elementwise inputs have incompatible lengths")
        result = tuple(_fraction(op(x, y)) for x, y in zip(av, bv))
        shape = a.shape if boundary is None else (len(result),)
        return self._finish(
            result,
            depth=a.depth if depth is None else int(depth),
            shape=shape,
        )

    def reduce_sum(
        self, state: ExactFoldState, *, boundary: KernelBoundary | None = None
    ) -> Fraction:
        values = self._slice(state, boundary)
        self.metrics.operations += 1
        self.metrics.values_processed += len(values)
        return sum(values, Fraction(0))

    def matmul(
        self, a: ExactFoldState, b: ExactFoldState, *, depth: int | None = None
    ) -> ExactFoldState:
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
                out.append(
                    sum(
                        (av[i * k + p] * bv[p * n + j] for p in range(k)),
                        Fraction(0),
                    )
                )
        return self._finish(
            out,
            depth=a.depth if depth is None else int(depth),
            shape=(m, n),
        )


class ManifoldType(Enum):
    EUCLIDEAN = "euclidean"
    PHI_SCALED = "phi_scaled"
    HYPERBOLIC = "hyperbolic"


def _vector(value: float | Sequence[float]) -> tuple[float, ...]:
    if isinstance(value, (int, float)):
        return (float(value),)
    return tuple(float(v) for v in value)


@dataclass(frozen=True)
class MetricTensor:
    kind: ManifoldType = ManifoldType.PHI_SCALED
    scale: float = PHI
    dimension: int = 1

    def __post_init__(self) -> None:
        if self.scale <= 0 or not math.isfinite(self.scale):
            raise ValueError("metric scale must be finite and positive")
        if self.dimension < 1:
            raise ValueError("metric dimension must be positive")

    @classmethod
    def euclidean(cls, dim: int = 4) -> "MetricTensor":
        return cls(ManifoldType.EUCLIDEAN, 1.0, int(dim))

    @classmethod
    def phi_scaled(cls, dim: int = 4) -> "MetricTensor":
        return cls(ManifoldType.PHI_SCALED, PHI, int(dim))

    @classmethod
    def hyperbolic(cls, dim: int = 4) -> "MetricTensor":
        return cls(ManifoldType.HYPERBOLIC, PHI, int(dim))

    def distance(
        self, a: float | Sequence[float], b: float | Sequence[float]
    ) -> float:
        av, bv = _vector(a), _vector(b)
        if len(av) != len(bv):
            raise ValueError("metric points have different dimensions")
        norm = math.sqrt(sum((x - y) ** 2 for x, y in zip(av, bv)))
        if self.kind is ManifoldType.EUCLIDEAN:
            return norm
        if self.kind is ManifoldType.PHI_SCALED:
            return norm / self.scale
        return math.asinh(norm / self.scale)

    def geodesic_step(
        self,
        current: float | Sequence[float],
        target: float | Sequence[float],
        fraction: float = 0.5,
    ) -> float | tuple[float, ...]:
        fraction = max(0.0, min(1.0, float(fraction)))
        cv, tv = _vector(current), _vector(target)
        if len(cv) != len(tv):
            raise ValueError("metric points have different dimensions")
        result = tuple(c + (t - c) * fraction for c, t in zip(cv, tv))
        if isinstance(current, (int, float)) and isinstance(target, (int, float)):
            return result[0]
        return result

    def walk_manifold(
        self,
        start: float | Sequence[float],
        target: float | Sequence[float],
        *,
        max_steps: int = 100,
        step_fraction: float = 0.1,
        tolerance: float = 1e-9,
    ) -> tuple[float | tuple[float, ...], ...]:
        if max_steps < 0:
            raise ValueError("max_steps must be non-negative")
        current: float | tuple[float, ...]
        current = float(start) if isinstance(start, (int, float)) else _vector(start)
        path: list[float | tuple[float, ...]] = [current]
        for _ in range(max_steps):
            if self.distance(current, target) <= tolerance:
                break
            current = self.geodesic_step(current, target, step_fraction)
            path.append(current)
        return tuple(path)


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
        self._tasks.append(
            GeodesicTask(
                self.metric.distance(self.position, float(location)),
                self._sequence,
                str(task_id),
                float(location),
                payload,
            )
        )
        self._sequence += 1

    def drain(self) -> list[GeodesicTask]:
        ordered: list[GeodesicTask] = []
        pending = list(self._tasks)
        self._tasks.clear()
        while pending:
            best = min(
                pending,
                key=lambda task: (
                    self.metric.distance(self.position, task.location),
                    task.sequence,
                ),
            )
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
        MemoryTier.REGISTER: 0,
        MemoryTier.SRAM: 1,
        MemoryTier.L2: 2,
        MemoryTier.HBM: 3,
    }

    def __init__(self) -> None:
        self._objects: dict[str, tuple[MemoryTier, ExactFoldState]] = {}

    def put(
        self, key: str, state: ExactFoldState, tier: MemoryTier = MemoryTier.HBM
    ) -> None:
        self._objects[str(key)] = (tier, state)

    def get(self, key: str) -> ExactFoldState:
        return self._objects[str(key)][1]

    def move(self, key: str, tier: MemoryTier) -> ExactFoldState:
        _, state = self._objects[str(key)]
        moved = fold_exact(
            state.unfold(), depth=self.DEFAULT_DEPTH[tier], shape=state.shape
        )
        self._objects[str(key)] = (tier, moved)
        return moved

    def snapshot(self) -> dict[str, Any]:
        return {
            key: {"tier": tier.name, "depth": state.depth, "shape": state.shape}
            for key, (tier, state) in self._objects.items()
        }


class TopologicalIntegrityGate:
    """Exact reconstruction and shape gate after transformed operations."""

    def verify(
        self,
        state: ExactFoldState,
        expected: Iterable[int | Fraction] | None = None,
    ) -> dict[str, Any]:
        values = state.unfold()
        shape_ok = math.prod(state.shape) == len(values)
        expected_ok = (
            True
            if expected is None
            else values == tuple(_fraction(v) for v in expected)
        )
        return {
            "passed": bool(shape_ok and expected_ok),
            "shape_ok": bool(shape_ok),
            "exact_reconstruction": bool(expected_ok),
            "depth": state.depth,
            "representation_only": True,
        }

    def require(
        self,
        state: ExactFoldState,
        expected: Iterable[int | Fraction] | None = None,
    ) -> None:
        report = self.verify(state, expected)
        if not report["passed"]:
            raise ArithmeticError(f"topological integrity gate failed: {report}")


@dataclass(frozen=True)
class EnergyModel:
    """Declared architectural energy model; never measured telemetry."""

    fma_pj_per_op: float = 0.3
    hbm_fetch_pj_per_byte: float = 10.0
    sram_fetch_pj_per_byte: float = 1.0
    register_pj_per_byte: float = 0.1
    unfold_pj_per_element: float = 0.5
    fold_pj_per_element: float = 0.5
    folded_access_pj_per_byte: float = 0.1

    def traditional_energy(
        self,
        flops: int,
        bytes_moved: int,
        *,
        hbm_fraction: float = 0.7,
        sram_fraction: float = 0.2,
        register_fraction: float = 0.1,
    ) -> dict[str, float | str | bool]:
        fractions = hbm_fraction + sram_fraction + register_fraction
        if abs(fractions - 1.0) > 1e-9:
            raise ValueError("memory fractions must sum to 1")
        compute = int(flops) * self.fma_pj_per_op
        hbm = int(bytes_moved) * hbm_fraction * self.hbm_fetch_pj_per_byte
        sram = int(bytes_moved) * sram_fraction * self.sram_fetch_pj_per_byte
        register = int(bytes_moved) * register_fraction * self.register_pj_per_byte
        total = compute + hbm + sram + register
        return {
            "total_pj": total,
            "compute_pj": compute,
            "hbm_pj": hbm,
            "sram_pj": sram,
            "register_pj": register,
            "movement_fraction": (hbm + sram + register) / max(total, 1e-12),
            "compute_fraction": compute / max(total, 1e-12),
            "truth_class": "declared_model",
            "measured": False,
        }

    def phi_gpu_energy(
        self,
        flops: int,
        slice_size: int,
        fold_depth: int,
        folded_bytes: int,
    ) -> dict[str, float | str | bool]:
        compute = int(flops) * self.fma_pj_per_op
        unfold = int(slice_size) * int(fold_depth) * self.unfold_pj_per_element
        fold = int(slice_size) * int(fold_depth) * self.fold_pj_per_element
        access = int(folded_bytes) * self.folded_access_pj_per_byte
        total = compute + unfold + fold + access
        return {
            "total_pj": total,
            "compute_pj": compute,
            "unfold_pj": unfold,
            "fold_pj": fold,
            "folded_access_pj": access,
            "movement_fraction": access / max(total, 1e-12),
            "compute_fraction": (compute + unfold + fold) / max(total, 1e-12),
            "truth_class": "declared_model",
            "measured": False,
        }

    def compare(
        self,
        *,
        flops: int,
        bytes_moved: int,
        slice_size: int,
        fold_depth: int,
        folded_bytes: int,
    ) -> dict[str, Any]:
        traditional = self.traditional_energy(flops, bytes_moved)
        phi = self.phi_gpu_energy(flops, slice_size, fold_depth, folded_bytes)
        savings = float(traditional["total_pj"]) - float(phi["total_pj"])
        return {
            "traditional": traditional,
            "phi_gpu": phi,
            "energy_savings_pj": savings,
            "energy_reduction_pct": (
                savings / max(float(traditional["total_pj"]), 1e-12) * 100.0
            ),
            "claim_lane": "INTERNAL",
            "truth_class": "declared_model",
            "measured": False,
        }


@dataclass(frozen=True)
class KernelLaunchConfig:
    grid_dim: tuple[int, int] = (1, 1)
    block_dim: tuple[int, int] = (1, 1)
    fold_depth: int = 3
    element_bytes: int | None = None

    def __post_init__(self) -> None:
        if any(int(v) < 1 for v in (*self.grid_dim, *self.block_dim)):
            raise ValueError("grid/block dimensions must be positive")
        if self.fold_depth < 0:
            raise ValueError("fold_depth must be non-negative")
        if self.element_bytes is not None and self.element_bytes < 1:
            raise ValueError("element_bytes must be positive when declared")

    @property
    def total_threads(self) -> int:
        return math.prod(self.grid_dim) * math.prod(self.block_dim)

    @property
    def num_blocks(self) -> int:
        return math.prod(self.grid_dim)


class GeodesicTensorEngine:
    def __init__(self, metric: MetricTensor | None = None) -> None:
        self.core = PhiTensorCore()
        self.scheduler = GeodesicScheduler(metric)
        self.memory = PhiMemoryHierarchy()
        self.integrity = TopologicalIntegrityGate()

    def fold(
        self,
        values: Iterable[int | Fraction],
        *,
        depth: int = 1,
        shape: tuple[int, ...] | None = None,
    ) -> ExactFoldState:
        original = tuple(values)
        state = fold_exact(original, depth=depth, shape=shape)
        self.integrity.require(state, original)
        return state

    def system_report(self) -> dict[str, Any]:
        return {
            "engine": "GeodesicTensorEngine",
            "arithmetic": "exact_rational",
            "fold_authority": "python_backend.core_modules.math_folding",
            "fold_semantics": "reversible_representation_not_physical_compression",
            "partial_unfold": "slice_only_recursive_inverse",
            "scheduler_semantics": "heuristic_ordering_only",
            "tensor_metrics": self.core.metrics.__dict__.copy(),
            "memory": self.memory.snapshot(),
        }


class PhiGPU:
    """Virtual exact-compute facade preserving the July PhiGPU control surface.

    It distributes exact PULVINI FMA slices across logical ``PhiTensorCore``
    instances. It is deliberately not a hardware backend; physical GPU dispatch
    belongs to ``chronus.tensor_compute`` through the ``tensor`` contracts.
    """

    def __init__(
        self,
        num_cores: int = 32,
        *,
        fold_depth: int = 3,
        metric: MetricTensor | None = None,
    ) -> None:
        if num_cores < 1:
            raise ValueError("num_cores must be positive")
        self.num_cores = int(num_cores)
        self.fold_depth = int(fold_depth)
        self.engine = GeodesicTensorEngine(metric)
        self.cores = [PhiTensorCore() for _ in range(self.num_cores)]
        self.energy_model = EnergyModel()
        self.kernel_launches = 0

    def store(
        self,
        key: str,
        values: Iterable[int | Fraction],
        *,
        shape: tuple[int, ...] | None = None,
        tier: MemoryTier = MemoryTier.HBM,
    ) -> ExactFoldState:
        state = self.engine.fold(values, depth=self.fold_depth, shape=shape)
        self.engine.memory.put(key, state, tier)
        return state

    def launch_fma(
        self,
        key_a: str,
        key_b: str,
        key_c: str,
        config: KernelLaunchConfig | None = None,
    ) -> dict[str, Any]:
        config = config or KernelLaunchConfig(fold_depth=self.fold_depth)
        a = self.engine.memory.get(key_a)
        b = self.engine.memory.get(key_b)
        c = self.engine.memory.get(key_c)
        if not (a.original_length == b.original_length == c.original_length):
            raise ValueError("FMA operands have different lengths")
        total = a.original_length
        blocks = max(1, min(config.num_blocks, total or 1))
        block_size = max(1, math.ceil(total / blocks))
        slices: list[tuple[int, tuple[Fraction, ...]]] = []
        source_reads = 0
        for block in range(blocks):
            start = block * block_size
            stop = min(total, start + block_size)
            if start >= stop:
                continue
            boundary = KernelBoundary(start, stop)
            core = self.cores[block % self.num_cores]
            before_reads = core.metrics.partial_source_values_read
            result = core.fma(a, b, c, boundary=boundary, depth=config.fold_depth)
            slices.append((start, result.unfold()))
            source_reads += core.metrics.partial_source_values_read - before_reads
        slices.sort(key=lambda item: item[0])
        combined = tuple(value for _, values in slices for value in values)
        result = fold_exact(combined, depth=config.fold_depth, shape=(len(combined),))
        expected = tuple(x * y + z for x, y, z in zip(a.unfold(), b.unfold(), c.unfold()))
        self.engine.integrity.require(result, expected)
        self.kernel_launches += 1
        energy = None
        if config.element_bytes is not None:
            energy = self.energy_model.compare(
                flops=2 * total,
                bytes_moved=3 * total * config.element_bytes,
                slice_size=block_size,
                fold_depth=config.fold_depth,
                folded_bytes=total * config.element_bytes,
            )
        return {
            "result": result,
            "blocks": len(slices),
            "logical_cores": self.num_cores,
            "partial_source_values_read": source_reads,
            "energy_model": energy,
            "execution_class": "virtual_exact_control_plane",
            "hardware_accelerated": False,
        }

    def get_system_report(self) -> dict[str, Any]:
        return {
            "system": "PhiGPU compatibility facade",
            "logical_cores": self.num_cores,
            "kernel_launches": self.kernel_launches,
            "execution_class": "virtual_exact_control_plane",
            "physical_backend": "Chronus (separate tensor backend)",
            "hardware_claim": False,
        }


class ComputeUnitType(Enum):
    PHI_NATIVE = "phi_native"
    TRADITIONAL = "traditional"


class HybridGPU:
    """Compatibility facade for hybrid workload routing, without simulation."""

    def __init__(self, *, structured_threshold: int = 256) -> None:
        if structured_threshold < 1:
            raise ValueError("structured_threshold must be positive")
        self.structured_threshold = int(structured_threshold)
        self.phi_operations = 0
        self.traditional_operations = 0

    @staticmethod
    def _size(data: Any) -> int:
        size = getattr(data, "size", None)
        if size is not None:
            return int(size)
        try:
            return len(data)
        except TypeError:
            return 1

    def route_workload(
        self, data: Any, is_structured: bool = True
    ) -> ComputeUnitType:
        if is_structured and self._size(data) >= self.structured_threshold:
            self.phi_operations += 1
            return ComputeUnitType.PHI_NATIVE
        self.traditional_operations += 1
        return ComputeUnitType.TRADITIONAL

    def execute(
        self,
        data: Any,
        *,
        is_structured: bool,
        phi_executor: Callable[[], Any],
        traditional_executor: Callable[[], Any],
    ) -> dict[str, Any]:
        route = self.route_workload(data, is_structured=is_structured)
        result = phi_executor() if route is ComputeUnitType.PHI_NATIVE else traditional_executor()
        return {
            "route": route.value,
            "result": result,
            "simulated": False,
            "routing_only": True,
        }

    def get_hybrid_report(self) -> dict[str, Any]:
        total = self.phi_operations + self.traditional_operations
        return {
            "phi_operations": self.phi_operations,
            "traditional_operations": self.traditional_operations,
            "phi_fraction": self.phi_operations / max(total, 1),
            "traditional_fraction": self.traditional_operations / max(total, 1),
            "claim_lane": "INTERNAL_CONTROL_PLANE",
            "simulated_hardware": False,
        }


class GeodesicNoncePlanner:
    """Bounded mining planner that can only permute supplied uint32 nonces."""

    consensus_authority = False

    def __init__(
        self, metric: MetricTensor | None = None, *, fold_depth: int = 3
    ) -> None:
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

    def order_window(
        self, candidates: Iterable[int], *, anchor: int | None = None
    ) -> list[int]:
        window = self._validate_window(candidates)
        if not window:
            self.last_report = {
                "count": 0,
                "passed": True,
                "consensus_authority": False,
            }
            return []
        state = fold_exact(window, depth=self.fold_depth, shape=(len(window),))
        self.integrity.require(state, window)
        origin = int(window[0] if anchor is None else anchor)
        ordered = sorted(
            enumerate(window),
            key=lambda item: (self.metric.distance(origin, item[1]), item[0]),
        )
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
    "ComputeUnitType",
    "EnergyModel",
    "ExactFoldState",
    "GeodesicNoncePlanner",
    "GeodesicScheduler",
    "GeodesicTask",
    "GeodesicTensorEngine",
    "HybridGPU",
    "KernelBoundary",
    "KernelLaunchConfig",
    "ManifoldType",
    "MemoryTier",
    "MetricTensor",
    "PartialUnfoldStats",
    "PhiGPU",
    "PhiMemoryHierarchy",
    "PhiTensorCore",
    "TensorCoreMetrics",
    "TopologicalIntegrityGate",
    "fold_exact",
    "unfold_partial",
    "unfold_partial_with_stats",
    "unfold_region",
    "unfold_values_at",
]
