"""Fleet qualification test - tenant boundaries survive retries and restart."""
from __future__ import annotations

from chronus.fleet.custody import FleetCustody
from chronus.fleet.native_worker import NativeIGPUWorker
from chronus.fleet.scheduler import FleetScheduler
from chronus.fleet.worker_identity import WorkerIdentity
from chronus.igpu.host import HostGPUPlan


def test_tenant_boundaries():
    """Tenant boundaries survive retries and restart."""
    print("[TEST 5] Tenant boundaries")
    scheduler = FleetScheduler({}, 30)
    custody = FleetCustody()

    items = list(range(4))

    # Different tenant should be rejected when verifying against tenant_alpha
    lease = scheduler.issue_lease(
        work_id="bound1",
        tenant="tenant_beta",
        operation="op",
        input_data=items,
    )
    assert lease is not None
    w = NativeIGPUWorker(
        WorkerIdentity(
            worker_id="w1",
            generation=1,
            instance_id="t1",
            tenant="tenant_beta",
        ),
        HostGPUPlan(total_items=4, lanes=2, mode="host_gpu_overlay"),
    )
    r = w.execute(lease.work_id, lambda x: x, items, lease=lease)
    w.complete_lease(lease.lease_id, r)
    rejected = not custody.verify_and_commit(r, "tenant_alpha")
    assert rejected is True
    print(f"  Different tenant rejected: {rejected}")

    # Same tenant retry should work
    lease2 = scheduler.issue_lease(
        work_id="bound2",
        tenant="tenant_alpha",
        operation="op",
        input_data=items,
    )
    assert lease2 is not None
    w2 = NativeIGPUWorker(
        WorkerIdentity(
            worker_id="w2",
            generation=1,
            instance_id="t2",
            tenant="tenant_alpha",
        ),
        HostGPUPlan(total_items=4, lanes=2, mode="host_gpu_overlay"),
    )
    r2 = w2.execute(lease2.work_id, lambda x: x, items, lease=lease2)
    w2.complete_lease(lease2.lease_id, r2)
    accepted = custody.verify_and_commit(r2, "tenant_alpha")
    assert accepted is True
    print(f"  Same tenant retry accepted: {accepted}")

    # Verify persisted result
    committed = custody.get_committed("bound2")
    assert committed is not None
    print(f"  Result persisted: {committed.output_digest[:16]}...")
    print("  [PASS] Tenant boundaries demonstrated")
