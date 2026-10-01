"""Chronus phi GPU — consolidated Geodesic Tensor Engine control plane.

Chronus owns scheduling and GPU orchestration. Aethel owns folded-state custody;
Kellogg owns folded tensor arithmetic; Tensor owns physical backend dispatch and
measured TFLOPS. This module retains every July Geodesic control-plane surface
while preserving those modern ownership boundaries.

The virtual ``PhiGPU`` uses Aethel's true addressed ``unfold_partial`` path for
kernel reads. Physical OpenCL tensor execution remains in
``tensor.backends.chronus_backend`` and ``chronus.tensor_compute``; no device
measurement is fabricated here.
"""
from __future__ import annotations

import heapq
import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from aethel.phi_fold import KernelBoundary, unfold_partial
from aethel.phi_memory import MemoryTier, PhiMemoryHierarchy, TopologicalIntegrityGate
from kellogg.phi_tensor_core import PhiTensorCore

logger = logging.getLogger("chronus.phi_gpu")
PHI = (1.0 + math.sqrt(5.0)) / 2.0
PHI_GPU_CORES = 32


class PhiGPUError(RuntimeError):
    """A phi-GPU dispatch, launch, or routing contract was violated."""


def phi_log_distance(a: float, b: float) -> float:
    m = max(abs(float(a)), abs(float(b)))
    if m <= 0:
        return 0.0
    return math.log(m) / math.log(PHI)


@dataclass(order=True)
class _ScheduledItem:
    distance: float
    sequence: int
    task: "KernelTask" = field(compare=False)


@dataclass
class KernelTask:
    name: str
    position: float
    payload: Any = None
    resident: Optional[str] = None
    completed: bool = False
    result: Any = None
    assigned_core: int = -1
    geodesic_distance: float = 0.0


GeodesicTask = KernelTask


class GeodesicScheduler:
    """Nearest-first φ-manifold scheduler with modern and July interfaces."""

    def __init__(
        self,
        memory: Optional[PhiMemoryHierarchy] = None,
        near_depth: int = 1,
        far_depth: int = 3,
        num_cores: int = PHI_GPU_CORES,
    ) -> None:
        if num_cores < 1:
            raise PhiGPUError("num_cores must be positive")
        self.memory = memory if memory is not None else PhiMemoryHierarchy()
        self.near_depth = int(near_depth)
        self.far_depth = int(far_depth)
        self.num_cores = int(num_cores)
        self._queue: List[_ScheduledItem] = []
        self._sequence = 0
        self.scheduled_log: List[str] = []
        self.completed_tasks: List[KernelTask] = []
        self.scheduling_decisions = 0
        self.total_geodesic_distance = 0.0
        self.current_position = np.array([1.0], dtype=np.float64)

    def compute_geodesic_distance(
        self, boundary: KernelBoundary, current_pos: Optional[np.ndarray] = None
    ) -> float:
        if not isinstance(boundary, KernelBoundary):
            raise PhiGPUError("compute_geodesic_distance requires KernelBoundary")
        center = float(boundary.offset + boundary.length / 2.0)
        pos = self.current_position if current_pos is None else np.asarray(current_pos, dtype=float)
        reference = float(pos.ravel()[0]) if pos.size else 1.0
        if center <= 0 or reference <= 0:
            return float("inf")
        return abs(math.log(center / reference) / math.log(PHI))

    def submit(
        self,
        task: KernelTask | KernelBoundary,
        reference: float = 0.0,
        *,
        operands: Any = None,
        operation: str = "fma",
        resident: Optional[str] = None,
    ) -> float:
        if isinstance(task, KernelBoundary):
            task = KernelTask(
                name=f"{operation}:{self._sequence}",
                position=float(task.offset + task.length / 2.0),
                payload={"boundary": task, "operands": operands, "operation": operation},
                resident=resident,
            )
        if not isinstance(task, KernelTask):
            raise PhiGPUError("submit requires a KernelTask or KernelBoundary")
        distance = phi_log_distance(task.position, reference)
        task.geodesic_distance = distance
        heapq.heappush(self._queue, _ScheduledItem(distance, self._sequence, task))
        self._sequence += 1
        return distance

    def _apply_depth_policy(self, item: _ScheduledItem, median: float) -> None:
        task = item.task
        if task.resident is None:
            return
        try:
            self._settle_depth(
                task.resident, self.near_depth if item.distance <= median else self.far_depth
            )
        except Exception as exc:
            logger.debug("depth settle for %r skipped: %s", task.resident, exc)

    def schedule(self) -> List[KernelTask]:
        """Drain pending work nearest-first; preserves the modern live contract."""
        drained: List[_ScheduledItem] = []
        while self._queue:
            drained.append(heapq.heappop(self._queue))
        if not drained:
            return []
        median = drained[len(drained) // 2].distance
        ordered = []
        for index, item in enumerate(drained):
            task = item.task
            task.assigned_core = index % self.num_cores
            task.geodesic_distance = item.distance
            ordered.append(task)
            self.scheduled_log.append(task.name)
            self.scheduling_decisions += 1
            self.total_geodesic_distance += item.distance
            self.current_position = np.array([task.position], dtype=np.float64)
            self._apply_depth_policy(item, median)
        return ordered

    def schedule_next(self) -> Optional[KernelTask]:
        if not self._queue:
            return None
        item = heapq.heappop(self._queue)
        task = item.task
        task.assigned_core = self.scheduling_decisions % self.num_cores
        task.geodesic_distance = item.distance
        self.scheduled_log.append(task.name)
        self.scheduling_decisions += 1
        self.total_geodesic_distance += item.distance
        self.current_position = np.array([task.position], dtype=np.float64)
        self._apply_depth_policy(item, item.distance)
        return task

    def schedule_batch(self, batch_size: Optional[int] = None) -> List[KernelTask]:
        limit = self.num_cores if batch_size is None else int(batch_size)
        if limit < 1:
            raise PhiGPUError("batch_size must be positive")
        batch = []
        for _ in range(min(limit, len(self._queue))):
            task = self.schedule_next()
            if task is not None:
                batch.append(task)
        return batch

    def mark_completed(self, task: KernelTask, result: Any = None) -> None:
        if not isinstance(task, KernelTask):
            raise PhiGPUError("mark_completed requires KernelTask")
        task.completed = True
        task.result = result
        self.completed_tasks.append(task)

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "num_cores": self.num_cores,
            "pending_tasks": len(self._queue),
            "completed_tasks": len(self.completed_tasks),
            "scheduling_decisions": self.scheduling_decisions,
            "total_geodesic_distance": self.total_geodesic_distance,
            "avg_geodesic_distance": (
                self.total_geodesic_distance / self.scheduling_decisions
                if self.scheduling_decisions
                else 0.0
            ),
            "current_position": float(self.current_position[0]),
        }

    def _settle_depth(self, name: str, depth: int) -> None:
        resident = self.memory._residents.get(name)
        if resident is None:
            return
        while resident.state.depth < depth:
            self.memory.demote(name)
            resident = self.memory._residents[name]
        while resident.state.depth > depth:
            self.memory.promote(name)
            resident = self.memory._residents[name]


@dataclass(frozen=True)
class KernelLaunchConfig:
    name: str
    work_items: int
    kernel: Callable[[np.ndarray], np.ndarray]
    boundary: Optional[KernelBoundary] = None

    def __post_init__(self) -> None:
        if self.work_items < 1:
            raise PhiGPUError("work_items must be >= 1")
        if not callable(self.kernel):
            raise PhiGPUError("kernel must be callable")

    @property
    def total_threads(self) -> int:
        return self.work_items

    @property
    def num_blocks(self) -> int:
        return max(1, math.ceil(self.work_items / PHI_GPU_CORES))


@dataclass(frozen=True)
class KernelResult:
    name: str
    work_items: int
    cores_used: int
    output_norm: float
    integrity_passed: bool
    boundary: Tuple[int, int]


class PhiGPU:
    """Complete July virtual GPU facade over modern Aethel/Kellogg owners."""

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
        self.scheduler = GeodesicScheduler(self.memory, num_cores=self.cores)
        self.tensor_core = PhiTensorCore()
        self.launch_log: List[KernelResult] = []

    @property
    def num_cores(self) -> int:
        return self.cores

    def store(self, name: str, array: np.ndarray, tier: MemoryTier = MemoryTier.HBM):
        return self.memory.store(name, array, tier)

    def launch_kernel(self, config: KernelLaunchConfig) -> np.ndarray:
        """Execute a kernel using only the addressed folded-state slice."""
        if not isinstance(config, KernelLaunchConfig):
            raise PhiGPUError("launch_kernel requires a KernelLaunchConfig")
        resident = self.memory._residents.get(config.name)
        if resident is None:
            raise PhiGPUError(f"launch_kernel requires a stored resident named {config.name!r}")
        boundary = config.boundary or KernelBoundary(
            0, min(config.work_items, resident.state.original_size)
        )
        if boundary.stop > resident.state.original_size:
            raise PhiGPUError(
                f"boundary [{boundary.offset}, {boundary.stop}) exceeds resident size "
                f"{resident.state.original_size}"
            )
        work = unfold_partial(resident.state, boundary)
        if work.size < config.work_items:
            raise PhiGPUError(
                f"boundary exposes {work.size} elements for {config.work_items} work items"
            )
        work = work[: config.work_items]
        slices = np.array_split(work, self.cores)
        partials = [np.asarray(config.kernel(s)) for s in slices if s.size]
        result = self._reduce_results(partials)
        reference = np.asarray(config.kernel(work)).ravel()
        seq = self.gate.next_sequence()
        verdict = self.gate.verify(
            op=config.name,
            sequence=seq,
            expected=reference,
            actual=result.ravel(),
            input_norm=float(np.linalg.norm(work)),
            output_norm=float(np.linalg.norm(result)),
        )
        self.launch_log.append(
            KernelResult(
                name=config.name,
                work_items=config.work_items,
                cores_used=len(partials),
                output_norm=float(np.linalg.norm(result)),
                integrity_passed=verdict.passed,
                boundary=(boundary.offset, boundary.length),
            )
        )
        return result

    def _reduce_results(self, partials: Sequence[np.ndarray]) -> np.ndarray:
        if not partials:
            return np.zeros(0, dtype=np.float64)
        return np.concatenate([np.asarray(p).ravel() for p in partials])

    def get_system_report(self) -> Dict[str, Any]:
        return {
            "truth_class": "internal_control_plane",
            "cores": self.cores,
            "launches": len(self.launch_log),
            "integrity_pass_rate": self.gate.pass_rate,
            "integrity": self.gate.get_metrics(),
            "scheduler": self.scheduler.get_metrics(),
            "memory": self.memory.get_memory_report(),
            "tensor_core": self.tensor_core.get_aggregate_metrics(),
            "kernel_log": [r.name for r in self.launch_log],
            "partial_unfold": "aethel_true_selective",
            "physical_tensor_backend": "tensor.backends.chronus_backend",
        }


class ComputeUnitType(Enum):
    PHI_NATIVE = "phi_native"
    TRADITIONAL = "traditional"


@dataclass(frozen=True)
class HybridComputeUnit:
    unit_id: int
    unit_type: ComputeUnitType
    active: bool = True


@dataclass(frozen=True)
class RouteDecisionRecord:
    name: str
    route: str
    reason: str
    elements: int


class HybridGPU:
    """Route structured payloads to phi-native units and irregular payloads traditional."""

    def __init__(self, phi_gpu: Optional[PhiGPU] = None, *, traditional_units: int = 1) -> None:
        if traditional_units < 1:
            raise PhiGPUError("traditional_units must be positive")
        self.phi_gpu = phi_gpu if phi_gpu is not None else PhiGPU()
        self.routes: List[RouteDecisionRecord] = []
        self.compute_units: List[HybridComputeUnit] = [
            HybridComputeUnit(i, ComputeUnitType.PHI_NATIVE) for i in range(self.phi_gpu.cores)
        ] + [
            HybridComputeUnit(self.phi_gpu.cores + i, ComputeUnitType.TRADITIONAL)
            for i in range(traditional_units)
        ]

    def route_workload(self, name: str, payload: Any) -> str:
        route, reason = self._classify(payload)
        elements = (
            int(np.asarray(payload).size)
            if hasattr(payload, "__len__") or np.isscalar(payload)
            else 0
        )
        self.routes.append(RouteDecisionRecord(name, route, reason, elements))
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
        route = self.route_workload(name, payload)
        flat = np.asarray(payload, dtype=np.float64).ravel()
        if route == "phi_native":
            self.phi_gpu.store(name, flat, MemoryTier.HBM)
            return self.phi_gpu.launch_kernel(
                KernelLaunchConfig(name=name, work_items=flat.size, kernel=kernel)
            )
        return np.asarray(kernel(flat)).ravel()

    def get_hybrid_report(self) -> Dict[str, Any]:
        counts = {"phi_native": 0, "traditional": 0}
        for record in self.routes:
            counts[record.route] += 1
        units = {kind.value: 0 for kind in ComputeUnitType}
        for unit in self.compute_units:
            if unit.active:
                units[unit.unit_type.value] += 1
        return {
            "truth_class": "internal_control_plane",
            "routes": counts,
            "compute_units": units,
            "decisions": [r.name for r in self.routes],
            "phi_gpu": self.phi_gpu.get_system_report(),
        }


@dataclass(frozen=True)
class EnergyComparison:
    traditional_j: float
    phi_gpu_j: float
    savings_j: float
    reduction_pct: float
    movement_share_traditional: float
    compute_share_phi: float


class EnergyModel:
    """Declared energy-coefficient model; never physical telemetry."""

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
        del working_set_ratio
        return self.movement_joule_per_element * elements * self.movement_share + (
            self.compute_joule_per_element * elements * (1.0 - self.movement_share)
        )

    def phi_gpu_energy(self, elements: float, working_set_ratio: float = 1.0) -> float:
        moved = elements / max(working_set_ratio, 1e-30)
        return self.movement_joule_per_element * moved * (1.0 - self.compute_share) + (
            self.compute_joule_per_element * elements * self.compute_share
        )

    def compare(self, elements: float, working_set_ratio: float = 1.0) -> EnergyComparison:
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
    "ComputeUnitType", "EnergyComparison", "EnergyModel", "GeodesicScheduler", "GeodesicTask",
    "HybridComputeUnit", "HybridGPU", "KernelLaunchConfig", "KernelResult", "KernelTask",
    "PHI_GPU_CORES", "PhiGPU", "PhiGPUError", "RouteDecisionRecord", "phi_log_distance",
]
