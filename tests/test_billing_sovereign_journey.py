"""Evidence-first Hermiten billing integration against existing services."""
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from chronus.service.app import create_app
from chronus.service.auth_middleware import Role, create_jwt_token
from chronus.service.dependencies import auth_service
from chronus.service.routers import billing as billing_router_module
from chronus.service.routers import workloads


class FakeWorkloadStore:
    def __init__(self, rows):
        self.rows = rows

    def list_for_tenant(self, tenant_id, offset, limit):
        selected = [row for row in self.rows if row.tenant_id == tenant_id]
        return selected[offset:offset + limit], len(selected)

    def get(self, workload_id):
        return next((row for row in self.rows if str(row.workload_id) == workload_id), None)


def row(tenant="billing-test", ccu="0.1", receipt="receipt-reference"):
    return SimpleNamespace(
        workload_id=uuid4(), tenant_id=tenant, status="COMPLETED",
        workload_type="LUCAS_PV_SCALING", ccu_cost=ccu,
        verification_receipt=receipt,
    )


@pytest.fixture()
def setup(monkeypatch):
    rows = [row() for _ in range(105)] + [row(tenant="another-tenant", ccu="99")]
    store = FakeWorkloadStore(rows)
    monkeypatch.setattr(workloads, "workload_store", store)
    auth_service.register_tenant("billing-test", "billing-test-static-token")
    client = TestClient(create_app())
    token = create_jwt_token("billing-test", "billing-admin", Role.TENANT_ADMIN)
    developer = create_jwt_token("billing-test", "billing-dev", Role.DEVELOPER)
    return client, store, {"Authorization": f"Bearer {token}"}, {"Authorization": f"Bearer {developer}"}


def test_usage_scans_every_page_and_remains_tenant_scoped(setup):
    client, store, admin, developer = setup
    response = client.get("/billing/usage", headers={"Authorization": "Bearer billing-test-static-token"})
    assert response.status_code == 200
    data = response.json()
    usage = data["usage"]
    assert usage["workloads_visible"] == 105
    assert usage["workloads_completed"] == 105
    assert usage["ccu_total_decimal"] == "10.5"
    assert usage["meter_quality"] == "REPORTED_NOT_INDEPENDENTLY_VERIFIED"
    assert usage["flops_measured"] is False
    assert data["invoice"] is False


def test_missing_ccu_is_not_turned_into_zero(setup):
    client, store, admin, developer = setup
    store.rows[0].ccu_cost = None
    usage = client.get("/billing/usage", headers={"Authorization": "Bearer billing-test-static-token"}).json()["usage"]
    assert usage["ccu_records_unavailable"] == 1
    assert usage["billing_completeness"] == "INCOMPLETE"


def test_delivery_fails_closed_without_config_and_roles(setup, monkeypatch):
    client, store, admin, developer = setup
    wid = store.rows[0].workload_id
    monkeypatch.delenv("CHRONUS_HERMITEN_USAGE_ENABLED", raising=False)
    assert client.post(f"/billing/hermiten/usage/{wid}").status_code == 401
    assert client.post(f"/billing/hermiten/usage/{wid}", headers=developer).status_code == 403
    assert client.post(f"/billing/hermiten/usage/{wid}", headers=admin).status_code == 503
    assert client.post(
        f"/billing/hermiten/usage/{store.rows[-1].workload_id}", headers=admin
    ).status_code == 404


def test_delivery_requires_custody_and_valid_provider_ack(setup, monkeypatch, tmp_path):
    client, store, admin, developer = setup
    wid = store.rows[0].workload_id
    monkeypatch.setenv("CHRONUS_HERMITEN_USAGE_ENABLED", "1")
    monkeypatch.setenv("CHRONUS_HERMITEN_USAGE_ENDPOINT", "https://billing.example.invalid/v1/usage")
    monkeypatch.setenv("CHRONUS_HERMITEN_API_TOKEN", "provider-secret")
    monkeypatch.setenv("CHRONUS_HERMITEN_ACCOUNT_MAP", json.dumps({"billing-test": "live-external-acc"}))
    monkeypatch.delenv("CHRONUS_THESEUS_DB_PATH", raising=False)
    assert client.post(f"/billing/hermiten/usage/{wid}", headers=admin).status_code == 503
    path = tmp_path / "theseus.sqlite3"
    monkeypatch.setenv("CHRONUS_THESEUS_DB_PATH", str(path))
    sent = []

    def fake_send(endpoint, api_token, payload, idempotency_key):
        sent.append((payload, idempotency_key))
        return {"account_id": "live-external-acc", "usage_receipt_id": "external-receipt-1"}

    monkeypatch.setattr(billing_router_module, "_send_hermiten_usage", fake_send)
    response = client.post(f"/billing/hermiten/usage/{wid}", headers=admin)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["invoice"] is False
    assert data["meter_quality"] == "REPORTED_NOT_INDEPENDENTLY_VERIFIED"
    assert sent[0][0]["reported_ccu"] == "0.1"
    assert sent[0][0]["hardware_flops"] is None

    from chronus.storage.durable import DurableTheseusService
    custody = DurableTheseusService(str(path))
    assert custody.verify_journal_continuity("billing-test")
    assert len(custody.get_journal("billing-test")) == 2
    # Retries retain the stable identifier; the provider must deduplicate.
    assert client.post(f"/billing/hermiten/usage/{wid}", headers=admin).status_code == 200
    assert sent[0][1] == sent[1][1]
