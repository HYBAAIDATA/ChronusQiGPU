"""Unit and integration tests for Chronus persistence layer.

Tests:
- WorkloadStoreInterface contract
- SQLiteWorkloadStore sync and async operations
- PostgresWorkloadStore configuration, DSN normalization, and table schemas
- with_retry deadlock and serialization error retry logic
"""

import asyncio
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from sqlalchemy.exc import DBAPIError, OperationalError

from uuid import uuid4

from chronus.service.models import Priority, WorkloadResponse, WorkloadStatus
from chronus.service.postgres_store import (
    PostgresWorkloadStore,
    execution_records_table,
    receipts_table,
    tenant_usage_table,
    with_retry,
    workloads_table,
)
from chronus.service.store_interface import WorkloadStoreInterface
from chronus.service.workload_store import SQLiteWorkloadStore, get_workload_store


class TestWorkloadStoreInterface(unittest.TestCase):
    """Test WorkloadStoreInterface abstract contract."""

    def test_sqlite_implements_interface(self):
        """Verify SQLiteWorkloadStore inherits from WorkloadStoreInterface."""
        store = SQLiteWorkloadStore(":memory:")
        self.assertIsInstance(store, WorkloadStoreInterface)

    def test_postgres_implements_interface(self):
        """Verify PostgresWorkloadStore inherits from WorkloadStoreInterface."""
        store = PostgresWorkloadStore("postgresql://localhost:5432/chronus")
        self.assertIsInstance(store, WorkloadStoreInterface)

    def test_factory_returns_interface(self):
        """Test get_workload_store factory returns WorkloadStoreInterface."""
        store = get_workload_store()
        self.assertIsInstance(store, WorkloadStoreInterface)


class TestRetryDecorator(unittest.TestCase):
    """Test the with_retry database transaction retry decorator."""

    def test_retry_success_on_first_try(self):
        """Function succeeding immediately returns expected result."""
        call_count = 0

        @with_retry(max_retries=3, initial_backoff=0.001)
        async def dummy_op():
            nonlocal call_count
            call_count += 1
            return "SUCCESS"

        result = asyncio.run(dummy_op())
        self.assertEqual(result, "SUCCESS")
        self.assertEqual(call_count, 1)

    def test_retry_on_deadlock(self):
        """Function encountering deadlock retries and eventually succeeds."""
        call_count = 0

        @with_retry(max_retries=3, initial_backoff=0.001)
        async def transient_op():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise OperationalError("deadlock detected", params=None, orig=Exception("deadlock"))
            return "RECOVERED"

        result = asyncio.run(transient_op())
        self.assertEqual(result, "RECOVERED")
        self.assertEqual(call_count, 3)

    def test_retry_exhausted_raises(self):
        """Function continuously deadlocking exhausts retries and raises."""
        call_count = 0

        @with_retry(max_retries=2, initial_backoff=0.001)
        async def failing_op():
            nonlocal call_count
            call_count += 1
            raise DBAPIError("could not serialize access due to concurrent update", params=None, orig=Exception("serialization"))

        with self.assertRaises(DBAPIError):
            asyncio.run(failing_op())
        self.assertEqual(call_count, 2)


class TestPostgresStoreConfiguration(unittest.TestCase):
    """Test PostgresWorkloadStore connection configuration and schemas."""

    def test_dsn_normalization(self):
        """Verify postgresql:// prefix is normalized to postgresql+asyncpg://."""
        store1 = PostgresWorkloadStore("postgresql://usr:pwd@host:5432/db")
        self.assertEqual(store1.dsn, "postgresql+asyncpg://usr:pwd@host:5432/db")

        store2 = PostgresWorkloadStore("postgres://usr:pwd@host:5432/db")
        self.assertEqual(store2.dsn, "postgresql+asyncpg://usr:pwd@host:5432/db")

        store3 = PostgresWorkloadStore("postgresql+asyncpg://usr:pwd@host:5432/db")
        self.assertEqual(store3.dsn, "postgresql+asyncpg://usr:pwd@host:5432/db")

    def test_table_metadata_definitions(self):
        """Verify table schema definitions have required primary keys and columns."""
        self.assertIn("workload_id", workloads_table.c)
        self.assertIn("tenant_id", workloads_table.c)
        self.assertIn("status", workloads_table.c)
        self.assertIn("response_json", workloads_table.c)

        self.assertIn("record_id", execution_records_table.c)
        self.assertIn("workload_id", execution_records_table.c)
        self.assertIn("backend", execution_records_table.c)

        self.assertIn("receipt_id", receipts_table.c)
        self.assertIn("workload_id", receipts_table.c)
        self.assertIn("signature", receipts_table.c)

        self.assertIn("tenant_id", tenant_usage_table.c)
        self.assertIn("ccu_consumed", tenant_usage_table.c)


class TestSQLiteWorkloadStore(unittest.TestCase):
    """Test SQLiteWorkloadStore sync and async operations."""

    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
        self.temp_file.close()
        self.store = SQLiteWorkloadStore(self.temp_file.name)

    def tearDown(self):
        try:
            os.unlink(self.temp_file.name)
        except OSError:
            pass

    def test_save_get_and_count(self):
        """Test persisting, retrieving, counting, and clearing workloads."""
        w_id = uuid4()
        resp = WorkloadResponse(
            workload_id=w_id,
            status=WorkloadStatus.SUBMITTED,
            workload_type="EXACT_Q5_ALGEBRAIC",
            representation_mode="EXACT_Q5_RATIONAL",
            priority=Priority.HIGH,
            region="us-east-1",
            tenant_id="tenant-alpha",
        )
        self.store.save(resp)

        retrieved = self.store.get(str(w_id))
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.workload_id, w_id)
        self.assertEqual(retrieved.tenant_id, "tenant-alpha")

        total, active = self.store.counts()
        self.assertEqual(total, 1)
        self.assertEqual(active, 1)

        # Update status to COMPLETED
        resp_completed = WorkloadResponse(
            workload_id=w_id,
            status=WorkloadStatus.COMPLETED,
            workload_type="EXACT_Q5_ALGEBRAIC",
            representation_mode="EXACT_Q5_RATIONAL",
            priority=Priority.HIGH,
            region="us-east-1",
            tenant_id="tenant-alpha",
        )
        self.store.save(resp_completed)
        total, active = self.store.counts()
        self.assertEqual(total, 1)
        self.assertEqual(active, 0)

        # Pagination
        records, count = self.store.list_for_tenant("tenant-alpha", offset=0, limit=10)
        self.assertEqual(count, 1)
        self.assertEqual(len(records), 1)

        # Clear
        self.store.clear()
        total, active = self.store.counts()
        self.assertEqual(total, 0)

    def test_async_wrapper_methods(self):
        """Test async interface wrappers of SQLiteWorkloadStore."""
        async def run_async():
            w_id = uuid4()
            resp = WorkloadResponse(
                workload_id=w_id,
                status=WorkloadStatus.SUBMITTED,
                workload_type="EXACT_Q5_ALGEBRAIC",
                representation_mode="EXACT_Q5_RATIONAL",
                priority=Priority.HIGH,
                region="us-east-1",
                tenant_id="tenant-beta",
            )
            await self.store.async_save(resp)
            retrieved = await self.store.async_get(str(w_id))
            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved.tenant_id, "tenant-beta")

            total, active = await self.store.async_counts()
            self.assertEqual(total, 1)

            records, count = await self.store.async_list_for_tenant("tenant-beta", 0, 5)
            self.assertEqual(count, 1)
            self.assertEqual(records[0].workload_id, w_id)

        asyncio.run(run_async())


if __name__ == "__main__":
    unittest.main()
