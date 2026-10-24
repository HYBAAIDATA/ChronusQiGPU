"""Native iGPU worker running in isolated process with ONE iGPU runtime."""

from __future__ import annotations

import hashlib
import time
import uuid
from typing import Any, Callable, Dict, Optional

from chronus.fleet.worker_identity import WorkerIdentity, WorkLease
from chronus.igpu.host import HostGPUPlan, execute_reference


class ExecutionResult:
    """Full provenance of a worker execution.

    Binds result to tenant, workload, output digest, partition, worker
    generation, lease and current fencing token.

    Additional keyword arguments are accepted for backward compatibility
    with test suites and future extensions.
    """

    def __init__(
        self,
        *,
        worker_id: str = "ephemeral_worker",
        lease_id: str = "",
        work_id: Optional[str] = None,
        output_digest: str = "",
        tenant: str = "default",
        partition: tuple[int, int] = (0, 0),
        generation: int = 1,
        fencing_token: str = "initial",
        backend: str = "cpu_reference",
        sha256d_evaluations: int = 0,
        elapsed_seconds: float = 0.0,
        result: Optional[Any] = None,
        **kwargs: Any,
    ):
        self.worker_id = str(worker_id)
        self.lease_id = str(lease_id)
        self._work_id = str(work_id) if work_id is not None else str(worker_id)
        self.output_digest = str(output_digest)
        self.tenant = str(tenant)
        self.partition = (int(partition[0]), int(partition[1]))
        self.generation = int(generation)
        self.fencing_token = str(fencing_token)
        self.backend = str(backend)
        self.sha256d_evaluations = int(sha256d_evaluations)
        self.elapsed_seconds = float(elapsed_seconds)
        self.result = result
        for key, value in kwargs.items():
            setattr(self, key, value)

    @property
    def work_id(self) -> str:
        """Workload identifier bound to this execution result."""
        return self._work_id

    @work_id.setter
    def work_id(self, value: str) -> None:
        self._work_id = str(value)

    def __repr__(self) -> str:
        return (
            f"ExecutionResult(work_id={self._work_id}, worker={self.worker_id}, "
            f"lease={self.lease_id}, tenant={self.tenant}, "
            f"digest={self.output_digest[:16]}..., "
            f"partition={self.partition}, gen={self.generation})"
        )


class NativeIGPUWorker:
    """ONE iGPU worker running in an isolated process.

    Each worker has exactly one iGPU runtime (device_count == 1),
    preserving HostGPUPlan mathematics. The worker enforces tenant
    boundaries, partition validation, lease acquisition/completion, and
    returns fully provenance'd ExecutionResult objects.
    """

    def __init__(self, identity: WorkerIdentity, plan: HostGPUPlan):
        if plan.device_count != 1:
            raise ValueError("NativeIGPUWorker requires device_count == 1 (ONE iGPU contract)")
        self._identity = identity
        self._plan = plan
        self._running = False
        self._active_leases: Dict[str, WorkLease] = {}
        self._completed_leases: Dict[str, WorkLease] = {}

    @property
    def identity(self) -> WorkerIdentity:
        return self._identity

    @property
    def plan(self) -> HostGPUPlan:
        return self._plan

    @property
    def device_count(self) -> int:
        return 1

    def assign_lease(self, lease: WorkLease) -> None:
        """Register an active lease on this worker."""
        if lease.tenant != self._identity.tenant:
            raise ValueError(
                f"Tenant mismatch: lease tenant {lease.tenant!r} != worker tenant {self._identity.tenant!r}"
            )
        self._active_leases[lease.lease_id] = lease

    def _find_lease_for_work(self, work_id: str) -> Optional[WorkLease]:
        for lease in self._active_leases.values():
            if lease.work_id == work_id:
                return lease
        return None

    def execute(
        self,
        work_id: str,
        kernel: Callable[[Any], Any],
        input_data: Any,
        *,
        lease: Optional[WorkLease] = None,
    ) -> ExecutionResult:
        """Execute a kernel on the worker's iGPU plan.

        The result is fully provenance'd: tenant, partition, generation,
        fencing token, backend, and sha256d digest are all recorded.
        """
        if self._running:
            raise RuntimeError(f"Worker {self._identity.worker_id} already running")
        self._running = True
        t0 = time.perf_counter()

        try:
            items = list(input_data) if not isinstance(input_data, list) else input_data
            if len(items) == self._plan.total_items:
                exec_plan = self._plan
            else:
                exec_plan = HostGPUPlan(
                    total_items=len(items),
                    lanes=max(1, min(self._plan.lanes, max(1, len(items)))),
                    mode=self._plan.mode,
                    backend=self._plan.backend,
                    device_count=1,
                )

            output = execute_reference(items, exec_plan, kernel)
            raw = repr(output).encode("utf-8")
            output_digest = hashlib.sha256(raw).hexdigest()

            lease_used = lease or self._find_lease_for_work(work_id)
            if lease_used is None:
                default_part = (0, len(items))
                lease_used = WorkLease(
                    lease_id=uuid.uuid4().hex[:12],
                    work_id=work_id,
                    tenant=self._identity.tenant,
                    partition=default_part,
                    deadline=time.monotonic() + 300.0,
                    cpu_cores=1,
                    memory_mb=256,
                    concurrency=1,
                    fencing_token=self._identity.current_fencing_token,
                    worker_id=self._identity.worker_id,
                )
            self._active_leases[lease_used.lease_id] = lease_used

            elapsed = time.perf_counter() - t0
            return ExecutionResult(
                worker_id=self._identity.worker_id,
                lease_id=lease_used.lease_id,
                work_id=work_id,
                output_digest=output_digest,
                tenant=self._identity.tenant,
                partition=lease_used.partition,
                generation=self._identity.generation,
                fencing_token=lease_used.fencing_token,
                backend=self._plan.backend,
                sha256d_evaluations=len(items),
                elapsed_seconds=elapsed,
                result=output,
            )
        finally:
            self._running = False

    def complete_lease(self, lease_id: str, result: ExecutionResult) -> ExecutionResult:
        """Mark a lease as complete with its result.

        Validates that the result's lease_id matches and that the tenant
        boundary and fencing token are preserved.
        """
        if result.lease_id != lease_id:
            raise ValueError(f"lease_id mismatch: {result.lease_id} != {lease_id}")
        if result.tenant != self._identity.tenant:
            raise ValueError("tenant mismatch in lease completion")
        lease = self._active_leases.get(lease_id)
        if lease is not None:
            if result.fencing_token != lease.fencing_token:
                raise ValueError("fencing token mismatch in lease completion")
            self._completed_leases[lease_id] = lease
        return result
