"""tests/test_chronus_fleet.py -- Regressions and qualification suite for Chronus GPU Fleet.

Covers:
1. Exact rational capacity planning and Lucas $L_n$ ladder scaling.
2. Zero-gap and zero-overlap partition allocation across tenant workers.
3. Merkle-rooted cryptographic capacity certificates and tamper detection.
4. Fleet custody, multi-tenant isolation, and unauthorized commit blocking.
5. Idempotent duplicate delivery and stale commit rejection.
6. Mid-flight worker termination with fencing token rotation and safe reassignment.
7. End-to-end distributed execution agreement against single-instance reference.
8. ChronusDevice to GPUWorkerSpec conversion and ChronusScheduler fleet planning.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from fractions import Fraction
import pytest

import chronus
from chronus.domain import (
    ChronusBackend,
    ChronusCapabilities,
    ChronusDevice,
    ChronusDeviceTopology,
    ChronusDeviceType,
    ChronusMemory,
    ChronusScheduler,
)
from chronus.fleet import (
    ExecutionResult,
    FleetCapacityCertificate,
    FleetCapacityPlan,
    FleetCustody,
    FleetScheduler,
    FleetWorkloadReport,
    GPUWorkerSpec,
    NativeIGPUWorker,
    WorkerIdentity,
    WorkerPartitionAllocation,
    WorkLease,
    WorkloadSpec,
    execute_fleet_workload,
    issue_fleet_capacity_certificate,
    plan_gpu_fleet_capacity,
    verify_fleet_capacity_certificate,
)
from chronus.igpu.host import HostGPUPlan, execute_reference


def _create_sample_fleet(tenant: str = "tenant_prime") -> list[GPUWorkerSpec]:
    return [
        GPUWorkerSpec(
            worker_id="fleet-node-1",
            tenant=tenant,
            lanes=8,
            compute_units=32,
            clock_mhz=1600,
            global_memory_bytes=8 * 1024**3,
        ),
        GPUWorkerSpec(
            worker_id="fleet-node-2",
            tenant=tenant,
            lanes=16,
            compute_units=64,
            clock_mhz=1600,
            global_memory_bytes=16 * 1024**3,
        ),
        GPUWorkerSpec(
            worker_id="fleet-node-3",
            tenant=tenant,
            lanes=8,
            compute_units=32,
            clock_mhz=1600,
            global_memory_bytes=8 * 1024**3,
        ),
    ]


@pytest.mark.unit
def test_fleet_capacity_planning_rational_arithmetic():
    """Fleet capacity planning uses exact rational arithmetic and Lucas L_n scaling."""
    fleet = _create_sample_fleet("tenant_prime")
    workload = WorkloadSpec(
        work_id="lucas-run-42",
        tenant="tenant_prime",
        operation="matrix_poly",
        total_items=32,
        bytes_per_item=2048,
        cycles_per_item=8,
        scale_index=15,  # Lucas L_15 = 1364
        state_qubits=8,
        required_floor_ops_per_second=100_000_000,
    )

    plan = plan_gpu_fleet_capacity(fleet, workload, proportional_by_lanes=True)

    assert plan.admitted is True
    assert plan.zero_gaps is True
    assert plan.zero_overlap is True
    assert plan.one_igpu_per_worker is True
    assert plan.lucas_factor == 1364
    assert plan.effective_scaled_items == 32 * 1364
    assert plan.total_lanes == 32  # 8 + 16 + 8
    assert plan.total_workers == 3
    assert plan.total_compute_units == 128  # 32 + 64 + 32

    # Lane fractions must be exact: 8/32 = 1/4, 16/32 = 1/2, 8/32 = 1/4
    allocs = plan.allocations
    assert len(allocs) == 3
    assert Fraction(allocs[0].lanes, plan.total_lanes) == Fraction(1, 4)
    assert Fraction(allocs[1].lanes, plan.total_lanes) == Fraction(1, 2)
    assert Fraction(allocs[2].lanes, plan.total_lanes) == Fraction(1, 4)

    # Disjoint partitions: [0, 8), [8, 24), [24, 32)
    assert [a.partition for a in allocs] == [(0, 8), (8, 24), (24, 32)]

    # Item counts match exactly
    assert allocs[0].item_count == 8
    assert allocs[1].item_count == 16
    assert allocs[2].item_count == 8
    assert sum(a.item_count for a in allocs) == 32
    assert all(isinstance(a.memory_utilization, Fraction) for a in allocs)


@pytest.mark.unit
def test_fleet_capacity_certificate_cryptographic_verification():
    """Cryptographic Merkle-rooted certificate generation and tamper detection."""
    fleet = _create_sample_fleet("tenant_prime")
    workload = WorkloadSpec(
        work_id="cert-verify-1",
        tenant="tenant_prime",
        operation="poly_eval",
        total_items=16,
        bytes_per_item=1024,
        scale_index=10,  # L_10 = 123
    )
    plan = plan_gpu_fleet_capacity(fleet, workload, proportional_by_lanes=True)
    cert = issue_fleet_capacity_certificate(plan)

    # Clean certificate verification
    assert verify_fleet_capacity_certificate(cert) is True
    assert cert.truth_class == "exact_mathematical_capacity_and_partition_plan"
    assert len(cert.attestation_root) == 64

    # Tampered certificate detection raises ValueError
    tampered_plan = dict(cert.plan)
    tampered_plan["effective_scaled_items"] = 999999
    tampered_cert = replace(cert, plan=tampered_plan)
    with pytest.raises(ValueError, match="failed exact deterministic replay"):
        verify_fleet_capacity_certificate(tampered_cert)


@pytest.mark.unit
def test_fleet_custody_and_multi_tenant_isolation():
    """Fleet custody enforces strict tenant boundary isolation."""
    custody = FleetCustody()

    # Unauthorized tenant commit must be rejected
    unauthorized_result = ExecutionResult(
        lease_id="lease-unauth",
        work_id="work-tenant-boundary",
        tenant="unauthorized_rogue",
        operation="crypto_op",
        output_digest="0" * 64,
        partition=(0, 8),
        success=True,
        timestamp=datetime.now(),
    )
    committed = custody.verify_and_commit(unauthorized_result, expected_tenant="authorized_client")
    assert committed is False

    # Authorized tenant commit must succeed
    authorized_result = ExecutionResult(
        lease_id="lease-auth",
        work_id="work-tenant-boundary",
        tenant="authorized_client",
        operation="crypto_op",
        output_digest="1" * 64,
        partition=(0, 8),
        success=True,
        timestamp=datetime.now(),
    )
    committed_auth = custody.verify_and_commit(authorized_result, expected_tenant="authorized_client")
    assert committed_auth is True

    # Persisted record retrieval
    record = custody.get_committed("work-tenant-boundary")
    assert record is not None
    assert record.tenant == "authorized_client"
    assert record.output_digest == "1" * 64


@pytest.mark.unit
def test_fleet_duplicate_and_stale_commit_prevention():
    """Idempotent delivery of duplicate digests and rejection of conflicting stale digests."""
    custody = FleetCustody()
    wid = WorkerIdentity(worker_id="w-dup", generation=1, instance_id="inst-1", tenant="tenant_x")
    worker = NativeIGPUWorker(wid, HostGPUPlan(total_items=4, lanes=2, mode="host_gpu_overlay"))
    scheduler = FleetScheduler({"w-dup": worker}, default_ttl=30.0)

    items = [10, 20, 30, 40]
    lease = scheduler.issue_lease(
        work_id="dup-work-1",
        tenant="tenant_x",
        operation="identity",
        input_data=items,
    )
    assert lease is not None

    res = worker.execute(lease.work_id, lambda x: x, items, lease=lease)
    worker.complete_lease(lease.lease_id, res)
    assert custody.verify_and_commit(res, "tenant_x") is True

    # Idempotent re-commit of identical digest succeeds
    assert custody.check_duplicate(res.work_id, res.output_digest) is True

    # Stale/conflicting commit for same work_id with altered digest is flagged and rejected
    assert custody.check_stale(res.work_id, "f" * 64) is True

    stale_result = ExecutionResult(
        lease_id="lease-stale",
        work_id="dup-work-1",
        tenant="tenant_x",
        operation="identity",
        output_digest="f" * 64,
        partition=(0, 4),
        success=True,
        timestamp=datetime.now(),
    )
    assert custody.verify_and_commit(stale_result, "tenant_x") is False


@pytest.mark.unit
def test_fleet_worker_termination_and_fencing_token_rotation():
    """Mid-flight worker termination rotates fencing tokens and prevents zombie commits."""
    wid = WorkerIdentity(worker_id="w-failover", generation=1, instance_id="i-1", tenant="tenant_y")
    worker = NativeIGPUWorker(wid, HostGPUPlan(total_items=8, lanes=4, mode="host_gpu_overlay"))
    scheduler = FleetScheduler({"w-failover": worker}, default_ttl=30.0)

    # Initial lease with initial fencing token
    lease_1 = scheduler.issue_lease(
        work_id="work-term",
        tenant="tenant_y",
        operation="op",
        input_data=list(range(8)),
    )
    assert lease_1 is not None
    initial_fencing = lease_1.fencing_token

    # Simulate worker crash / termination
    new_fencing = "fencing_epoch_token_9999"
    scheduler.worker_terminated("w-failover", fencing_token=new_fencing)

    # Subsequent lease issued after failure receives new rotated fencing token
    lease_2 = scheduler.issue_lease(
        work_id="work-term-retry",
        tenant="tenant_y",
        operation="op",
        input_data=list(range(8)),
        target_worker="w-failover",
    )
    assert lease_2 is not None
    assert lease_2.fencing_token == new_fencing
    assert lease_2.fencing_token != initial_fencing


@pytest.mark.unit
def test_end_to_end_distributed_fleet_execution_agreement():
    """Distributed execution across isolated fleet nodes produces bit-exact reference result."""
    fleet = _create_sample_fleet("tenant_sim")
    items = list(range(16))
    workload = WorkloadSpec(
        work_id="dist-agree-run",
        tenant="tenant_sim",
        operation="square_add",
        total_items=len(items),
        scale_index=12,  # L_12 = 322
    )

    def kernel(x: int) -> int:
        return x * x + 7

    # 1. Single-instance reference execution
    ref_plan = HostGPUPlan(total_items=len(items), lanes=4, mode="host_gpu_overlay")
    ref_output = execute_reference(items, ref_plan, kernel)

    # 2. Distributed fleet execution
    report = execute_fleet_workload(
        workers=fleet,
        workload=workload,
        input_data=items,
        kernel=kernel,
        proportional_by_lanes=True,
    )

    assert isinstance(report, FleetWorkloadReport)
    assert report.certificate_verified is True
    assert report.single_vs_distributed_agree is True
    assert report.reassembled_output == ref_output
    assert report.reassembled_output == report.reference_output
    assert report.custody_committed_count == len(report.partition_results)


@pytest.mark.unit
def test_chronus_device_to_fleet_worker_integration():
    """ChronusDevice seamlessly converts to GPUWorkerSpec and binds to ChronusScheduler fleet planning."""
    # Build 2 ChronusDevices with different compute capabilities
    dev1 = ChronusDevice(
        id="opencl:node1:iris",
        name="Node 1 iGPU",
        vendor="intel",
        device_type=ChronusDeviceType.INTEGRATED_GPU,
        backend=ChronusBackend.OPENCL,
        memory=ChronusMemory(total_bytes=8 * 1024**3, is_unified=True, memory_type="UMA"),
        capabilities=ChronusCapabilities(compute_units=32, has_unified_memory=True, is_integrated=True),
        is_integrated=True,
    )
    dev2 = ChronusDevice(
        id="cuda:node2:rtx",
        name="Node 2 GPU",
        vendor="nvidia",
        device_type=ChronusDeviceType.DISCRETE_GPU,
        backend=ChronusBackend.CUDA,
        memory=ChronusMemory(total_bytes=16 * 1024**3, is_unified=False, memory_type="VRAM"),
        capabilities=ChronusCapabilities(compute_units=64, has_unified_memory=False, is_integrated=False),
        is_integrated=False,
    )

    # Verify device to worker specification conversion
    spec1 = dev1.to_worker_spec(tenant="alpha", worker_id="w-alpha-1")
    assert isinstance(spec1, GPUWorkerSpec)
    assert spec1.worker_id == "w-alpha-1"
    assert spec1.tenant == "alpha"
    assert spec1.compute_units == 32
    assert spec1.global_memory_bytes == 8 * 1024**3

    spec2 = dev2.to_worker_spec(tenant="alpha", worker_id="w-alpha-2")
    assert spec2.compute_units == 64

    # ChronusScheduler fleet capacity planning
    scheduler = ChronusScheduler(devices=[dev1, dev2])
    workload = WorkloadSpec(
        work_id="scheduler-fleet-plan-1",
        tenant="alpha",
        operation="fft_transform",
        total_items=40,
        scale_index=10,
    )

    plan = scheduler.plan_fleet(workload, tenant="alpha", proportional_by_lanes=True)
    assert isinstance(plan, FleetCapacityPlan)
    assert plan.admitted is True
    assert plan.zero_gaps is True
    assert plan.zero_overlap is True
    assert plan.one_igpu_per_worker is True
    assert len(plan.allocations) == 2


@pytest.mark.unit
def test_canonical_workload_contracts_classes_a_through_e(tmp_path: Path):
    """Verify all canonical workload fixture contracts (Classes A-E + Refusal)."""
    from chronus.fleet.workload_contracts import canonical_workload_fixtures, run_all_workload_fixtures

    fixtures = canonical_workload_fixtures()
    assert len(fixtures) == 6
    assert set(fixtures.keys()) == {
        "fixture_a_exact_algebraic_quantum",
        "fixture_a_exact_domain_refusal",
        "fixture_b_native_quantum_numerical",
        "fixture_c_tensor_kellogg_planes",
        "fixture_d_resident_data_ovid_theseus",
        "fixture_e_integrated_service_lifecycle",
    }

    report = run_all_workload_fixtures(tmp_path)
    assert report["all_verified"] is True
    assert report["fixture_count"] == 6

    # Verify each class outcome independently
    outcomes = report["outcomes"]
    assert outcomes["fixture_a_exact_algebraic_quantum"]["verified"] is True
    assert outcomes["fixture_a_exact_domain_refusal"]["verified"] is True
    assert outcomes["fixture_b_native_quantum_numerical"]["verified"] is True
    assert outcomes["fixture_c_tensor_kellogg_planes"]["verified"] is True
    assert outcomes["fixture_d_resident_data_ovid_theseus"]["verified"] is True
    assert outcomes["fixture_e_integrated_service_lifecycle"]["verified"] is True
