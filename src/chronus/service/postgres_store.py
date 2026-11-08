"""PostgreSQL persistence store for enterprise-grade, horizontally scalable Chronus deployments.

Implements WorkloadStoreInterface using SQLAlchemy AsyncIO and asyncpg with:
- Connection pooling (pool_size, max_overflow, pool_pre_ping)
- Transaction isolation levels (REPEATABLE READ / READ COMMITTED)
- Automatic retry logic for deadlocks and serialization failures
- Schema management for workloads, execution records, receipts, and tenant usage
"""

import asyncio
import functools
import logging
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    delete,
    func,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from chronus.service.models import WorkloadResponse
from chronus.service.store_interface import WorkloadStoreInterface

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Metadata and Table Declarations
metadata = MetaData()

workloads_table = Table(
    "workloads",
    metadata,
    Column("workload_id", String(64), primary_key=True),
    Column("tenant_id", String(128), nullable=False, index=True),
    Column("status", String(32), nullable=False, index=True),
    Column("response_json", Text, nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    ),
    Column(
        "updated_at",
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    ),
)

execution_records_table = Table(
    "execution_records",
    metadata,
    Column("record_id", String(64), primary_key=True),
    Column("workload_id", String(64), nullable=False, index=True),
    Column("backend", String(64), nullable=False),
    Column("execution_mode", String(64), nullable=False),
    Column("duration_ms", Float, nullable=False),
    Column("result_json", Text, nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    ),
)

receipts_table = Table(
    "receipts",
    metadata,
    Column("receipt_id", String(64), primary_key=True),
    Column("workload_id", String(64), nullable=False, index=True),
    Column("tenant_id", String(128), nullable=False, index=True),
    Column("signature", Text, nullable=False),
    Column("algorithm", String(32), nullable=False),
    Column("verified", Integer, default=1),
    Column("receipt_json", Text, nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    ),
)

tenant_usage_table = Table(
    "tenant_usage_metrics",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("tenant_id", String(128), nullable=False, index=True),
    Column("ccu_consumed", Float, default=0.0),
    Column("requests_total", Integer, default=0),
    Column("period_start", DateTime(timezone=True), nullable=False),
    Column("period_end", DateTime(timezone=True), nullable=False),
)

ciaas_tenants_table = Table(
    "ciaas_tenants",
    metadata,
    Column("tenant_id", String(128), primary_key=True),
    Column("contract_id", String(128), nullable=False, index=True),
    Column("company_name", String(256), nullable=False),
    Column("admin_email", String(256), nullable=False),
    Column("assigned_cce_id", String(128), nullable=False, unique=True),
    Column("schema_name", String(128), nullable=False),
    Column("enduring_addendum_accepted", Boolean, nullable=False, default=True),
    Column("active_warps", Integer, nullable=False, default=32),
    Column("max_authorized_warps", Integer, nullable=False, default=1024),
    Column("data_at_rest_gb", Integer, nullable=False, default=10000),
    Column("data_in_motion_gb", Integer, nullable=False, default=5000),
    Column("kms_provider", String(64), nullable=False),
    Column("kms_key_arn", Text, nullable=False),
    Column("profile_json", Text, nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    ),
    Column(
        "updated_at",
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    ),
)

ciaas_capacity_ledger_table = Table(
    "ciaas_capacity_ledger",
    metadata,
    Column("event_id", String(64), primary_key=True),
    Column("tenant_id", String(128), nullable=False, index=True),
    Column("previous_warps", Integer, nullable=False),
    Column("new_active_warps", Integer, nullable=False),
    Column("previous_storage_gb", Integer, nullable=False),
    Column("new_storage_gb", Integer, nullable=False),
    Column("reason", String(256), nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    ),
)

# Indexes
Index(
    "ix_workloads_tenant_status", workloads_table.c.tenant_id, workloads_table.c.status
)
Index("ix_execution_records_workload", execution_records_table.c.workload_id)
Index(
    "ix_receipts_tenant_workload",
    receipts_table.c.tenant_id,
    receipts_table.c.workload_id,
)


def sanitize_tenant_schema_name(tenant_id: str) -> str:
    """Derive a strictly validated PostgreSQL identifier for per-tenant schema isolation."""
    cleaned = "".join(
        ch if (ch.isalnum() or ch == "_") else "_" for ch in tenant_id.strip().lower()
    ).strip("_")
    if not cleaned:
        raise ValueError("tenant_id cannot derive a valid PostgreSQL schema identifier")
    if not cleaned.startswith("tenant_"):
        cleaned = f"tenant_{cleaned}"
    return cleaned[:63]


def with_retry(
    max_retries: int = 3,
    initial_backoff: float = 0.05,
    backoff_factor: float = 2.0,
) -> Callable:
    """Decorator retrying database operations on deadlock or serialization errors."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            backoff = initial_backoff
            last_err = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except (DBAPIError, OperationalError, Exception) as exc:
                    err_msg = str(exc).lower()
                    is_transient = any(
                        token in err_msg
                        for token in (
                            "deadlock",
                            "serialization",
                            "could not serialize",
                            "lock conflict",
                        )
                    )
                    if is_transient and attempt < max_retries - 1:
                        logger.warning(
                            "Transient DB error (attempt %d/%d): %s. Retrying in %.3fs...",
                            attempt + 1,
                            max_retries,
                            exc,
                            backoff,
                        )
                        await asyncio.sleep(backoff)
                        backoff *= backoff_factor
                        last_err = exc
                    else:
                        raise
            if last_err:
                raise last_err

        return async_wrapper

    return decorator


class PostgresWorkloadStore(WorkloadStoreInterface):
    """PostgreSQL Workload Store with connection pooling, isolation levels, and retry logic."""

    def __init__(
        self,
        dsn: Optional[str] = None,
        pool_size: int = 10,
        max_overflow: int = 20,
        isolation_level: str = "REPEATABLE READ",
    ) -> None:
        raw_dsn = dsn or os.getenv(
            "CHRONUS_DATABASE_URL",
            "postgresql+asyncpg://postgres:postgres@localhost:5432/chronus",
        )
        # Ensure asyncpg driver prefix for SQLAlchemy async engine
        if raw_dsn.startswith("postgresql://"):
            self.dsn = raw_dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif raw_dsn.startswith("postgres://"):
            self.dsn = raw_dsn.replace("postgres://", "postgresql+asyncpg://", 1)
        else:
            self.dsn = raw_dsn

        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.isolation_level = isolation_level
        self.engine: AsyncEngine = create_async_engine(
            self.dsn,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=30.0,
            pool_pre_ping=True,
            isolation_level=self.isolation_level,
        )
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        self._initialized = False
        self._tenant_schemas: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def build_tenant_isolation_descriptor(
        cls,
        tenant_id: str,
        pool_size: int = 10,
        isolation_level: str = "REPEATABLE READ",
    ) -> Dict[str, Any]:
        """Construct dedicated PostgreSQL tenant schema & REPEATABLE READ pool descriptor."""
        schema_name = sanitize_tenant_schema_name(tenant_id)
        return {
            "tenant_id": tenant_id,
            "schema_name": schema_name,
            "pool_size": pool_size,
            "isolation_level": isolation_level,
            "status": "PROVISIONED",
        }

    @with_retry()
    async def async_provision_tenant_schema(self, tenant_id: str) -> Dict[str, Any]:
        """Create a dedicated tenant schema under REPEATABLE READ isolation in PostgreSQL."""
        await self.init_db()
        descriptor = self.build_tenant_isolation_descriptor(
            tenant_id=tenant_id,
            pool_size=self.pool_size,
            isolation_level=self.isolation_level,
        )
        schema_name = descriptor["schema_name"]
        async with self.engine.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
        self._tenant_schemas[tenant_id] = descriptor
        return descriptor

    async def init_db(self) -> None:
        """Create tables if they do not exist."""
        if not self._initialized:
            async with self.engine.begin() as conn:
                await conn.run_sync(metadata.create_all)
            self._initialized = True

    def _run_sync(self, coro: Any) -> Any:
        """Helper to run async coroutines in synchronous methods."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # If already inside an running event loop, schedule via new task or thread
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()
        return asyncio.run(coro)

    # -------------------------------------------------------------------------
    # Asynchronous Interface Implementation
    # -------------------------------------------------------------------------

    @with_retry()
    async def async_save(self, workload: WorkloadResponse) -> None:
        """Persist or upsert workload record."""
        await self.init_db()
        status_val = (
            workload.status.value
            if hasattr(workload.status, "value")
            else str(workload.status)
        )
        payload_json = workload.model_dump_json()

        async with self.session_factory() as session:
            async with session.begin():
                stmt = pg_insert(workloads_table).values(
                    workload_id=str(workload.workload_id),
                    tenant_id=workload.tenant_id,
                    status=status_val,
                    response_json=payload_json,
                    updated_at=datetime.now(timezone.utc),
                )
                upsert_stmt = stmt.on_conflict_do_update(
                    index_elements=[workloads_table.c.workload_id],
                    set_={
                        "tenant_id": stmt.excluded.tenant_id,
                        "status": stmt.excluded.status,
                        "response_json": stmt.excluded.response_json,
                        "updated_at": stmt.excluded.updated_at,
                    },
                )
                await session.execute(upsert_stmt)

    @with_retry()
    async def async_get(self, workload_id: str) -> Optional[WorkloadResponse]:
        """Fetch workload record by ID."""
        await self.init_db()
        async with self.session_factory() as session:
            stmt = select(workloads_table.c.response_json).where(
                workloads_table.c.workload_id == workload_id
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row:
                return WorkloadResponse.model_validate_json(row)
            return None

    @with_retry()
    async def async_list_for_tenant(
        self, tenant_id: str, offset: int, limit: int
    ) -> Tuple[List[WorkloadResponse], int]:
        """Paginated list of workloads for a given tenant."""
        await self.init_db()
        async with self.session_factory() as session:
            # Count total
            count_stmt = (
                select(func.count())
                .select_from(workloads_table)
                .where(workloads_table.c.tenant_id == tenant_id)
            )
            count_res = await session.execute(count_stmt)
            total = count_res.scalar() or 0

            # Fetch rows ordered by created_at desc
            stmt = (
                select(workloads_table.c.response_json)
                .where(workloads_table.c.tenant_id == tenant_id)
                .order_by(workloads_table.c.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
            rows = (await session.execute(stmt)).scalars().all()
            records = [WorkloadResponse.model_validate_json(r) for r in rows]
            return records, total

    @with_retry()
    async def async_counts(self) -> Tuple[int, int]:
        """Return (total_workloads, active_workloads)."""
        await self.init_db()
        async with self.session_factory() as session:
            total_stmt = select(func.count()).select_from(workloads_table)
            total = (await session.execute(total_stmt)).scalar() or 0

            active_stmt = (
                select(func.count())
                .select_from(workloads_table)
                .where(
                    workloads_table.c.status.in_(
                        [
                            "SUBMITTED",
                            "QUEUED",
                            "PROVISIONING",
                            "EXECUTING",
                            "RECOVERING",
                        ]
                    )
                )
            )
            active = (await session.execute(active_stmt)).scalar() or 0
            return total, active

    @with_retry()
    async def async_clear(self) -> None:
        """Clear all records from workloads table."""
        await self.init_db()
        async with self.session_factory() as session:
            async with session.begin():
                await session.execute(delete(workloads_table))

    # Record and Receipt helpers for multi-replica auditing
    @with_retry()
    async def record_execution(
        self,
        record_id: str,
        workload_id: str,
        backend: str,
        execution_mode: str,
        duration_ms: float,
        result_json: str,
    ) -> None:
        await self.init_db()
        async with self.session_factory() as session:
            async with session.begin():
                stmt = pg_insert(execution_records_table).values(
                    record_id=record_id,
                    workload_id=workload_id,
                    backend=backend,
                    execution_mode=execution_mode,
                    duration_ms=duration_ms,
                    result_json=result_json,
                )
                await session.execute(stmt)

    @with_retry()
    async def record_receipt(
        self,
        receipt_id: str,
        workload_id: str,
        tenant_id: str,
        signature: str,
        algorithm: str,
        receipt_json: str,
        verified: bool = True,
    ) -> None:
        await self.init_db()
        async with self.session_factory() as session:
            async with session.begin():
                stmt = pg_insert(receipts_table).values(
                    receipt_id=receipt_id,
                    workload_id=workload_id,
                    tenant_id=tenant_id,
                    signature=signature,
                    algorithm=algorithm,
                    receipt_json=receipt_json,
                    verified=1 if verified else 0,
                )
                await session.execute(stmt)

    # -------------------------------------------------------------------------
    # Synchronous Fallbacks for WorkloadStoreInterface compatibility
    # -------------------------------------------------------------------------

    def save(self, workload: WorkloadResponse) -> None:
        self._run_sync(self.async_save(workload))

    def get(self, workload_id: str) -> Optional[WorkloadResponse]:
        return self._run_sync(self.async_get(workload_id))

    def list_for_tenant(
        self, tenant_id: str, offset: int, limit: int
    ) -> Tuple[List[WorkloadResponse], int]:
        return self._run_sync(self.async_list_for_tenant(tenant_id, offset, limit))

    def counts(self) -> Tuple[int, int]:
        return self._run_sync(self.async_counts())

    def clear(self) -> None:
        self._run_sync(self.async_clear())
