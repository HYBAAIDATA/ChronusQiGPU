"""Transactional SQLite persistence for single-node Chronus API deployments."""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from chronus.service.models import WorkloadResponse


class SQLiteWorkloadStore:
    """Persist workload lifecycle records across process restarts."""

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path or os.getenv(
            "CHRONUS_WORKLOAD_DB_PATH", "data/chronus-workloads.sqlite3"
        )
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS workloads (
                    workload_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    response_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS workloads_by_tenant "
                "ON workloads (tenant_id, workload_id)"
            )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10.0)
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def save(self, workload: WorkloadResponse) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workloads (workload_id, tenant_id, status, response_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(workload_id) DO UPDATE SET
                    tenant_id=excluded.tenant_id,
                    status=excluded.status,
                    response_json=excluded.response_json
                """,
                (
                    str(workload.workload_id),
                    workload.tenant_id,
                    (
                        workload.status.value
                        if hasattr(workload.status, "value")
                        else workload.status
                    ),
                    workload.model_dump_json(),
                ),
            )

    def get(self, workload_id: str) -> Optional[WorkloadResponse]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT response_json FROM workloads WHERE workload_id = ?",
                (workload_id,),
            ).fetchone()
        return WorkloadResponse.model_validate_json(row[0]) if row else None

    def list_for_tenant(
        self, tenant_id: str, offset: int, limit: int
    ) -> tuple[list[WorkloadResponse], int]:
        with self._connect() as connection:
            total = connection.execute(
                "SELECT COUNT(*) FROM workloads WHERE tenant_id = ?",
                (tenant_id,),
            ).fetchone()[0]
            rows = connection.execute(
                """
                SELECT response_json FROM workloads
                WHERE tenant_id = ?
                ORDER BY rowid DESC
                LIMIT ? OFFSET ?
                """,
                (tenant_id, limit, offset),
            ).fetchall()
        return [WorkloadResponse.model_validate_json(row[0]) for row in rows], total

    def counts(self) -> tuple[int, int]:
        with self._connect() as connection:
            total = connection.execute(
                "SELECT COUNT(*) FROM workloads"
            ).fetchone()[0]
            active = connection.execute(
                """
                SELECT COUNT(*) FROM workloads
                WHERE status IN ('SUBMITTED', 'QUEUED', 'PROVISIONING',
                                 'EXECUTING', 'RECOVERING')
                """
            ).fetchone()[0]
        return total, active

    def clear(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM workloads")
