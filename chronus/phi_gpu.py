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
    depends_on: Tuple[str, ...] = ()


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
        self._blocked: List[_ScheduledItem] = []
        self._sequence = 0
        self.scheduled_log: List[str] = []
        self.completed_tasks: List[KernelTask] = []
        self._completed_names: set = set()
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

    def is_ready(self, task: KernelTask) -> bool:
        """A task is dispatchable only when every named dependency completed."""
        return all(name in self._completed_names for name in task.depends_on)

    def submit(
        self,
        task: KernelTask | KernelBoundary,
        reference: float = 0.0,
        *,
        operands: Any = None,
        operation: str = "fma",
        resident: Optional[str] = None,
        kernel: Optional[Callable[[np.ndarray], np.ndarray]] = None,
        depends_on: Tuple[str, ...] = (),
    ) -> float:
        if isinstance(task, KernelBoundary):
            task = KernelTask(
                name=f"{operation}:{self._sequence}",
                position=float(task.offset + task.length / 2.0),
                payload={
                    "boundary": task,
                    "operands": operands,
                    "operation": operation,
                    "kernel": kernel,
                },
                resident=resident,
                depends_on=tuple(depends_on),
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

    def _pop_ready(self) -> Optional[_ScheduledItem]:
        """Pop the nearest dispatchable item; hold blocked items aside.

        Blocked tasks stay pending — selection order is defined over the
        ready queue, so a dependency-locked task cannot shadow nearer ready
        work nor launch before its dependencies complete.
        """
        skipped: List[_ScheduledItem] = []
        found: Optional[_ScheduledItem] = None
        while self._queue and found is None:
            item = heapq.heappop(self._queue)
            if self.is_ready(item.task):
                found = item
            else:
                skipped.append(item)
        for item in skipped:
            self._blocked.append(item)
        return found

    def _dispatch(self, item: _ScheduledItem, median: float) -> KernelTask:
        task = item.task
        task.assigned_core = self.scheduling_decisions % self.num_cores
        task.geodesic_distance = item.distance
        self.scheduled_log.append(task.name)
        self.scheduling_decisions += 1
        self.total_geodesic_distance += item.distance
        self.current_position = np.array([task.position], dtype=np.float64)
        self._apply_depth_policy(item, median)
        return task

    def schedule(self) -> List[KernelTask]:
        """Drain pending ready work nearest-first; blocked work stays queued."""
        drained: List[_ScheduledItem] = []
        while True:
            item = self._pop_ready()
            if item is None:
                break
            drained.append(item)
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
        """Select the nearest *ready* task, or None when none can dispatch."""
        item = self._pop_ready()
        if item is None:
            return None
        return self._dispatch(item, item.distance)

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
        self._completed_names.add(task.name)
        # Unblock any dependents now that their readiness may hold.
        still_blocked: List[_ScheduledItem] = []
        for item in self._blocked:
            if self.is_ready(item.task):
                heapq.heappush(self._queue, item)
            else:
                still_blocked.append(item)
        self._blocked = still_blocked

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "num_cores": self.num_cores,
            "pending_tasks": len(self._queue),
            "blocked_tasks": len(self._blocked),
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
    #: Optional ``(resident_name, KernelBoundary)``: when declared, the
    #: *verified* result is spliced into that resident's folded state at the
    #: declared coordinates exactly once. A failed integrity verdict
    #: withholds the commit — unverified output never reaches custody.
    commit_to: Optional[Tuple[str, KernelBoundary]] = None

    def __post_init__(self) -> None:
        if self.work_items < 1:
            raise PhiGPUError("work_items must be >= 1")
        if not callable(self.kernel):
            raise PhiGPUError("kernel must be callable")
        if self.commit_to is not None:
            target, boundary = self.commit_to
            if not target or not isinstance(boundary, KernelBoundary):
                raise PhiGPUError(
                    "commit_to must be (resident_name, KernelBoundary)"
                )
            if boundary.length != self.work_items:
                raise PhiGPUError(
                    f"commit boundary spans {boundary.length} elements but the "
                    f"launch produces {self.work_items}"
                )

    @property
    def total_threads(self) -> int:
        return self.work_items

    @property
    def num_blocks(self) -> int:
        return max(1, math.ceil(self.work_items / PHI_GPU_CORES))


class CoordinateCommit:
    """Exactly-once output assembly by declared flat coordinates.

    Each kernel partial commits its output span at a declared offset;
    overlapping or out-of-span commits fail closed, and ``finish`` rejects
    an incomplete coverage map. Whole-state concatenation cannot express
    this contract — a partial writing the wrong span is silently ordered,
    not verified.
    """

    def __init__(self, total: int, dtype: np.dtype) -> None:
        if total < 1:
            raise PhiGPUError("coordinate-committed output requires >= 1 element")
        self._buffer = np.empty(int(total), dtype=np.dtype(dtype))
        self._written = np.zeros(int(total), dtype=bool)

    def commit(self, offset: int, values: np.ndarray) -> None:
        flat = np.asarray(values).ravel()
        start, stop = int(offset), int(offset) + flat.size
        if start < 0 or stop > self._buffer.size:
            raise PhiGPUError(
                f"commit [{start}, {stop}) lies outside output span {self._buffer.size}"
            )
        if self._written[start:stop].any():
            raise PhiGPUError(
                f"coordinates [{start}, {stop}) already committed — exactly-once violated"
            )
        self._buffer[start:stop] = flat
        self._written[start:stop] = True

    def finish(self) -> np.ndarray:
        if not self._written.all():
            raise PhiGPUError(
                "output span incomplete — uncommitted coordinates remain"
            )
        return self._buffer


@dataclass(frozen=True)
class KernelResult:
    name: str
    work_items: int
    cores_used: int
    output_norm: float
    integrity_passed: bool
    boundary: Tuple[int, int]
    #: ``(resident, offset, length)`` when the verified output was committed
    #: into resident folded state; ``None`` for a read-only launch.
    committed: Optional[Tuple[str, int, int]] = None


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

    def submit_task(
        self,
        task: KernelTask | KernelBoundary,
        reference: float = 0.0,
        *,
        kernel: Optional[Callable[[np.ndarray], np.ndarray]] = None,
        resident: Optional[str] = None,
        operands: Any = None,
        operation: str = "fma",
        depends_on: Tuple[str, ...] = (),
    ) -> float:
        """Queue work through the scheduler — the production submission path."""
        return self.scheduler.submit(
            task,
            reference,
            operands=operands,
            operation=operation,
            resident=resident,
            kernel=kernel,
            depends_on=depends_on,
        )

    def _task_launch_config(self, task: KernelTask) -> KernelLaunchConfig:
        """Build the launch config the *selected* task dictates.

        The boundary comes from the task payload — scheduler selection is
        what controls which region executes, never a local default.
        """
        payload = task.payload if isinstance(task.payload, dict) else {}
        boundary = payload.get("boundary")
        if not isinstance(boundary, KernelBoundary):
            raise PhiGPUError(
                f"scheduled task {task.name!r} carries no KernelBoundary payload"
            )
        kernel = payload.get("kernel")
        if not callable(kernel):
            raise PhiGPUError(
                f"scheduled task {task.name!r} carries no kernel payload"
            )
        resident = task.resident or payload.get("resident")
        if not resident:
            raise PhiGPUError(
                f"scheduled task {task.name!r} names no resident operand"
            )
        commit_to = payload.get("commit_to")
        if commit_to is not None and not (
            isinstance(commit_to, tuple)
            and len(commit_to) == 2
            and isinstance(commit_to[1], KernelBoundary)
        ):
            raise PhiGPUError(
                "scheduled commit_to must be (resident_name, KernelBoundary)"
            )
        return KernelLaunchConfig(
            name=resident,
            work_items=int(payload.get("work_items") or boundary.length),
            kernel=kernel,
            boundary=boundary,
            commit_to=commit_to,
        )

    def run_next(self) -> Optional[np.ndarray]:
        """Scheduler-driven execution: the selected task controls the launch."""
        task = self.scheduler.schedule_next()
        if task is None:
            return None
        result = self.launch_kernel(self._task_launch_config(task))
        self.scheduler.mark_completed(task, result)
        return result

    def run_ready(self, limit: Optional[int] = None) -> List[np.ndarray]:
        """Drain the ready queue under scheduler control.

        Execution order is exactly the scheduler's selection order;
        dependency-locked tasks run only after their dependencies complete.
        """
        results: List[np.ndarray] = []
        remaining = None if limit is None else int(limit)
        while remaining is None or remaining > 0:
            result = self.run_next()
            if result is None:
                break
            results.append(result)
            if remaining is not None:
                remaining -= 1
        return results

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
        slices = [s for s in np.array_split(work, self.cores) if s.size]
        # Each partial commits its output at the declared coordinates of the
        # slice it was computed from — coordinate-preserving kernels only.
        partials: List[Tuple[int, np.ndarray]] = []
        offset = 0
        for piece in slices:
            partial = np.asarray(config.kernel(piece))
            if partial.size != piece.size:
                raise PhiGPUError(
                    f"kernel output span {partial.size} does not match declared "
                    f"coordinates [{offset}, {offset + piece.size}) — non "
                    f"coordinate-preserving kernels must declare a reduce boundary"
                )
            partials.append((offset, partial))
            offset += piece.size
        result = self._reduce_results(partials, total=work.size)
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
        committed: Optional[Tuple[str, int, int]] = None
        if config.commit_to is not None:
            target_name, commit_boundary = config.commit_to
            if not verdict.passed:
                raise PhiGPUError(
                    f"integrity verdict failed — output withheld from resident "
                    f"{target_name!r}"
                )
            self.memory.commit_region(
                target_name, commit_boundary, result.ravel()
            )
            committed = (target_name, commit_boundary.offset, commit_boundary.length)
        self.launch_log.append(
            KernelResult(
                name=config.name,
                work_items=config.work_items,
                cores_used=len(partials),
                output_norm=float(np.linalg.norm(result)),
                integrity_passed=verdict.passed,
                boundary=(boundary.offset, boundary.length),
                committed=committed,
            )
        )
        return result

    def _reduce_results(
        self, partials: Sequence[Tuple[int, np.ndarray]], *, total: int
    ) -> np.ndarray:
        """Assemble partials by declared coordinates — exactly-once coverage.

        Output dtype follows the first partial; uncommitted or doubly
        committed coordinates fail closed inside :class:`CoordinateCommit`.
        """
        if not partials:
            return np.zeros(0, dtype=np.float64)
        commit = CoordinateCommit(total, np.asarray(partials[0][1]).dtype)
        for offset, partial in partials:
            commit.commit(offset, partial)
        return commit.finish()

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
