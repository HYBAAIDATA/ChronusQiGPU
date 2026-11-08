"""Abstract interface for Chronus Workload Store persistence.

Supports switching between local development (SQLiteWorkloadStore)
and horizontal enterprise production (PostgresWorkloadStore).
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple, List

from chronus.service.models import WorkloadResponse


class WorkloadStoreInterface(ABC):
    """Abstract persistence interface for workload records across process restarts."""

    @abstractmethod
    def save(self, workload: WorkloadResponse) -> None:
        """Persist or update a workload record."""
        ...

    @abstractmethod
    def get(self, workload_id: str) -> Optional[WorkloadResponse]:
        """Retrieve a workload record by workload_id."""
        ...

    @abstractmethod
    def list_for_tenant(
        self, tenant_id: str, offset: int, limit: int
    ) -> Tuple[List[WorkloadResponse], int]:
        """List paginated workloads for a tenant, returning (records, total_count)."""
        ...

    @abstractmethod
    def counts(self) -> Tuple[int, int]:
        """Return (total_workloads, active_workloads)."""
        ...

    @abstractmethod
    def clear(self) -> None:
        """Clear all workload records."""
        ...

    async def async_save(self, workload: WorkloadResponse) -> None:
        """Async variant of save (defaults to calling sync save)."""
        self.save(workload)

    async def async_get(self, workload_id: str) -> Optional[WorkloadResponse]:
        """Async variant of get (defaults to calling sync get)."""
        return self.get(workload_id)

    async def async_list_for_tenant(
        self, tenant_id: str, offset: int, limit: int
    ) -> Tuple[List[WorkloadResponse], int]:
        """Async variant of list_for_tenant."""
        return self.list_for_tenant(tenant_id, offset, limit)

    async def async_counts(self) -> Tuple[int, int]:
        """Async variant of counts."""
        return self.counts()

    async def async_clear(self) -> None:
        """Async variant of clear."""
        self.clear()
