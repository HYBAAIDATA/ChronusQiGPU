"""Fleet qualification test - partitions have no gaps or overlap."""
from __future__ import annotations

from chronus.fleet.native_worker import NativeIGPUWorker
from chronus.fleet.scheduler import FleetScheduler
from chronus.fleet.worker_identity import WorkerIdentity
from chronus.igpu.host import HostGPUPlan


def test_partitions_no_gaps():
    """Partitions have no gaps or unintended overlap."""
    print("[TEST 2] Partitions no gaps/overlap")
    plan = HostGPUPlan(total_items=16, lanes=4, mode="host_gpu_overlay")

    workers = {}
    for i, wid in enumerate(["w1", "w2", "w3"]):
        identity = WorkerIdentity(
            worker_id=wid,
            generation=1,
            instance_id=f"t{i+1}",
            tenant="ta",
        )
        workers[wid] = NativeIGPUWorker(identity, plan)

    scheduler = FleetScheduler(workers, 30)

    # Partition: w1=[0,6), w2=[6,12), w3=[12,16)
    leases = [
        scheduler.issue_lease(
            work_id="p1",
            tenant="ta",
            operation="op",
            input_data=list(range(6)),
            target_worker="w1",
        ),
        scheduler.issue_lease(
            work_id="p2",
            tenant="ta",
            operation="op",
            input_data=list(range(6, 12)),
            target_worker="w2",
        ),
        scheduler.issue_lease(
            work_id="p3",
            tenant="ta",
            operation="op",
            input_data=list(range(12, 16)),
            target_worker="w3",
        ),
    ]

    for lease in leases:
        assert lease is not None
        wid = list(workers.keys())[
            list([l.lease_id for l in leases if l is not None]).index(lease.lease_id)
        ]
        r = workers[wid].execute(
            lease.work_id,
            lambda x: x,
            list(range(lease.partition[1] - lease.partition[0])),
        )
        workers[wid].complete_lease(lease.lease_id, r)

    # Verify: items 0-5, 6-11, 12-15 covered exactly once
    all_items = set(range(16))
    covered = set()
    total_covered_count = 0
    for wid, worker in workers.items():
        for lid, lease in worker._active_leases.items():
            part_range = range(lease.partition[0], lease.partition[1])
            total_covered_count += len(part_range)
            covered.update(part_range)

    gaps = all_items - covered
    assert len(gaps) == 0
    assert total_covered_count == 16
    print(f"  Covered: {sorted(covered)}")
    print(f"  Gaps: {sorted(gaps) if gaps else 'none'}")
    print(f"  No gaps: {len(gaps) == 0}")
    print("  [PASS] Partitions demonstrated")
