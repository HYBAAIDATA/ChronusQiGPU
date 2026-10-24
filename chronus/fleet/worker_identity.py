"""Worker identity, generation tracking, fencing tokens, and bounded work leases for fleet qualification."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True, kw_only=True)
class WorkerIdentity:
    """Unique per-worker identity scoped to a tenant generation.

    Every worker gets an immutable identity that includes:
    - worker_id: unique within the fleet
    - generation: monotonically incremented on worker restart
    - instance_id: tenant or workload identifier
    - tenant: the authorizing tenant boundary
    - fencing_token: optional explicit token; defaults to deterministic worker+generation token
    """

    worker_id: str
    generation: int = 1
    instance_id: str = "default"
    tenant: str = "default"
    fencing_token: str = ""

    @property
    def current_fencing_token(self) -> str:
        """Return the active string fencing token for this worker generation."""
        if self.fencing_token:
            return str(self.fencing_token)
        return f"fence-{self.worker_id}-gen{self.generation}"

    def rotated(
        self,
        *,
        generation: Optional[int] = None,
        fencing_token: Optional[str] = None,
    ) -> WorkerIdentity:
        """Return a new identity with an incremented generation (e.g. after worker restart)."""
        gen = generation if generation is not None else self.generation + 1
        token = str(fencing_token) if fencing_token is not None else f"fence-{self.worker_id}-gen{gen}"
        return WorkerIdentity(
            worker_id=self.worker_id,
            generation=gen,
            instance_id=self.instance_id,
            tenant=self.tenant,
            fencing_token=token,
        )


@dataclass(frozen=True, kw_only=True)
class WorkLease:
    """Bounded, expiring work lease with partition, budget, and fencing token.

    A work lease grants a worker the right to execute a bounded piece of work.
    The lease expires at `deadline`, and the `fencing_token` changes on worker
    restart to prevent stale results from being committed.
    """

    lease_id: str
    work_id: str
    tenant: str
    partition: tuple[int, int]  # (start, end) item range
    deadline: float  # monotonic deadline timestamp
    cpu_cores: int = 1
    memory_mb: int = 256
    concurrency: int = 1
    fencing_token: str = field(repr=False, default_factory=lambda: "initial")
    worker_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "fencing_token", str(self.fencing_token))
        p0, p1 = int(self.partition[0]), int(self.partition[1])
        if p0 < 0 or p1 < p0:
            raise ValueError(f"invalid partition range: {self.partition}")
        object.__setattr__(self, "partition", (p0, p1))

    def is_expired(self, now: float) -> bool:
        return now > self.deadline

    def rotated(self, *, new_token: Optional[str] = None, **lease_overrides: object) -> WorkLease:
        """Return a new lease with rotated fencing token and/or overridden fields."""
        token = str(new_token) if new_token is not None else f"{self.fencing_token}.rotated"
        merged = {**self.__dict__, "fencing_token": token}
        merged.update(lease_overrides)
        return WorkLease(**{k: v for k, v in merged.items() if k in WorkLease.__dataclass_fields__})  # type: ignore[arg-type]
