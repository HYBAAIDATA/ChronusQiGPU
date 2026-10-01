"""Chronus phi GPU — the virtual phi-native device model.

The GPU plane of the geodesic engine: :class:`GeodesicScheduler` orders
kernel work by hyperbolic manifold proximity ``d_phi = log_phi(max(|a|,|b|))``
and drives fold-depth promote/demote on the ``aethel.phi_memory`` tiers;
:class:`PhiGPU` launches kernels across 32 cores (one per M_32 face) through
:class:`kellogg.phi_tensor_core.PhiTensorCore`; :class:`HybridGPU` routes
structured workloads to the phi-native path and irregular ones to the
traditional path; :class:`EnergyModel` compares the declared energy
coefficients.

Claim discipline: every report carries ``truth_class`` — ``internal`` for
software-emulated execution on the host, ``model`` for energy arithmetic.
Nothing here asserts a physical-device property; measured hardware numbers
come from ``chronus.telemetry`` on real devices only.
"""

from __future__ import annotations

import heapq
import logging
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from aethel.phi_fold import KernelBoundary, phi_unfold
from aethel.phi_memory import MemoryTier, PhiMemoryHierarchy, TopologicalIntegrityGate
from kellogg.phi_tensor_core import PhiTensorCore

logger = logging.getLogger("chronus.phi_gpu")

PHI = (1.0 + math.sqrt(5.0)) / 2.0
PHI_GPU_CORES = 32  # one core per M_32 face


class PhiGPUError(RuntimeError):
    """A phi-GPU dispatch, launch, or routing contract was violated."""


def phi_log_distance(a: float, b: float) -> float:
    """Scheduler distance ``d_phi = log_phi(max(|a|, |b|))``.

    This is the simplified hyperbolic distance declared in the engine
    record — the full Riemannian metric tensor is
    ``kellogg.phi_tensor_core.MetricTensor.hyperbolic``.
    """
    m = max(abs(float(a)), abs(float(b)))
    if m <= 0:
        return 0.0
    return math.log(m) / math.log(PHI)


# -- GeodesicScheduler ---------------------------------------------------------


@dataclass(order=True)
class _ScheduledItem:
    distance: float
    sequence: int
    task: "KernelTask" = field(compare=False)


@dataclass
class KernelTask:
    """One schedulable unit: a callable over a manifold position."""

    name: str
    position: float
    payload: Any = None
    resident: Optional[str] = None


class GeodesicScheduler:
    """Warp-scheduler analogue: orders queued kernels by manifold
    proximity to the reference position and promotes/demotes fold depths
    so near work rides shallow folds and far work sinks toward HBM."""

    def __init__(
        self,
        memory: Optional[PhiMemoryHierarchy] = None,
        near_depth: int = 1,
        far_depth: int = 3,
    ) -> None:
        self.memory = memory if memory is not None else PhiMemoryHierarchy()
        self.near_depth = int(near_depth)
        self.far_depth = int(far_depth)
        self._queue: List[_ScheduledItem] = []
        self._sequence = 0
        self.scheduled_log: List[str] = []

    def submit(self, task: KernelTask, reference: float = 0.0) -> float:
        """Queue ``task`` ordered by ``d_phi`` proximity to ``reference``."""
        if not isinstance(task, KernelTask):
            raise PhiGPUError("submit requires a KernelTask")
        distance = phi_log_distance(task.position, reference)
        heapq.heappush(self._queue, _ScheduledItem(distance, self._sequence, task))
        self._sequence += 1
        return distance

    def schedule(self) -> List[KernelTask]:
        """Drain the queue nearest-first, applying depth policy: tasks at
        or below the median queued distance are promoted toward the near
        tier; the rest are demoted toward the far tier."""
        ordered: List[KernelTask] = []
        drained: List[_ScheduledItem] = []
        while self._queue:
            drained.append(heapq.heappop(self._queue))
        if not drained:
            return ordered
        median = drained[len(drained) // 2].distance
        for item in drained:
            task = item.task
            ordered.append(task)
            self.scheduled_log.append(task.name)
            if task.resident is None:
                continue
            try:
                if item.distance <= median:
                    self._settle_depth(task.resident, self.near_depth)
                else:
                    self._settle_depth(task.resident, self.far_depth)
            except Exception as exc:  # memory policy is advisory, never fatal
                logger.debug("depth settle for %r skipped: %s", task.resident, exc)
        return ordered

    def _settle_depth(self, name: str, depth: int) -> None:
        """Walk the resident toward the target depth via promote/demote."""
        resident = self.memory._residents.get(name)
        if resident is None:
            return
        while resident.state.depth < depth:
            self.memory.demote(name)
            resident = self.memory._residents[name]
        while resident.state.depth > depth:
            self.memory.promote(name)
            resident = self.memory._residents[name]


# -- PhiGPU --------------------------------------------------------------------


@dataclass(frozen=True)
class KernelLaunchConfig:
    """One kernel launch: work partitioned across the 32 cores."""

    name: str
    work_items: int
    kernel: Callable[[np.ndarray], np.ndarray]
    boundary: Optional[KernelBoundary] = None

    def __post_init__(self) -> None:
        if self.work_items < 1:
            raise PhiGPUError("work_items must be >= 1")
        if not callable(self.kernel):
            raise PhiGPUError("kernel must be callable")


@dataclass(frozen=True)
class KernelResult:
    """Measured record of one launch."""

    name: str
    work_items: int
    cores_used: int
    output_norm: float
    integrity_passed: bool


class PhiGPU:
    """The virtual phi-native GPU: 32 tensor cores over a fold-depth
    memory hierarchy behind the geodesic scheduler and integrity gate."""

    def __init__(
        self,
        cores: int = PHI_GPU_CORES,
        memory: Optional[PhiMemoryHierarchy] = None,
        gate: Optional[TopologicalIntegrityGate] = None,
    ) -> None:
        if cores < 1:
            raise PhiGPUError("PhiGPU requires at least one core")
        self.cores = int(cores)
        self.memory = memory if memory is not None else PhiMemoryHierarchy()
        self.gate = gate if gate is not None else TopologicalIntegrityGate()
        self.scheduler = GeodesicScheduler(self.memory)
        self.tensor_core = PhiTensorCore()
        self.launch_log: List[KernelResult] = []

    def store(self, name: str, array: np.ndarray, tier: MemoryTier = MemoryTier.HBM):
        return self.memory.store(name, array, tier)

    def launch_kernel(self, config: KernelLaunchConfig) -> np.ndarray:
        """Execute ``config.kernel`` on per-core slices and reduce.

        Each core receives a contiguous work slice (ceil-partitioned),
        runs the kernel on the unfolded slice, and the partial results are
        concatenated by ``_reduce_results``. The integrity gate verifies
        the assembled output against a host reference computation.
        """
        if not isinstance(config, KernelLaunchConfig):
            raise PhiGPUError("launch_kernel requires a KernelLaunchConfig")
        resident = (
            self.memory._residents.get(config.name)
            if config.name in self.memory._residents
            else None
        )
        if resident is None:
            raise PhiGPUError(f"launch_kernel requires a stored resident named {config.name!r}")
        flat = phi_unfold(resident.state).ravel()
        boundary = config.boundary or KernelBoundary(0, min(config.work_items, flat.size))
        work = flat[boundary.slice]
        if work.size < config.work_items:
            raise PhiGPUError(
                f"boundary exposes {work.size} elements for {config.work_items} work items"
            )
        slices = np.array_split(work, self.cores)
        partials = [np.asarray(config.kernel(s)) for s in slices if s.size]
        result = self._reduce_results(partials)
        reference = np.asarray(config.kernel(work)).ravel()
        seq = self.gate.next_sequence()
        self.gate.verify(
            op=config.name,
            sequence=seq,
            expected=reference,
            actual=result.ravel(),
            input_norm=float(np.linalg.norm(work)),
            output_norm=float(np.linalg.norm(result)),
        )
        verdict = self.gate.verdicts[-1]
        self.launch_log.append(
            KernelResult(
                name=config.name,
                work_items=config.work_items,
                cores_used=len(partials),
                output_norm=float(np.linalg.norm(result)),
                integrity_passed=verdict.passed,
            )
        )
        return result

    def _reduce_results(self, partials: Sequence[np.ndarray]) -> np.ndarray:
        """Concatenate per-core partial results (order-preserving)."""
        if not partials:
            return np.zeros(0, dtype=np.float64)
        return np.concatenate([p.ravel() for p in partials])

    def get_system_report(self) -> Dict[str, Any]:
        """Software-emulated device report — internal accounting only."""
        tiers = self.memory.tier_report()
        return {
            "truth_class": "internal",
            "cores": self.cores,
            "launches": len(self.launch_log),
            "integrity_pass_rate": self.gate.pass_rate,
            "tiers": tiers,
            "kernel_log": [r.name for r in self.launch_log],
        }


# -- HybridGPU -----------------------------------------------------------------


@dataclass(frozen=True)
class RouteDecisionRecord:
    """Where a workload was routed and why — internal observability."""

    name: str
    route: str
    reason: str
    elements: int


class HybridGPU:
    """Routes structured workloads to the phi-native path and irregular
    ones to the traditional NumPy path. A workload is *structured* when it
    is a numeric ndarray foldable by ``aethel.phi_fold``; anything else
    (ragged/object payloads, scalars too small to fold) stays traditional.
    """

    def __init__(self, phi_gpu: Optional[PhiGPU] = None) -> None:
        self.phi_gpu = phi_gpu if phi_gpu is not None else PhiGPU()
        self.routes: List[RouteDecisionRecord] = []

    def route_workload(self, name: str, payload: Any) -> str:
        """Return ``phi_native`` or ``traditional`` with a recorded reason."""
        route, reason = self._classify(payload)
        elements = (
            int(np.asarray(payload).size)
            if hasattr(payload, "__len__") or np.isscalar(payload)
            else 0
        )
        self.routes.append(
            RouteDecisionRecord(name=name, route=route, reason=reason, elements=elements)
        )
        return route

    @staticmethod
    def _classify(payload: Any) -> Tuple[str, str]:
        if isinstance(payload, np.ndarray) and payload.dtype.kind in "fiu":
            if payload.size >= 8:
                return "phi_native", "numeric ndarray of foldable size"
            return "traditional", "payload too small to fold"
        if isinstance(payload, (list, tuple)) and payload and all(np.isscalar(x) for x in payload):
            return "phi_native", "flat numeric sequence"
        return "traditional", "irregular or non-numeric payload"

    def execute(
        self, name: str, payload: Any, kernel: Callable[[np.ndarray], np.ndarray]
    ) -> np.ndarray:
        """Route then run: phi-native payloads are folded into the
        hierarchy, launched through ``PhiGPU``, and unfolded; traditional
        payloads run the kernel directly."""
        route = self.route_workload(name, payload)
        flat = np.asarray(payload, dtype=np.float64).ravel()
        if route == "phi_native":
            self.phi_gpu.store(name, flat, MemoryTier.HBM)
            result = self.phi_gpu.launch_kernel(
                KernelLaunchConfig(name=name, work_items=flat.size, kernel=kernel)
            )
            return result
        return np.asarray(kernel(flat)).ravel()

    def get_hybrid_report(self) -> Dict[str, Any]:
        counts = {"phi_native": 0, "traditional": 0}
        for record in self.routes:
            counts[record.route] += 1
        return {
            "truth_class": "internal",
            "routes": counts,
            "decisions": [r.name for r in self.routes],
            "phi_gpu": self.phi_gpu.get_system_report(),
        }


# -- EnergyModel ----------------------------------------------------------------


@dataclass(frozen=True)
class EnergyComparison:
    """Declared-coefficient comparison — model arithmetic, not measurement."""

    traditional_j: float
    phi_gpu_j: float
    savings_j: float
    reduction_pct: float
    movement_share_traditional: float
    compute_share_phi: float


class EnergyModel:
    """Compares energy using the declared shift: traditional devices spend
    ``movement_share`` of energy on data movement while the phi-native
    model spends ``compute_share`` on compute. The coefficients are model
    constants — INTERNAL, never a device measurement."""

    def __init__(
        self,
        movement_share: float = 0.80,
        compute_share: float = 0.95,
        movement_joule_per_element: float = 1.0,
        compute_joule_per_element: float = 1.0,
    ):
        if not 0 < movement_share < 1 or not 0 < compute_share < 1:
            raise PhiGPUError("energy shares must lie in (0, 1)")
        self.movement_share = float(movement_share)
        self.compute_share = float(compute_share)
        self.movement_joule_per_element = float(movement_joule_per_element)
        self.compute_joule_per_element = float(compute_joule_per_element)

    def traditional_energy(self, elements: float, working_set_ratio: float = 1.0) -> float:
        # Traditional path moves the full working set; folding does not help it.
        moved = elements
        compute = elements
        return self.movement_joule_per_element * moved * self.movement_share + (
            self.compute_joule_per_element * compute * (1.0 - self.movement_share)
        )

    def phi_gpu_energy(self, elements: float, working_set_ratio: float = 1.0) -> float:
        # Phi-native path moves only the folded working set (elements / ratio).
        moved = elements / max(working_set_ratio, 1e-30)
        compute = elements
        return self.movement_joule_per_element * moved * (1.0 - self.compute_share) + (
            self.compute_joule_per_element * compute * self.compute_share
        )

    def compare(self, elements: float, working_set_ratio: float = 1.0) -> EnergyComparison:
        """``compare()`` returns savings and reduction percent. The ratio
        argument is the measured fold ratio from ``PhiMemoryHierarchy`` —
        never an assumed value."""
        if elements <= 0:
            raise PhiGPUError("elements must be > 0")
        traditional = self.traditional_energy(elements, working_set_ratio)
        phi = self.phi_gpu_energy(elements, working_set_ratio)
        savings = traditional - phi
        return EnergyComparison(
            traditional_j=traditional,
            phi_gpu_j=phi,
            savings_j=savings,
            reduction_pct=(100.0 * savings / traditional) if traditional else 0.0,
            movement_share_traditional=self.movement_share,
            compute_share_phi=self.compute_share,
        )


__all__ = [
    "EnergyComparison",
    "EnergyModel",
    "GeodesicScheduler",
    "HybridGPU",
    "KernelLaunchConfig",
    "KernelResult",
    "KernelTask",
    "PHI_GPU_CORES",
    "PhiGPU",
    "PhiGPUError",
    "RouteDecisionRecord",
    "phi_log_distance",
]
