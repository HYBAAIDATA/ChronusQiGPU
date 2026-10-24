"""Tests for GPU Fleet Capacity Planning, Certificates, and Distributed Workload Execution."""
from __future__ import annotations

from fractions import Fraction
import pytest

from chronus.fleet.capacity import (
    GPUWorkerSpec,
    WorkloadSpec,
    execute_fleet_workload,
    issue_fleet_capacity_certificate,
    plan_gpu_fleet_capacity,
    verify_fleet_capacity_certificate,
)
from turing_universal_quantum_computer.quantum_library import audit_exactness


def _sample_fleet(tenant: str = "tenant_a") -> list[GPUWorkerSpec]:
    return [
        GPUWorkerSpec(
            worker_id="gpu-w1",
            tenant=tenant,
            lanes=8,
            compute_units=32,
            clock_mhz=1500,
            global_memory_bytes=8 * 1024**3,
        ),
        GPUWorkerSpec(
            worker_id="gpu-w2",
            tenant=tenant,
            lanes=16,
            compute_units=64,
            clock_mhz=1500,
            global_memory_bytes=16 * 1024**3,
        ),
        GPUWorkerSpec(
            worker_id="gpu-w3",
            tenant=tenant,
            lanes=8,
            compute_units=32,
            clock_mhz=1500,
            global_memory_bytes=8 * 1024**3,
        ),
    ]


def test_gpu_fleet_capacity_plan_and_certificate_replay():
    fleet = _sample_fleet("tenant_a")
    workload = WorkloadSpec(
        work_id="lucas-batch-1",
        tenant="tenant_a",
        operation="poly_eval",
        total_items=32,
        bytes_per_item=1024,
        cycles_per_item=4,
        scale_index=15,
        state_qubits=6,
        required_floor_ops_per_second=1_000_000_000,
    )
    plan = plan_gpu_fleet_capacity(fleet, workload, proportional_by_lanes=True)
    assert plan.admitted is True
    assert plan.zero_gaps is True
    assert plan.zero_overlap is True
    assert plan.one_igpu_per_worker is True
    assert plan.lucas_factor == 1364  # L_15 = 1364
    assert plan.effective_scaled_items == 32 * 1364
    assert [a.partition for a in plan.allocations] == [(0, 8), (8, 24), (24, 32)]

    cert = issue_fleet_capacity_certificate(plan)
    assert verify_fleet_capacity_certificate(cert) is True
    assert audit_exactness(cert.as_dict()).exact is True


def test_gpu_fleet_capacity_rejects_excess_memory_or_floor():
    fleet = [
        GPUWorkerSpec(
            worker_id="small-gpu",
            tenant="tenant_a",
            lanes=4,
            compute_units=8,
            clock_mhz=1000,
            global_memory_bytes=1024,  # 1 KiB only
        )
    ]
    workload = WorkloadSpec(
        work_id="oversized-statevector",
        tenant="tenant_a",
        operation="statevector_sim",
        total_items=4,
        bytes_per_item=64,
        state_qubits=10,  # 16 * 1024 = 16384 bytes per item > 1024 bytes
        required_floor_ops_per_second=10**18,
    )
    plan = plan_gpu_fleet_capacity(fleet, workload)
    assert plan.admitted is False
    assert plan.memory_admitted is False
    assert plan.floor_admitted is False
    assert any("worker_memory_exceeded" in r for r in plan.rejection_reasons)
    assert any("throughput_floor_not_met" in r for r in plan.rejection_reasons)


def test_execute_fleet_workload_with_midflight_worker_failover():
    fleet = _sample_fleet("tenant_a")
    workload = WorkloadSpec(
        work_id="distributed-map-32",
        tenant="tenant_a",
        operation="quadratic_map",
        total_items=32,
        bytes_per_item=128,
        scale_index=10,
    )
    inputs = list(range(32))

    def kernel(x: int) -> int:
        return x * x + 3 * x + 1

    report = execute_fleet_workload(
        fleet,
        workload,
        inputs,
        kernel,
        fail_worker_ids=("gpu-w2",),
        authentication_key=b"chronus-fleet-hmac-key",
    )
    assert report.certificate_verified is True
    assert report.single_vs_distributed_agree is True
    assert report.reassembled_output == [kernel(x) for x in inputs]
    assert report.custody_committed_count == 3
    assert len(report.failover_events) == 1
    assert report.failover_events[0]["worker_id"] == "gpu-w2"
    assert report.failover_events[0]["stale_rejected"] is True
    assert report.failover_events[0]["new_generation"] == 2
    assert report.buffer_attestation is not None
    assert report.buffer_attestation.hmac_sha256 is not None
    assert audit_exactness(report.as_exact_dict()).exact is True
