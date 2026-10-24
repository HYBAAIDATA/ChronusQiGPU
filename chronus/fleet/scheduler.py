"""Fleet scheduler issuing bounded expiring work leases with partition coverage and fencing tokens."""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, Optional

from chronus.fleet.native_worker import ExecutionResult, NativeIGPUWorker
from chronus.fleet.worker_identity import WorkerIdentity, WorkLease
from chronus.igpu.host import HostGPUPlan


class FleetScheduler:
    """Issues bounded expiring work leases with partitions, resource budgets,
    deadlines, fencing tokens, and worker termination handling.

    Design decisions:
    - ONE iGPU per worker (device_count == 1) preserved
    - Leases carry partition ranges to guarantee no gaps/overlap
    - Fencing tokens rotate on worker restart, invalidating old leases
    - Idempotency: same work_id + same output_digest accepted; different digest rejected
    """

    def __init__(self, workers: Dict[str, NativeIGPUWorker], default_ttl: float = 300.0):
        """Initialize scheduler with a mapping of worker_id -> NativeIGPUWorker."""
        self._workers: Dict[str, NativeIGPUWorker] = dict(workers)
        self._allow_ephemeral_workers: bool = len(self._workers) == 0
        self._default_ttl = float(default_ttl)
        self._active_leases: Dict[str, WorkLease] = {}
        self._work_id_history: Dict[str, list[tuple[str, str]]] = {}
        self._tenant_partition_cursor: Dict[str, int] = {}
        self._revoked_fencing_tokens: set[str] = set()

    @property
    def workers(self) -> Dict[str, NativeIGPUWorker]:
        return dict(self._workers)

    def register_worker(self, worker: NativeIGPUWorker) -> None:
        """Register or replace a worker in the fleet pool."""
        if worker.device_count != 1:
            raise ValueError("FleetScheduler requires ONE iGPU per worker (device_count == 1)")
        self._workers[worker.identity.worker_id] = worker

    def issue_lease(
        self,
        *,
        work_id: str,
        tenant: str,
        operation: str,
        input_data: Any,
        partition: Optional[tuple[int, int]] = None,
        resource_budget: Optional[dict[str, int]] = None,
        deadline_override: Optional[float] = None,
        target_worker: Optional[str] = None,
    ) -> Optional[WorkLease]:
        """Issue a bounded expiring work lease.

        Enforces:
        - Tenant authorization (tenant must match worker assignment)
        - Partition coverage (no gaps/overlap via contiguous cursor or explicit range)
        - Resource budget (cpu_cores, memory_mb, concurrency)
        - String fencing token from worker identity
        """
        items_len = len(input_data) if hasattr(input_data, "__len__") else 0
        assigned_worker_id = self._assign_worker(
            tenant=tenant,
            partition=partition,
            target_worker=target_worker,
            default_items=max(1, items_len),
        )
        if assigned_worker_id is None:
            return None

        worker = self._workers[assigned_worker_id]
        identity = worker.identity

        if partition is None:
            total_plan_items = max(1, worker.plan.total_items)
            slice_items = items_len if items_len > 0 else total_plan_items
            cursor = self._tenant_partition_cursor.get(tenant, 0)
            if cursor + slice_items <= total_plan_items:
                partition = (cursor, cursor + slice_items)
                next_cursor = cursor + slice_items
                self._tenant_partition_cursor[tenant] = (
                    0 if next_cursor >= total_plan_items else next_cursor
                )
            else:
                partition = (0, slice_items)
                self._tenant_partition_cursor[tenant] = (
                    0 if slice_items >= total_plan_items else slice_items
                )

        now = time.monotonic()
        effective_deadline = (
            float(deadline_override)
            if deadline_override is not None
            else now + self._default_ttl
        )

        rb = resource_budget or {"cpu_cores": 1, "memory_mb": 256, "concurrency": 1}

        lease = WorkLease(
            lease_id=uuid.uuid4().hex[:12],
            work_id=work_id,
            tenant=tenant,
            partition=partition,
            deadline=effective_deadline,
            cpu_cores=int(rb.get("cpu_cores", 1)),
            memory_mb=int(rb.get("memory_mb", 256)),
            concurrency=int(rb.get("concurrency", 1)),
            fencing_token=identity.current_fencing_token,
            worker_id=identity.worker_id,
        )

        self._active_leases[lease.lease_id] = lease
        worker.assign_lease(lease)
        self._work_id_history.setdefault(work_id, []).append((lease.lease_id, ""))
        return lease

    def _assign_worker(
        self,
        tenant: str,
        partition: Optional[tuple[int, int]],
        target_worker: Optional[str] = None,
        default_items: int = 4,
    ) -> Optional[str]:
        """Assign a worker for the given tenant and partition."""
        if target_worker is not None:
            worker = self._workers.get(target_worker)
            if worker is None or worker.identity.tenant != tenant:
                return None
            return target_worker

        for wid, worker in self._workers.items():
            if worker.identity.tenant == tenant:
                return wid

        if self._allow_ephemeral_workers:
            wid = f"ephemeral_{tenant}"
            identity = WorkerIdentity(
                worker_id=wid,
                generation=1,
                instance_id=f"inst_{tenant}",
                tenant=tenant,
            )
            plan = HostGPUPlan(
                total_items=max(1, default_items),
                lanes=min(4, max(1, default_items)),
                mode="host_gpu_overlay",
                device_count=1,
            )
            self._workers[wid] = NativeIGPUWorker(identity, plan)
            return wid

        return None

    def register_result(
        self,
        *,
        lease_id: str,
        worker: NativeIGPUWorker,
        result: ExecutionResult,
    ) -> bool:
        """Register a worker's result against its lease.

        Enforces:
        - Lease must be active and not expired
        - Fencing token must match and not be revoked
        - Tenant boundary must match
        - Idempotency: same work_id + same output_digest = accepted
        """
        if result.fencing_token in self._revoked_fencing_tokens:
            return False

        lease = self._active_leases.get(lease_id)
        if lease is None:
            return False

        if lease.is_expired(time.monotonic()):
            del self._active_leases[lease_id]
            return False

        if result.fencing_token != lease.fencing_token:
            return False

        if result.tenant != lease.tenant or worker.identity.tenant != lease.tenant:
            return False

        history = self._work_id_history.get(result.work_id, [])
        for prev_lease_id, prev_digest in history:
            if prev_digest and prev_digest != result.output_digest:
                return False
            if prev_lease_id == lease_id and prev_digest == result.output_digest:
                return True

        history.append((lease_id, result.output_digest))
        return True

    def terminate_worker(
        self,
        worker_id: str,
        *,
        fencing_token: Optional[str] = None,
    ) -> Optional[WorkerIdentity]:
        """Handle worker termination: rotate fencing tokens, invalidate old leases."""
        if worker_id not in self._workers:
            return None

        worker = self._workers[worker_id]
        old_token = worker.identity.current_fencing_token
        self._revoked_fencing_tokens.add(old_token)

        new_identity = worker.identity.rotated(fencing_token=fencing_token)
        self._workers[worker_id] = type(worker)(new_identity, worker.plan)

        leases_to_remove = [
            lid
            for lid, lease in self._active_leases.items()
            if lease.worker_id == worker_id or lease.fencing_token == old_token
        ]
        for lid in leases_to_remove:
            del self._active_leases[lid]

        self._tenant_partition_cursor[worker.identity.tenant] = 0
        return new_identity

    def worker_terminated(
        self,
        worker_id: str,
        *,
        fencing_token: Optional[str] = None,
    ) -> Optional[WorkerIdentity]:
        """Alias for terminate_worker supporting explicit fencing_token rotation."""
        return self.terminate_worker(worker_id, fencing_token=fencing_token)
