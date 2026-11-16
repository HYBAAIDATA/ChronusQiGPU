"""Admission tests for shared mining administration (no live pool traffic)."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from chronus.service.app import app
from chronus.service.auth_middleware import Role, create_jwt_token
from chronus.service.dependencies import auth_service
from chronus.storage.durable import DurableTheseusService


@pytest.fixture
def guarded(tmp_path, monkeypatch):
    monkeypatch.setenv("CHRONUS_JWT_SECRET", "admin-admission-test-key-of-at-least-thirty-two-bytes")
    monkeypatch.setenv("CHRONUS_MINING_ADMIN_SUBJECTS", json.dumps(["operator-1"]))
    monkeypatch.setenv("CHRONUS_MINING_ADMIN_TENANT_ID", "mining-tenant")
    path = str(tmp_path / "admission.sqlite3")
    monkeypatch.setenv("CHRONUS_MINING_ADMIN_CUSTODY_PATH", path)
    monkeypatch.delenv("CHRONUS_DEV_JWT_PERMISSIVE", raising=False)
    return TestClient(app), path


def signed_headers(tenant="mining-tenant", user="operator-1", role=Role.SYSTEM_ADMIN):
    return {
        "Authorization": "Bearer " + create_jwt_token(
            tenant_id=tenant, user_id=user, role=role
        )
    }


def test_system_admin_explicit_subject_and_tenant_is_audited(guarded):
    client, path = guarded
    response = client.post("/v1/mining/admin/stop", headers=signed_headers())
    assert response.status_code == 200, response.text
    custody = DurableTheseusService(path)
    events = custody.get_journal("mining-tenant")
    assert len(events) == 1
    assert events[0].event_type == "MINING_ADMIN_OPERATOR_ADMITTED"
    record = json.loads(custody.reconstruct("mining-tenant", events[0].object_id))
    assert record["actor_id"] == "operator-1"
    assert record["tenant_id"] == "mining-tenant"
    assert record["path"] == "/v1/mining/admin/stop"
    assert record["event"] == "OPERATOR_ADMITTED_NOT_ACTION_COMPLETED"
    assert custody.verify_journal_continuity("mining-tenant")


@pytest.mark.parametrize(
    "tenant,user,role",
    [
        ("other-tenant", "operator-1", Role.SYSTEM_ADMIN),
        ("mining-tenant", "other-user", Role.SYSTEM_ADMIN),
        ("mining-tenant", "operator-1", Role.TENANT_ADMIN),
        ("mining-tenant", "operator-1", Role.DEVELOPER),
        ("mining-tenant", "operator-1", Role.ADMIN),
    ],
)
def test_other_tenant_subject_or_role_cannot_control_global_engine(
    guarded, tenant, user, role
):
    client, path = guarded
    denied = client.post(
        "/v1/mining/admin/stop",
        headers=signed_headers(tenant, user, role),
    )
    assert denied.status_code == 403
    assert not __import__("os").path.exists(path)


def test_legacy_tenant_token_cannot_control_global_engine(guarded):
    client, path = guarded
    try:
        auth_service.register_tenant("mining-tenant", "legacy-mining-test-token")
    except ValueError:
        pass
    response = client.post(
        "/v1/mining/admin/stop",
        headers={"Authorization": "Bearer legacy-mining-test-token"},
    )
    assert response.status_code == 403
    assert not __import__("os").path.exists(path)


def test_missing_roster_dev_mode_and_missing_key_fail_closed(guarded, monkeypatch):
    client, _ = guarded
    monkeypatch.delenv("CHRONUS_MINING_ADMIN_SUBJECTS")
    assert client.post("/v1/mining/admin/stop", headers=signed_headers()).status_code == 403
    monkeypatch.setenv("CHRONUS_MINING_ADMIN_SUBJECTS", '["operator-1"]')
    monkeypatch.setenv("CHRONUS_DEV_JWT_PERMISSIVE", "1")
    assert client.post("/v1/mining/admin/stop", headers=signed_headers()).status_code == 403


def test_custody_failure_denies_admission_before_mutation(guarded, monkeypatch, tmp_path):
    client, _ = guarded
    # Point SQLite at a directory, which cannot become a database file.
    monkeypatch.setenv("CHRONUS_MINING_ADMIN_CUSTODY_PATH", str(tmp_path))
    denied = client.post("/v1/mining/admin/stop", headers=signed_headers())
    assert denied.status_code == 503
    assert "durable audit unavailable" in denied.json()["detail"].lower()
