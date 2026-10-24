"""Chronus multi-worker ONE-iGPU fleet, capacity planning, and custody package."""

from __future__ import annotations

from chronus.fleet.capacity import (
    FLEET_CAPACITY_SCHEMA,
    TRUTH_CLASS_CAPACITY_PLAN,
    FleetCapacityCertificate,
    FleetCapacityPlan,
    FleetWorkloadReport,
    GPUWorkerSpec,
    WorkerPartitionAllocation,
    WorkloadSpec,
    execute_fleet_workload,
    issue_fleet_capacity_certificate,
    plan_gpu_fleet_capacity,
    verify_fleet_capacity_certificate,
)
from chronus.fleet.custody import FleetCustody
from chronus.fleet.native_worker import ExecutionResult, NativeIGPUWorker
from chronus.fleet.scheduler import FleetScheduler
from chronus.fleet.worker_identity import WorkerIdentity, WorkLease

__all__ = [
    "ExecutionResult",
    "FLEET_CAPACITY_SCHEMA",
    "FleetCapacityCertificate",
    "FleetCapacityPlan",
    "FleetCustody",
    "FleetScheduler",
    "FleetWorkloadReport",
    "GPUWorkerSpec",
    "NativeIGPUWorker",
    "TRUTH_CLASS_CAPACITY_PLAN",
    "WorkLease",
    "WorkerIdentity",
    "WorkerPartitionAllocation",
    "WorkloadSpec",
    "execute_fleet_workload",
    "issue_fleet_capacity_certificate",
    "plan_gpu_fleet_capacity",
    "verify_fleet_capacity_certificate",
]
