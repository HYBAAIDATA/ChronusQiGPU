"""Unit tests for the Thesus database configuration and ORM layer.

No live PostgreSQL is required: connection behavior is tested with mocks and
the async entry points are driven with ``asyncio.run``.
"""

import asyncio
from datetime import datetime, timezone
from unittest import mock
from uuid import uuid4

import pytest

from chronus.database.config import DatabaseConfig, MigrationConfig
from chronus.database.connection import ThesusDatabase
from chronus.database.models import (
    ConfigRecord,
    NodeRecord,
    ReceiptRecord,
    WorkloadRecord,
)


# ---------------------------------------------------------------------------
# DatabaseConfig
# ---------------------------------------------------------------------------


def test_database_config_defaults():
    cfg = DatabaseConfig()
    assert cfg.host == "localhost"
    assert cfg.port == 5432
    assert cfg.database == "chronus_quantum"
    assert cfg.pool_size == 20
    assert cfg.max_overflow == 10
    assert cfg.pool_pre_ping is True
    assert cfg.max_retries == 3


def test_database_config_from_env(monkeypatch):
    monkeypatch.setenv("THESISUS_DB_HOST", "db.internal")
    monkeypatch.setenv("THESISUS_DB_PORT", "6543")
    monkeypatch.setenv("THESISUS_DB_DATABASE", "chronus_test")
    monkeypatch.setenv("THESISUS_POOL_SIZE", "7")
    cfg = DatabaseConfig.from_env()
    assert cfg.host == "db.internal"
    assert cfg.port == 6543
    assert cfg.database == "chronus_test"
    assert cfg.pool_size == 7


def test_database_config_from_env_defaults(monkeypatch):
    for var in (
        "THESISUS_DB_HOST",
        "THESISUS_DB_PORT",
        "THESISUS_DB_DATABASE",
        "THESISUS_POOL_SIZE",
    ):
        monkeypatch.delenv(var, raising=False)
    cfg = DatabaseConfig.from_env()
    assert cfg.host == "localhost"
    assert cfg.port == 5432


def test_database_config_rejects_bad_port(monkeypatch):
    monkeypatch.setenv("THESISUS_DB_PORT", "not-a-number")
    with pytest.raises(ValueError):
        DatabaseConfig.from_env()


def test_migration_config_defaults():
    cfg = MigrationConfig()
    assert cfg.auto_migrate is True
    assert cfg.log_migrations is True
    assert "migrations" in cfg.migrations_dir


# ---------------------------------------------------------------------------
# ThesusDatabase
# ---------------------------------------------------------------------------


def test_build_url_includes_ssl_mode():
    db = ThesusDatabase(DatabaseConfig(ssl_mode="require"))
    url = db.build_url()
    assert url.startswith("postgresql+asyncpg://")
    assert "sslmode=require" in url
    assert ":5432/" in url


def test_build_url_without_ssl_mode():
    db = ThesusDatabase(DatabaseConfig(ssl_mode=""))
    assert "sslmode" not in db.build_url()


def test_is_connected_before_connect():
    db = ThesusDatabase(DatabaseConfig())
    assert db.is_connected is False


def test_health_check_disconnected():
    db = ThesusDatabase(DatabaseConfig())
    result = asyncio.run(db.health_check())
    assert result["status"] == "disconnected"
    assert result["latency_ms"] == 0


def test_disconnect_without_engine_is_noop():
    db = ThesusDatabase(DatabaseConfig())
    asyncio.run(db.disconnect())
    assert db.is_connected is False


def test_connect_retries_then_raises(monkeypatch):
    cfg = DatabaseConfig(max_retries=2, retry_delay=0.0)
    db = ThesusDatabase(cfg)
    calls = []

    def _boom(*args, **kwargs):
        calls.append(1)
        raise RuntimeError("connection refused")

    monkeypatch.setattr(
        "chronus.database.connection.create_async_engine", _boom
    )
    with pytest.raises(RuntimeError, match="connection refused"):
        asyncio.run(db.connect())
    assert len(calls) == 2  # exactly max_retries attempts
    assert db.is_connected is False


def test_connect_success_sets_session_factory(monkeypatch):
    db = ThesusDatabase(DatabaseConfig())
    fake_engine = mock.MagicMock()
    monkeypatch.setattr(
        "chronus.database.connection.create_async_engine",
        lambda *a, **k: fake_engine,
    )
    asyncio.run(db.connect())
    assert db.is_connected is True
    assert db._session_factory is not None
    # Second connect is a no-op
    asyncio.run(db.connect())


# ---------------------------------------------------------------------------
# ORM model to_dict serialization
# ---------------------------------------------------------------------------


def test_workload_record_to_dict():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    record = WorkloadRecord(
        id=uuid4(),
        payload_hash="ab" * 32,
        payload_bytes="cHJveA==",
        workload_type="grover",
        representation_mode="finite_field",
        priority="HIGH",
        tenant_id="tenant-1",
        region="us-east",
        status="COMPLETED",
        ccu_cost=3.5,
        result={"answer": 42},
        verification_receipt="cd" * 32,
        submitted_at=now,
        started_at=now,
        completed_at=now,
        error_message=None,
        metadata={"k": "v"},
    )
    data = record.to_dict()
    assert data["payload_hash"] == "ab" * 32
    assert data["status"] == "COMPLETED"
    assert data["submitted_at"] == now.isoformat()
    assert data["result"] == {"answer": 42}
    assert data["error_message"] is None


def test_workload_record_to_dict_optional_fields_none():
    record = WorkloadRecord(
        id=uuid4(),
        payload_hash="0" * 64,
        payload_bytes="eA==",
        workload_type="t",
        representation_mode="m",
        priority="LOW",
        tenant_id="t",
        region="r",
        status="QUEUED",
        submitted_at=None,
    )
    data = record.to_dict()
    assert data["submitted_at"] is None
    assert data["started_at"] is None
    assert data["completed_at"] is None


def test_node_record_to_dict():
    now = datetime(2026, 2, 2, tzinfo=timezone.utc)
    record = NodeRecord(
        id=uuid4(),
        hostname="node-1.local",
        region="eu-west",
        capacity=64,
        status="ACTIVE",
        last_heartbeat=now,
        workloads_assigned=3,
        metadata=None,
    )
    data = record.to_dict()
    assert data["hostname"] == "node-1.local"
    assert data["last_heartbeat"] == now.isoformat()
    assert data["workloads_assigned"] == 3


def test_config_record_to_dict():
    now = datetime(2026, 3, 3, tzinfo=timezone.utc)
    record = ConfigRecord(id=uuid4(), key="feature.x", value={"on": True}, updated_at=now)
    data = record.to_dict()
    assert data["key"] == "feature.x"
    assert data["value"] == {"on": True}


def test_receipt_record_to_dict():
    now = datetime(2026, 4, 4, tzinfo=timezone.utc)
    record = ReceiptRecord(
        id=uuid4(),
        hash_value="ef" * 32,
        ml_dsa_signature="sig",
        ed25519_signature="edsig",
        timestamp=now,
        latency_ms=1.25,
        validity=True,
        metadata=None,
    )
    data = record.to_dict()
    assert data["hash_value"] == "ef" * 32
    assert data["validity"] is True
    assert data["latency_ms"] == 1.25


# ---------------------------------------------------------------------------
# Migration runner
# ---------------------------------------------------------------------------


class _FakeConn:
    async def run_sync(self, fn):
        fn(None)

    async def exec_driver_sql(self, sql):
        class _Result:
            def fetchall(self):
                return [("workloads",), ("nodes",)]

        return _Result()


class _FakeBegin:
    async def __aenter__(self):
        return _FakeConn()

    async def __aexit__(self, *args):
        return False


class _FakeEngine:
    def begin(self):
        return _FakeBegin()


def test_run_migrations_without_alembic_succeeds(monkeypatch):
    from chronus.database import migrate

    async def _fake_create(engine):
        return None

    monkeypatch.setattr(migrate, "_create_initial_schema", _fake_create)
    success = asyncio.run(migrate.run_migrations(_FakeEngine(), MigrationConfig()))
    assert success is True


def test_run_migrations_no_auto_migrate(monkeypatch):
    from chronus.database import migrate

    async def _fake_create(engine):
        return None

    monkeypatch.setattr(migrate, "_create_initial_schema", _fake_create)
    success = asyncio.run(
        migrate.run_migrations(_FakeEngine(), MigrationConfig(auto_migrate=False))
    )
    assert success is True


def test_run_migrations_failure_returns_false():
    from chronus.database import migrate

    class _BrokenEngine:
        def begin(self):
            raise RuntimeError("engine exploded")

    success = asyncio.run(migrate.run_migrations(_BrokenEngine(), MigrationConfig()))
    assert success is False
