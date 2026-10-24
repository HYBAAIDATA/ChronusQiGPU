r"""Exact GPU/iGPU Fleet Capacity Planning, Partition Certification, and Distributed Workload Execution.

This module implements substrate-agnostic, deterministic capacity planning and
workload execution across a fleet of isolated ONE-iGPU workers (`NativeIGPUWorker`):

1. **Exact GPU/iGPU Worker & Fleet Capacity Specification (`GPUWorkerSpec`, `WorkloadSpec`)**:
   - Models homogeneous or heterogeneous worker pools where each worker adheres
     strictly to the Chronus `device_count == 1` (`ONE iGPU per worker`) contract.
   - Integrates with `chronus.igpu.scaled_plan.ScaledPlan` for Lucas $L_n$ scaling
     rungs ($L_{10}=123, L_{12}=322, L_{15}=1364, L_{18}=5778, \dots$) and
     `chronus.gpu_capabilities.GPUDeviceTopology` / `GPUMemoryHierarchyProfile`.

2. **Exact Rational Capacity & Partition Planning (`FleetCapacityPlan`, `plan_gpu_fleet_capacity`)**:
   - Uses exact integer and rational (`Fraction`) arithmetic — zero floating-point
     rounding in capacity certificates.
   - Allocates disjoint contiguous item partitions `[start, end)` across authorized
     tenant workers proportional to compute lanes (or uniform), proving
     `zero_gaps == True` and `zero_overlap == True`.
   - Evaluates memory budget admission (including optional $2^n$ quantum statevector
     bytes) and throughput floor admission (`required_floor_ops_per_second`).

3. **Cryptographic Fleet Capacity Certificates (`FleetCapacityCertificate`)**:
   - Canonical SHA-256 and Merkle-rooted capacity certificates with explicit honesty
     boundaries (`truth_class="exact_mathematical_capacity_and_partition_plan"`).

4. **End-to-End Distributed Fleet Workload Execution (`execute_fleet_workload`)**:
   - Orchestrates `FleetScheduler`, `NativeIGPUWorker`, `FleetCustody`, and
     `BufferIntegrityGate` across all planned partitions.
   - Supports simulated or live worker termination mid-flight with automatic
     fencing-token rotation, stale-commit rejection, and safe partition reassignment.
   - Verifies bit-exact agreement between distributed fleet execution and
     single-instance reference execution.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from fractions import Fraction
from typing import Any, Callable, Iterable, Optional, Sequence

from chronus.fleet.custody import FleetCustody
from chronus.fleet.native_worker import ExecutionResult, NativeIGPUWorker
from chronus.fleet.scheduler import FleetScheduler
from chronus.fleet.worker_identity import WorkerIdentity, WorkLease
from chronus.gpu_capabilities import (
    BufferAttestation,
    BufferIntegrityGate,
    GPUDeviceTopology,
    GPUMemoryHierarchyProfile,
    memory_hierarchy_from_topology,
)
from chronus.igpu.host import HostGPUPlan, execute_reference
from chronus.igpu.scaled_plan import LADDER, ScaledPlan
from turing_universal_quantum_computer.canonical_serialization import (
    canonical_sha256,
)

FLEET_CAPACITY_SCHEMA = "chronus.gpu_fleet_capacity/v1"
TRUTH_CLASS_CAPACITY_PLAN = "exact_mathematical_capacity_and_partition_plan"


def _fraction_dict(value: Fraction) -> dict[str, dict[str, int]]:
    val = Fraction(value)
    return {
        "$rational": {
            "numerator": int(val.numerator),
            "denominator": int(val.denominator),
        }
    }


def _fraction_from_dict(payload: dict[str, Any]) -> Fraction:
    rat = payload["$rational"]
    return Fraction(int(rat["numerator"]), int(rat["denominator"]))


def _merkle_root(leaves: Iterable[Any]) -> str:
    level = [bytes.fromhex(canonical_sha256(leaf)) for leaf in leaves]
    if not level:
        return hashlib.sha256(b"").hexdigest()
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        level = [
            hashlib.sha256(level[i] + level[i + 1]).digest()
            for i in range(0, len(level), 2)
        ]
    return level[0].hex()


@dataclass(frozen=True, kw_only=True)
class GPUWorkerSpec:
    """Formal capacity specification for a single isolated ONE-iGPU worker node."""

    worker_id: str
    tenant: str = "default"
    lanes: int = 8
    compute_units: int = 16
    clock_mhz: int = 1500
    global_memory_bytes: int = 8 * 1024**3
    local_memory_bytes: int = 64 * 1024
    cpu_cores: int = 2
    memory_mb: int = 1024
    mode: str = "host_gpu_overlay"
    backend: str = "cpu_reference"
    initiation_interval_cycles: Fraction = Fraction(1)
    generation: int = 1

    def __post_init__(self) -> None:
        if not self.worker_id.strip():
            raise ValueError("worker_id must be non-empty")
        if self.lanes < 1 or self.compute_units < 1 or self.clock_mhz < 1:
            raise ValueError("lanes, compute_units, and clock_mhz must be >= 1")
        if self.global_memory_bytes < 1 or self.local_memory_bytes < 1:
            raise ValueError("memory capacities must be positive")
        if self.cpu_cores < 1 or self.memory_mb < 1:
            raise ValueError("cpu_cores and memory_mb must be >= 1")
        interval = Fraction(self.initiation_interval_cycles)
        if interval <= 0:
            raise ValueError("initiation_interval_cycles must be > 0")
        object.__setattr__(self, "initiation_interval_cycles", interval)

    @property
    def clock_hz(self) -> int:
        return int(self.clock_mhz) * 1_000_000

    @property
    def steady_state_ops_per_second(self) -> Fraction:
        """Exact formal steady-state operation capacity: compute_units * lanes * clock_hz / I."""
        return (
            Fraction(int(self.compute_units) * int(self.lanes) * self.clock_hz)
            / self.initiation_interval_cycles
        )

    def to_topology(self) -> GPUDeviceTopology:
        """Build an honest GPUDeviceTopology declaration for this worker specification."""
        return GPUDeviceTopology(
            name=f"chronus_worker_{self.worker_id}",
            vendor="Chronus-Virtual-iGPU",
            backend=self.backend,
            compute_units=self.compute_units,
            clock_mhz=float(self.clock_mhz),
            global_memory_bytes=self.global_memory_bytes,
            local_memory_bytes=self.local_memory_bytes,
            max_work_group_size=self.lanes * 32,
            host_unified_memory=(self.mode in {"integrated_iGPU", "host_gpu_overlay"}),
            truth_class="declared_worker_capacity_spec",
            measured_by_chronus=False,
            notes=(
                "device_count=1 (ONE iGPU per worker contract)",
                f"mode={self.mode}",
                f"tenant={self.tenant}",
            ),
        )

    def memory_hierarchy(self) -> GPUMemoryHierarchyProfile:
        return memory_hierarchy_from_topology(self.to_topology())

    def as_dict(self) -> dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "tenant": self.tenant,
            "lanes": int(self.lanes),
            "compute_units": int(self.compute_units),
            "clock_mhz": int(self.clock_mhz),
            "global_memory_bytes": int(self.global_memory_bytes),
            "local_memory_bytes": int(self.local_memory_bytes),
            "cpu_cores": int(self.cpu_cores),
            "memory_mb": int(self.memory_mb),
            "mode": self.mode,
            "backend": self.backend,
            "initiation_interval_cycles": _fraction_dict(self.initiation_interval_cycles),
            "generation": int(self.generation),
            "steady_state_ops_per_second": _fraction_dict(self.steady_state_ops_per_second),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> GPUWorkerSpec:
        return cls(
            worker_id=str(payload["worker_id"]),
            tenant=str(payload["tenant"]),
            lanes=int(payload["lanes"]),
            compute_units=int(payload["compute_units"]),
            clock_mhz=int(payload["clock_mhz"]),
            global_memory_bytes=int(payload["global_memory_bytes"]),
            local_memory_bytes=int(payload["local_memory_bytes"]),
            cpu_cores=int(payload["cpu_cores"]),
            memory_mb=int(payload["memory_mb"]),
            mode=str(payload["mode"]),
            backend=str(payload["backend"]),
            initiation_interval_cycles=_fraction_from_dict(payload["initiation_interval_cycles"]),
            generation=int(payload.get("generation", 1)),
        )


@dataclass(frozen=True, kw_only=True)
class WorkloadSpec:
    """Formal workload specification for GPU/iGPU fleet capacity planning and execution."""

    work_id: str
    tenant: str = "default"
    operation: str = "kernel_eval"
    total_items: int
    bytes_per_item: int = 64
    cycles_per_item: int = 1
    scale_index: Optional[int] = None
    state_qubits: Optional[int] = None
    required_floor_ops_per_second: Optional[int] = None

    def __post_init__(self) -> None:
        if not self.work_id.strip():
            raise ValueError("work_id must be non-empty")
        if self.total_items < 0:
            raise ValueError("total_items must be >= 0")
        if self.bytes_per_item < 1 or self.cycles_per_item < 1:
            raise ValueError("bytes_per_item and cycles_per_item must be >= 1")
        if self.scale_index is not None and self.scale_index not in LADDER:
            raise ValueError(f"scale_index {self.scale_index} is not in Lucas LADDER {LADDER}")
        if self.state_qubits is not None and self.state_qubits < 0:
            raise ValueError("state_qubits must be >= 0")
        if self.required_floor_ops_per_second is not None and self.required_floor_ops_per_second < 1:
            raise ValueError("required_floor_ops_per_second must be >= 1")

    @property
    def statevector_bytes_per_item(self) -> int:
        """Exact complex128 statevector memory requirement per item when state_qubits is set."""
        if self.state_qubits is None:
            return 0
        return 16 * (1 << int(self.state_qubits))

    @property
    def effective_bytes_per_item(self) -> int:
        return int(self.bytes_per_item) + self.statevector_bytes_per_item

    def as_dict(self) -> dict[str, Any]:
        return {
            "work_id": self.work_id,
            "tenant": self.tenant,
            "operation": self.operation,
            "total_items": int(self.total_items),
            "bytes_per_item": int(self.bytes_per_item),
            "cycles_per_item": int(self.cycles_per_item),
            "scale_index": self.scale_index,
            "state_qubits": self.state_qubits,
            "required_floor_ops_per_second": self.required_floor_ops_per_second,
            "effective_bytes_per_item": self.effective_bytes_per_item,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> WorkloadSpec:
        return cls(
            work_id=str(payload["work_id"]),
            tenant=str(payload["tenant"]),
            operation=str(payload["operation"]),
            total_items=int(payload["total_items"]),
            bytes_per_item=int(payload["bytes_per_item"]),
            cycles_per_item=int(payload["cycles_per_item"]),
            scale_index=payload.get("scale_index"),
            state_qubits=payload.get("state_qubits"),
            required_floor_ops_per_second=payload.get("required_floor_ops_per_second"),
        )


@dataclass(frozen=True, kw_only=True)
class WorkerPartitionAllocation:
    """Exact partition and capacity allocation for one worker in the fleet."""

    worker_id: str
    tenant: str
    partition: tuple[int, int]
    item_count: int
    lanes: int
    estimated_bytes: int
    global_memory_bytes: int
    memory_utilization: Fraction
    memory_fits: bool
    steady_state_ops_per_second: Fraction
    estimated_duration_seconds: Fraction

    def as_dict(self) -> dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "tenant": self.tenant,
            "partition": [int(self.partition[0]), int(self.partition[1])],
            "item_count": int(self.item_count),
            "lanes": int(self.lanes),
            "estimated_bytes": int(self.estimated_bytes),
            "global_memory_bytes": int(self.global_memory_bytes),
            "memory_utilization": _fraction_dict(self.memory_utilization),
            "memory_fits": bool(self.memory_fits),
            "steady_state_ops_per_second": _fraction_dict(self.steady_state_ops_per_second),
            "estimated_duration_seconds": _fraction_dict(self.estimated_duration_seconds),
        }


@dataclass(frozen=True, kw_only=True)
class FleetCapacityPlan:
    """Complete deterministic capacity and partition plan for a workload across a GPU fleet."""

    work_id: str
    tenant: str
    workload: WorkloadSpec
    workers: tuple[GPUWorkerSpec, ...]
    proportional_by_lanes: bool
    total_items: int
    lucas_scale_index: Optional[int]
    lucas_factor: int
    effective_scaled_items: int
    total_workers: int
    total_lanes: int
    total_compute_units: int
    total_global_memory_bytes: int
    total_required_memory_bytes: int
    memory_admitted: bool
    floor_admitted: bool
    admitted: bool
    rejection_reasons: tuple[str, ...]
    aggregate_steady_state_ops_per_second: Fraction
    estimated_wall_seconds: Fraction
    allocations: tuple[WorkerPartitionAllocation, ...]
    zero_gaps: bool
    zero_overlap: bool
    one_igpu_per_worker: bool
    truth_class: str = TRUTH_CLASS_CAPACITY_PLAN

    def as_dict(self) -> dict[str, Any]:
        return {
            "work_id": self.work_id,
            "tenant": self.tenant,
            "workload": self.workload.as_dict(),
            "workers": [w.as_dict() for w in self.workers],
            "proportional_by_lanes": bool(self.proportional_by_lanes),
            "total_items": int(self.total_items),
            "lucas_scale_index": self.lucas_scale_index,
            "lucas_factor": int(self.lucas_factor),
            "effective_scaled_items": int(self.effective_scaled_items),
            "total_workers": int(self.total_workers),
            "total_lanes": int(self.total_lanes),
            "total_compute_units": int(self.total_compute_units),
            "total_global_memory_bytes": int(self.total_global_memory_bytes),
            "total_required_memory_bytes": int(self.total_required_memory_bytes),
            "memory_admitted": bool(self.memory_admitted),
            "floor_admitted": bool(self.floor_admitted),
            "admitted": bool(self.admitted),
            "rejection_reasons": list(self.rejection_reasons),
            "aggregate_steady_state_ops_per_second": _fraction_dict(
                self.aggregate_steady_state_ops_per_second
            ),
            "estimated_wall_seconds": _fraction_dict(self.estimated_wall_seconds),
            "allocations": [a.as_dict() for a in self.allocations],
            "zero_gaps": bool(self.zero_gaps),
            "zero_overlap": bool(self.zero_overlap),
            "one_igpu_per_worker": bool(self.one_igpu_per_worker),
            "truth_class": self.truth_class,
        }


@dataclass(frozen=True, kw_only=True)
class FleetCapacityCertificate:
    """Merkle-attested deterministic capacity and partition certificate."""

    schema: str
    plan: dict[str, Any]
    admitted: bool
    theorem: str
    truth_class: str
    attestation_root: str
    certificate_digest: str

    def unsigned_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row.pop("certificate_digest")
        return row

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def plan_gpu_fleet_capacity(
    workers: Sequence[GPUWorkerSpec],
    workload: WorkloadSpec,
    *,
    proportional_by_lanes: bool = True,
) -> FleetCapacityPlan:
    """Compute an exact GPU fleet capacity plan and disjoint partition schedule."""
    authorized = tuple(w for w in workers if w.tenant == workload.tenant)
    seen_ids = set()
    for w in authorized:
        if w.worker_id in seen_ids:
            raise ValueError(f"Duplicate worker_id in fleet: {w.worker_id}")
        seen_ids.add(w.worker_id)

    rejection_reasons: list[str] = []
    if not authorized:
        rejection_reasons.append(f"no_authorized_workers_for_tenant:{workload.tenant}")

    total_workers = len(authorized)
    total_lanes = sum(w.lanes for w in authorized)
    total_cus = sum(w.compute_units for w in authorized)
    total_mem = sum(w.global_memory_bytes for w in authorized)
    aggregate_ops = sum(
        (w.steady_state_ops_per_second for w in authorized),
        Fraction(0),
    )

    if workload.scale_index is not None:
        scaled = ScaledPlan(
            base_items=workload.total_items,
            scale_index=workload.scale_index,
            lanes=max(1, total_lanes),
        )
        lucas_factor = int(scaled.factor)
        effective_scaled_items = int(scaled.effective_items)
    else:
        lucas_factor = 1
        effective_scaled_items = int(workload.total_items)

    bytes_per_item = workload.effective_bytes_per_item
    total_required_mem = int(workload.total_items) * bytes_per_item

    allocations: list[WorkerPartitionAllocation] = []
    if authorized:
        weights = [w.lanes if proportional_by_lanes else 1 for w in authorized]
        weight_sum = sum(weights)
        cursor = 0
        for idx, (w, weight) in enumerate(zip(authorized, weights)):
            if idx == len(authorized) - 1:
                count = workload.total_items - cursor
            else:
                count = (workload.total_items * weight) // weight_sum
            start = cursor
            end = start + count
            cursor = end

            est_bytes = count * bytes_per_item
            mem_util = Fraction(est_bytes, w.global_memory_bytes)
            mem_fits = est_bytes <= w.global_memory_bytes
            if not mem_fits:
                rejection_reasons.append(
                    f"worker_memory_exceeded:{w.worker_id}:{est_bytes}>{w.global_memory_bytes}"
                )

            ops_needed = Fraction(count * lucas_factor * workload.cycles_per_item)
            duration = (
                ops_needed / w.steady_state_ops_per_second
                if count > 0
                else Fraction(0)
            )
            allocations.append(
                WorkerPartitionAllocation(
                    worker_id=w.worker_id,
                    tenant=w.tenant,
                    partition=(start, end),
                    item_count=count,
                    lanes=w.lanes,
                    estimated_bytes=est_bytes,
                    global_memory_bytes=w.global_memory_bytes,
                    memory_utilization=mem_util,
                    memory_fits=mem_fits,
                    steady_state_ops_per_second=w.steady_state_ops_per_second,
                    estimated_duration_seconds=duration,
                )
            )

    # Verify exact partition coverage (zero gaps, zero overlap)
    if workload.total_items == 0:
        zero_gaps = True
        zero_overlap = True
    elif not allocations:
        zero_gaps = False
        zero_overlap = True
    else:
        starts_at_zero = allocations[0].partition[0] == 0
        ends_at_total = allocations[-1].partition[1] == workload.total_items
        contiguous = all(
            a.partition[1] == b.partition[0]
            for a, b in zip(allocations, allocations[1:])
        )
        non_decreasing = all(a.partition[0] <= a.partition[1] for a in allocations)
        zero_gaps = bool(starts_at_zero and ends_at_total and contiguous and non_decreasing)
        zero_overlap = bool(contiguous and non_decreasing)

    if not zero_gaps or not zero_overlap:
        rejection_reasons.append("partition_coverage_failure")

    memory_admitted = bool(authorized) and all(a.memory_fits for a in allocations)
    if workload.required_floor_ops_per_second is not None:
        floor_admitted = aggregate_ops >= int(workload.required_floor_ops_per_second)
        if not floor_admitted:
            rejection_reasons.append(
                f"throughput_floor_not_met:{aggregate_ops}<{workload.required_floor_ops_per_second}"
            )
    else:
        floor_admitted = True

    admitted = bool(authorized and memory_admitted and floor_admitted and zero_gaps and zero_overlap)
    wall_seconds = max(
        (a.estimated_duration_seconds for a in allocations),
        default=Fraction(0),
    )

    return FleetCapacityPlan(
        work_id=workload.work_id,
        tenant=workload.tenant,
        workload=workload,
        workers=authorized,
        proportional_by_lanes=proportional_by_lanes,
        total_items=workload.total_items,
        lucas_scale_index=workload.scale_index,
        lucas_factor=lucas_factor,
        effective_scaled_items=effective_scaled_items,
        total_workers=total_workers,
        total_lanes=total_lanes,
        total_compute_units=total_cus,
        total_global_memory_bytes=total_mem,
        total_required_memory_bytes=total_required_mem,
        memory_admitted=memory_admitted,
        floor_admitted=floor_admitted,
        admitted=admitted,
        rejection_reasons=tuple(rejection_reasons),
        aggregate_steady_state_ops_per_second=aggregate_ops,
        estimated_wall_seconds=wall_seconds,
        allocations=tuple(allocations),
        zero_gaps=zero_gaps,
        zero_overlap=zero_overlap,
        one_igpu_per_worker=True,
        truth_class=TRUTH_CLASS_CAPACITY_PLAN,
    )


def issue_fleet_capacity_certificate(plan: FleetCapacityPlan) -> FleetCapacityCertificate:
    """Issue a canonical SHA-256 + Merkle-attested capacity certificate for a FleetCapacityPlan."""
    plan_dict = plan.as_dict()
    leaves = (
        {"workload": plan_dict["workload"]},
        {"workers": plan_dict["workers"]},
        {"allocations": plan_dict["allocations"]},
        {
            "admitted": plan.admitted,
            "aggregate_steady_state_ops_per_second": plan_dict[
                "aggregate_steady_state_ops_per_second"
            ],
            "zero_gaps": plan.zero_gaps,
            "zero_overlap": plan.zero_overlap,
        },
    )
    unsigned = {
        "schema": FLEET_CAPACITY_SCHEMA,
        "plan": plan_dict,
        "admitted": plan.admitted,
        "theorem": (
            "C_fleet = sum_w(CU_w * lanes_w * clock_w / I_w) and "
            "union_w([start_w, end_w)) = [0, N) with pairwise empty intersection"
        ),
        "truth_class": TRUTH_CLASS_CAPACITY_PLAN,
        "attestation_root": _merkle_root(leaves),
    }
    return FleetCapacityCertificate(
        **unsigned,
        certificate_digest=canonical_sha256(unsigned),
    )


def verify_fleet_capacity_certificate(certificate: FleetCapacityCertificate) -> bool:
    """Recompute and verify a FleetCapacityCertificate from its embedded specification."""
    if certificate.schema != FLEET_CAPACITY_SCHEMA:
        raise ValueError(f"Unsupported fleet capacity certificate schema: {certificate.schema}")
    if certificate.truth_class != TRUTH_CLASS_CAPACITY_PLAN:
        raise ValueError(f"Invalid truth_class on capacity certificate: {certificate.truth_class}")
    plan_dict = certificate.plan
    workload = WorkloadSpec.from_dict(plan_dict["workload"])
    workers = [GPUWorkerSpec.from_dict(w) for w in plan_dict["workers"]]
    recomputed_plan = plan_gpu_fleet_capacity(
        workers,
        workload,
        proportional_by_lanes=bool(plan_dict.get("proportional_by_lanes", True)),
    )
    expected = issue_fleet_capacity_certificate(recomputed_plan)
    if certificate != expected:
        raise ValueError("FleetCapacityCertificate failed exact deterministic replay verification")
    return True


@dataclass(frozen=True, kw_only=True)
class FleetWorkloadReport:
    """Complete execution and provenance report for a distributed GPU fleet workload."""

    work_id: str
    tenant: str
    capacity_plan: FleetCapacityPlan
    capacity_certificate: FleetCapacityCertificate
    certificate_verified: bool
    partition_results: tuple[ExecutionResult, ...]
    reassembled_output: list[Any]
    reference_output: list[Any]
    single_vs_distributed_agree: bool
    output_digest: str
    custody_committed_count: int
    failover_events: tuple[dict[str, Any], ...]
    buffer_attestation: Optional[BufferAttestation] = None

    def as_exact_dict(self) -> dict[str, Any]:
        """Return a 100% exact dictionary representation (zero floats) suitable for audit_exactness."""
        return {
            "work_id": self.work_id,
            "tenant": self.tenant,
            "capacity_plan": self.capacity_plan.as_dict(),
            "capacity_certificate": self.capacity_certificate.as_dict(),
            "certificate_verified": bool(self.certificate_verified),
            "partition_results": [
                {
                    "work_id": r.work_id,
                    "worker_id": r.worker_id,
                    "lease_id": r.lease_id,
                    "tenant": r.tenant,
                    "partition": [int(r.partition[0]), int(r.partition[1])],
                    "generation": int(r.generation),
                    "fencing_token": r.fencing_token,
                    "backend": r.backend,
                    "sha256d_evaluations": int(r.sha256d_evaluations),
                    "output_digest": r.output_digest,
                }
                for r in self.partition_results
            ],
            "reassembled_output": list(self.reassembled_output),
            "reference_output": list(self.reference_output),
            "single_vs_distributed_agree": bool(self.single_vs_distributed_agree),
            "output_digest": self.output_digest,
            "custody_committed_count": int(self.custody_committed_count),
            "failover_events": list(self.failover_events),
        }


def execute_fleet_workload(
    workers: Sequence[GPUWorkerSpec],
    workload: WorkloadSpec,
    input_data: Sequence[Any],
    kernel: Callable[[Any], Any],
    *,
    proportional_by_lanes: bool = True,
    fail_worker_ids: Sequence[str] = (),
    authentication_key: Optional[bytes] = None,
) -> FleetWorkloadReport:
    """Plan, partition, lease, execute, and custody-verify a workload across a GPU/iGPU fleet."""
    items = list(input_data)
    if len(items) != workload.total_items:
        raise ValueError(
            f"input_data length ({len(items)}) does not match workload.total_items ({workload.total_items})"
        )

    plan = plan_gpu_fleet_capacity(
        workers,
        workload,
        proportional_by_lanes=proportional_by_lanes,
    )
    if not plan.admitted:
        raise ValueError(
            f"Workload {workload.work_id!r} rejected by fleet capacity admission: {plan.rejection_reasons}"
        )

    certificate = issue_fleet_capacity_certificate(plan)
    cert_verified = verify_fleet_capacity_certificate(certificate)

    native_workers: dict[str, NativeIGPUWorker] = {}
    for spec in plan.workers:
        identity = WorkerIdentity(
            worker_id=spec.worker_id,
            generation=spec.generation,
            instance_id=f"{workload.work_id}:{spec.worker_id}",
            tenant=spec.tenant,
        )
        host_plan = HostGPUPlan(
            total_items=max(1, workload.total_items),
            lanes=spec.lanes,
            mode=spec.mode,
            backend=spec.backend,
            device_count=1,
        )
        native_workers[spec.worker_id] = NativeIGPUWorker(identity, host_plan)

    scheduler = FleetScheduler(native_workers, default_ttl=300.0)
    custody = FleetCustody()
    fail_set = set(fail_worker_ids)
    failover_events: list[dict[str, Any]] = []
    partition_results: list[ExecutionResult] = []
    reassembled: list[Any] = [None] * workload.total_items

    for alloc in plan.allocations:
        if alloc.item_count == 0:
            continue
        start, end = alloc.partition
        slice_items = items[start:end]
        part_work_id = f"{workload.work_id}:part:{start}:{end}"
        spec_map = {w.worker_id: w for w in plan.workers}
        w_spec = spec_map[alloc.worker_id]
        budget = {
            "cpu_cores": w_spec.cpu_cores,
            "memory_mb": w_spec.memory_mb,
            "concurrency": w_spec.lanes,
        }

        lease = scheduler.issue_lease(
            work_id=part_work_id,
            tenant=workload.tenant,
            operation=workload.operation,
            input_data=slice_items,
            partition=(start, end),
            resource_budget=budget,
            target_worker=alloc.worker_id,
        )
        if lease is None:
            raise RuntimeError(f"Scheduler failed to issue lease for partition {(start, end)}")

        if alloc.worker_id in fail_set:
            fail_set.remove(alloc.worker_id)
            old_worker = scheduler.workers[alloc.worker_id]
            stale_result = old_worker.execute(
                part_work_id,
                kernel,
                slice_items,
                lease=lease,
            )
            old_token = lease.fencing_token
            rotated_identity = scheduler.worker_terminated(alloc.worker_id)
            custody.revoke_fencing_token(old_token)

            stale_sched_ok = scheduler.register_result(
                lease_id=lease.lease_id,
                worker=old_worker,
                result=stale_result,
            )
            stale_custody_ok = custody.verify_and_commit(
                stale_result,
                workload.tenant,
            )
            if stale_sched_ok or stale_custody_ok:
                raise RuntimeError("Stale result from terminated worker was not rejected")

            lease = scheduler.issue_lease(
                work_id=part_work_id,
                tenant=workload.tenant,
                operation=workload.operation,
                input_data=slice_items,
                partition=(start, end),
                resource_budget=budget,
                target_worker=alloc.worker_id,
            )
            if lease is None or rotated_identity is None:
                raise RuntimeError(f"Failed to reassign partition {(start, end)} after termination")

            failover_events.append(
                {
                    "worker_id": alloc.worker_id,
                    "partition": [start, end],
                    "revoked_fencing_token": old_token,
                    "new_fencing_token": lease.fencing_token,
                    "new_generation": int(rotated_identity.generation),
                    "stale_rejected": True,
                }
            )

        active_worker = scheduler.workers[alloc.worker_id]
        result = active_worker.execute(
            part_work_id,
            kernel,
            slice_items,
            lease=lease,
        )
        active_worker.complete_lease(lease.lease_id, result)

        if not scheduler.register_result(
            lease_id=lease.lease_id,
            worker=active_worker,
            result=result,
        ):
            raise RuntimeError(f"Scheduler rejected valid partition result for {part_work_id}")

        if not custody.verify_and_commit(
            result,
            workload.tenant,
            expected_fencing_token=lease.fencing_token,
        ):
            raise RuntimeError(f"Custody rejected valid partition result for {part_work_id}")

        partition_results.append(result)
        part_out = list(result.result) if isinstance(result.result, list) else []
        reassembled[start:end] = part_out

    if workload.total_items > 0:
        ref_plan = HostGPUPlan(
            total_items=workload.total_items,
            lanes=max(1, min(plan.total_lanes, workload.total_items)),
            mode="host_gpu_overlay",
            backend="cpu_reference",
            device_count=1,
        )
        reference_output = execute_reference(items, ref_plan, kernel)
    else:
        reference_output = []

    agree = reassembled == reference_output
    output_digest = hashlib.sha256(repr(reassembled).encode("utf-8")).hexdigest()

    attestation: Optional[BufferAttestation] = None
    if reassembled and all(isinstance(x, (int, float)) for x in reassembled):
        gate = BufferIntegrityGate(authentication_key=authentication_key)
        attestation = gate.attest(
            reassembled,
            device_fingerprint=certificate.certificate_digest,
        )
        gate.verify(reassembled, attestation)

    return FleetWorkloadReport(
        work_id=workload.work_id,
        tenant=workload.tenant,
        capacity_plan=plan,
        capacity_certificate=certificate,
        certificate_verified=cert_verified,
        partition_results=tuple(partition_results),
        reassembled_output=reassembled,
        reference_output=reference_output,
        single_vs_distributed_agree=agree,
        output_digest=output_digest,
        custody_committed_count=custody.committed_count,
        failover_events=tuple(failover_events),
        buffer_attestation=attestation,
    )


__all__ = [
    "FLEET_CAPACITY_SCHEMA",
    "TRUTH_CLASS_CAPACITY_PLAN",
    "FleetCapacityCertificate",
    "FleetCapacityPlan",
    "FleetWorkloadReport",
    "GPUWorkerSpec",
    "WorkerPartitionAllocation",
    "WorkloadSpec",
    "execute_fleet_workload",
    "issue_fleet_capacity_certificate",
    "plan_gpu_fleet_capacity",
    "verify_fleet_capacity_certificate",
]
