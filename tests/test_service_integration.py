"""Cross-router integration tests for the Chronus service API.

Exercises interactions that span multiple routers and middleware: error
envelope consistency, observability headers, rate limiting, workload
counters, and receipt verification flows.
"""

import base64
import json

import pytest
from starlette.testclient import TestClient

from chronus.service.app import create_app
from chronus.service.dependencies import RateLimiter, auth_service, service_config


@pytest.fixture()
def client():
    service_config.execution_backend_url = None
    return TestClient(create_app())


@pytest.fixture()
def tenant():
    auth_service.register_tenant("integration-tenant", "integration-token")
    return {
        "tenant_id": "integration-tenant",
        "headers": {"Authorization": "Bearer integration-token"},
    }


def _submit(client, tenant, workload_type="LUCAS_PV_SCALING", payload=None):
    body = {
        "payload_bytes": payload
        or "base64:" + base64.b64encode(json.dumps({"index": 10}).encode()).decode(),
        "tenant_id": tenant["tenant_id"],
        "workload_type": workload_type,
    }
    return client.post("/workloads/submit", headers=tenant["headers"], json=body)


# ---------------------------------------------------------------------------
# Middleware invariants
# ---------------------------------------------------------------------------


def test_response_headers_present_on_success_and_error(client, tenant):
    ok = client.get("/health")
    assert ok.headers["X-Service-Version"] == "36.0.1"
    assert "X-Process-Time" in ok.headers

    err = client.get("/workloads/not-a-uuid", headers=tenant["headers"])
    assert err.headers["X-Service-Version"] == "36.0.1"
    assert "X-Process-Time" in err.headers


def test_error_envelope_consistency_across_routers(client, tenant):
    """All error responses carry a structured detail payload."""
    unauth = client.post("/workloads/submit", json={})
    assert unauth.status_code in (401, 422)

    missing = client.get(
        "/workloads/00000000-0000-0000-0000-000000000000",
        headers=tenant["headers"],
    )
    assert missing.status_code == 404

    bad_verify = client.get("/verify/not a hash!!")
    assert bad_verify.status_code == 400
    detail = bad_verify.json()["detail"]
    assert detail["error"] == "invalid_hash"


def test_openapi_schema_exposes_core_routers(client):
    paths = client.get("/openapi.json").json()["paths"]
    for prefix in (
        "/workloads/submit",
        "/health",
        "/health/ready",
        "/billing/usage",
        "/metrics",
    ):
        assert any(p == prefix or p.startswith(prefix) for p in paths), prefix


# ---------------------------------------------------------------------------
# Rate limiting integration
# ---------------------------------------------------------------------------


def test_rate_limit_returns_429_with_error_code(client, tenant, monkeypatch):
    tight = RateLimiter(requests_per_minute=60, burst=2)
    monkeypatch.setattr(auth_service, "_rate_limiter", tight)
    assert _submit(client, tenant).status_code == 202
    assert _submit(client, tenant).status_code == 202
    limited = _submit(client, tenant)
    assert limited.status_code == 429
    detail = limited.json()["detail"]
    assert detail["error_code"] == "RL001"


def test_zero_auth_get_requests_bypass_rate_limit(client):
    # GET requests with no tenant do not consume any tenant bucket
    for _ in range(5):
        assert client.get("/health").status_code == 200


# ---------------------------------------------------------------------------
# Cross-router state coherence
# ---------------------------------------------------------------------------


def test_health_workload_counter_reflects_submissions(client, tenant):
    before = client.get("/health").json()["total_workloads"]
    response = _submit(client, tenant)
    assert response.status_code == 202
    after = client.get("/health").json()["total_workloads"]
    assert after == before + 1


def test_submitted_workload_persists_and_lists(client, tenant):
    response = _submit(client, tenant)
    assert response.status_code == 202
    workload_id = response.json()["workload_id"]

    fetched = client.get(f"/workloads/{workload_id}", headers=tenant["headers"])
    assert fetched.status_code == 200
    assert fetched.json()["workload_id"] == workload_id

    listed = client.get("/workloads", headers=tenant["headers"])
    assert listed.status_code == 200
    ids = [item["workload_id"] for item in listed.json()["items"]]
    assert workload_id in ids


def test_completed_workload_cannot_be_cancelled(client, tenant):
    response = _submit(client, tenant)
    workload_id = response.json()["workload_id"]
    assert response.json()["status"] == "COMPLETED"
    cancel = client.delete(f"/workloads/{workload_id}", headers=tenant["headers"])
    assert cancel.status_code in (400, 409, 422)


def test_unknown_workload_cancel_returns_404(client, tenant):
    response = client.delete(
        "/workloads/00000000-0000-0000-0000-000000000000",
        headers=tenant["headers"],
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Receipt flow across workload and verify routers
# ---------------------------------------------------------------------------


def test_workload_receipt_verifies_via_zero_auth_endpoint(client, tenant):
    response = _submit(client, tenant)
    assert response.status_code == 202
    receipt = response.json().get("verification_receipt")
    assert receipt, "completed workload must carry a verification receipt"

    verified = client.get(f"/verify/{receipt}")
    assert verified.status_code == 200
    body = verified.json()
    assert body["ed25519_verified"] is True


def test_verify_unknown_receipt_fails_closed(client, tenant):
    digest = "ab" * 32
    response = client.get(f"/verify/{digest}")
    assert response.status_code == 200
    body = response.json()
    assert body["qualification_status"] == "NOT_FOUND"
    assert body["ed25519_verified"] is not True


# ---------------------------------------------------------------------------
# Billing coherence with workload router
# ---------------------------------------------------------------------------


def test_billing_usage_matches_completed_workloads(client, tenant):
    response = _submit(client, tenant)
    assert response.status_code == 202
    usage = client.get("/billing/usage", headers=tenant["headers"])
    assert usage.status_code == 200
    body = usage.json()
    assert body["usage"]["tenant_id"] == tenant["tenant_id"]
    assert body["usage"]["workloads_completed"] >= 1
    assert body["signature_algorithm"] == "Ed25519"
    assert body["invoice"] is False


def test_billing_usage_requires_auth(client):
    response = client.get("/billing/usage")
    assert response.status_code == 401
