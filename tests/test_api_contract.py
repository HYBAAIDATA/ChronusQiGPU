"""Contract tests: the guarantees the surface actually makes."""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

from chronus.service.api import claims, state, store
from chronus.service.api.app import create_app, reset_rate_limit
from chronus.service.api.claims import reset_cache as reset_claim_cache
from chronus.service.api.errors import ApiError
from chronus.service.api.idempotency import reset_idempotency_store
from chronus.service.api.schemas import WorkloadState
from chronus.service.api.security import reset_token_cache

TOKENS = {
    "tok-alpha-000001": {"tenant_id": "acme", "scopes": [
        "workloads:read", "workloads:write", "fleet:read", "evidence:read"]},
    "tok-beta-0000002": {"tenant_id": "globex", "scopes": [
        "workloads:read", "evidence:read"]},
}
ALPHA = {"Authorization": "Bearer tok-alpha-000001"}
BETA = {"Authorization": "Bearer tok-beta-0000002"}
BODY = {"kind": "inference", "region": "eu-west", "image": "img:1",
        "duration_seconds": 300}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("CHRONUS_TENANT_TOKENS", json.dumps(TOKENS))
    monkeypatch.setenv("CHRONUS_CLAIM_AUDIT", "docs/claim-audit.yaml")
    monkeypatch.setenv("CHRONUS_RATE_MAX", "120")
    monkeypatch.setenv("CHRONUS_API_STATE_BACKEND", "memory")
    monkeypatch.delenv("CHRONUS_LEASE_FILE", raising=False)
    reset_token_cache()
    reset_idempotency_store()
    reset_claim_cache()
    reset_rate_limit()
    store.reset()
    store.seed_nodes([{"id": "n1", "region": "eu-west", "tier": "shared",
                       "gpu_model": "igpu-a", "gpu_count": 4, "state": "ready"}])
    yield
    for reset in (reset_token_cache, reset_idempotency_store, reset_claim_cache,
                  reset_rate_limit):
        reset()


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


def _post(client, headers, key="idem-key-0001", body=BODY):
    return client.post("/v1/workloads", json=body,
                       headers={**headers, "Idempotency-Key": key})


def _audit(tmp_path, body):
    path = tmp_path / "claim-audit.yaml"
    path.write_text(body, encoding="utf-8")
    return path


# --- auth -------------------------------------------------------------------

def test_missing_token_is_401_problem_json(client):
    response = client.get("/v1/workloads")
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "missing_token"
    assert "WWW-Authenticate" in response.headers


def test_bad_token_is_401(client):
    response = client.get("/v1/workloads", headers={"Authorization": "Bearer nope"})
    assert response.json()["code"] == "invalid_token"


def test_insufficient_scope_is_403(client):
    assert client.get("/v1/nodes", headers=BETA).status_code == 403


# --- create and idempotency -------------------------------------------------

def test_create_returns_202_and_location(client):
    response = _post(client, ALPHA)
    assert response.status_code == 202
    assert response.headers["Location"].startswith("/v1/workloads/wl_")


def test_replay_same_key_and_body_returns_same_workload(client):
    first = _post(client, ALPHA)
    second = _post(client, ALPHA)
    assert second.status_code == 202
    assert second.json()["id"] == first.json()["id"]
    assert second.headers.get("Idempotent-Replay") == "true"


def test_sqlite_workload_is_visible_across_app_instances(tmp_path, monkeypatch):
    monkeypatch.setenv("CHRONUS_API_STATE_BACKEND", "sqlite")
    monkeypatch.setenv("CHRONUS_API_DB_PATH", str(tmp_path / "api.sqlite3"))
    first = TestClient(create_app(), raise_server_exceptions=False)
    second = TestClient(create_app(), raise_server_exceptions=False)
    workload_id = _post(first, ALPHA, key="shared-visibility-0001").json()["id"]
    response = second.get(f"/v1/workloads/{workload_id}", headers=ALPHA)
    assert response.status_code == 200
    assert response.json()["id"] == workload_id


def test_sqlite_idempotency_survives_app_recreation(tmp_path, monkeypatch):
    monkeypatch.setenv("CHRONUS_API_STATE_BACKEND", "sqlite")
    monkeypatch.setenv("CHRONUS_API_DB_PATH", str(tmp_path / "api.sqlite3"))
    first = TestClient(create_app(), raise_server_exceptions=False)
    created = _post(first, ALPHA, key="restart-idem-0001")
    first.close()
    second = TestClient(create_app(), raise_server_exceptions=False)
    replay = _post(second, ALPHA, key="restart-idem-0001")
    assert replay.status_code == 202
    assert replay.json()["id"] == created.json()["id"]
    assert replay.headers["Idempotent-Replay"] == "true"


def test_concurrent_sqlite_idempotency_creates_one_workload(tmp_path, monkeypatch):
    monkeypatch.setenv("CHRONUS_API_STATE_BACKEND", "sqlite")
    monkeypatch.setenv("CHRONUS_API_DB_PATH", str(tmp_path / "api.sqlite3"))
    clients = [TestClient(create_app(), raise_server_exceptions=False) for _ in range(2)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(
            lambda current: _post(current, ALPHA, key="concurrent-idem-0001"), clients
        ))
    assert {response.status_code for response in responses} == {202}
    assert len({response.json()["id"] for response in responses}) == 1
    assert len(store.list_workloads("acme", 100, None, None)[0]) == 1
    assert len(clients[0].get("/v1/workloads", headers=ALPHA).json()["items"]) == 1


def test_concurrent_sqlite_first_use_initializes_wal_once(tmp_path, monkeypatch):
    """Concurrent first connections must not compete to switch journal modes."""
    monkeypatch.setenv("CHRONUS_API_STATE_BACKEND", "sqlite")
    monkeypatch.setenv("CHRONUS_API_DB_PATH", str(tmp_path / "first-use.sqlite3"))
    barrier = Barrier(8)

    def open_connection(_):
        barrier.wait()
        with state.connection() as conn:
            return conn.execute("PRAGMA journal_mode").fetchone()[0]

    with ThreadPoolExecutor(max_workers=8) as pool:
        modes = list(pool.map(open_connection, range(8)))
    assert modes == ["wal"] * 8


def test_sqlite_replaced_database_fails_closed_and_readiness_drops(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("CHRONUS_API_STATE_BACKEND", "sqlite")
    db_path = tmp_path / "api.sqlite3"
    monkeypatch.setenv("CHRONUS_API_DB_PATH", str(db_path))
    with state.connection() as conn:
        assert conn.execute("SELECT count(*) FROM api_workloads").fetchone()

    replacement = tmp_path / "replacement.sqlite3"
    with sqlite3.connect(replacement) as conn:
        conn.execute("CREATE TABLE unrelated (value INTEGER)")
    replacement.replace(db_path)

    with pytest.raises(RuntimeError, match="database replaced"):
        with state.connection():
            pass

    response = TestClient(create_app(), raise_server_exceptions=False).get(
        "/health/ready"
    )
    assert response.status_code == 503
    assert "state_unavailable" in response.json()["reasons"]
    # Do not leave intentionally invalid SQLite state for fixture cleanup.
    monkeypatch.setenv("CHRONUS_API_STATE_BACKEND", "memory")


def test_sqlite_missing_schema_after_initialization_fails_closed(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("CHRONUS_API_STATE_BACKEND", "sqlite")
    db_path = tmp_path / "api.sqlite3"
    monkeypatch.setenv("CHRONUS_API_DB_PATH", str(db_path))
    with state.connection():
        pass
    with sqlite3.connect(db_path) as conn:
        conn.execute("DROP TABLE api_rate_limits")

    with pytest.raises(RuntimeError, match="schema changed"):
        with state.connection():
            pass
    monkeypatch.setenv("CHRONUS_API_STATE_BACKEND", "memory")


def test_sqlite_restart_does_not_repair_missing_table(tmp_path, monkeypatch):
    monkeypatch.setenv("CHRONUS_API_STATE_BACKEND", "sqlite")
    db_path = tmp_path / "api.sqlite3"
    monkeypatch.setenv("CHRONUS_API_DB_PATH", str(db_path))
    with state.connection():
        pass
    with sqlite3.connect(db_path) as conn:
        conn.execute("DROP TABLE api_rate_limits")
    # Simulate the empty in-memory cache on a process restart.
    monkeypatch.setattr(state, "_INITIALIZED_DB", {})
    with pytest.raises(RuntimeError, match="existing database"):
        with state.connection():
            pass
    monkeypatch.setenv("CHRONUS_API_STATE_BACKEND", "memory")


def test_sqlite_schema_validation_checks_primary_key(tmp_path, monkeypatch):
    monkeypatch.setenv("CHRONUS_API_STATE_BACKEND", "sqlite")
    db_path = tmp_path / "api.sqlite3"
    monkeypatch.setenv("CHRONUS_API_DB_PATH", str(db_path))
    with state.connection():
        pass
    with sqlite3.connect(db_path) as conn:
        conn.execute("DROP INDEX api_workloads_tenant_created")
        conn.execute("DROP TABLE api_workloads")
        conn.execute(
            "CREATE TABLE api_workloads (record_id TEXT, tenant_id TEXT, "
            "state TEXT, created_at TEXT, record_json TEXT NOT NULL)"
        )
        conn.execute(
            "CREATE INDEX api_workloads_tenant_created "
            "ON api_workloads (tenant_id, created_at, record_id)"
        )
    with pytest.raises(RuntimeError, match="schema changed"):
        with state.connection():
            pass
    monkeypatch.setenv("CHRONUS_API_STATE_BACKEND", "memory")


def test_sqlite_detects_path_swap_during_connection_open(tmp_path, monkeypatch):
    monkeypatch.setenv("CHRONUS_API_STATE_BACKEND", "sqlite")
    db_path = tmp_path / "api.sqlite3"
    monkeypatch.setenv("CHRONUS_API_DB_PATH", str(db_path))
    with state.connection():
        pass
    replacement_db = tmp_path / "replacement.sqlite3"
    with sqlite3.connect(replacement_db) as conn:
        conn.execute("CREATE TABLE unrelated (value INTEGER)")

    actual_connect = state.sqlite3.connect
    def connect_with_swap(*args, **kwargs):
        opened = actual_connect(*args, **kwargs)
        replacement_db.replace(db_path)
        return opened

    with monkeypatch.context() as patch:
        patch.setattr(state.sqlite3, "connect", connect_with_swap)
        with pytest.raises(RuntimeError, match="database changed while opening"):
            with state.connection():
                pass
    monkeypatch.setenv("CHRONUS_API_STATE_BACKEND", "memory")


def test_sqlite_path_alias_replacement_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("CHRONUS_API_STATE_BACKEND", "sqlite")
    db_path = tmp_path / "api.sqlite3"
    monkeypatch.setenv("CHRONUS_API_DB_PATH", str(db_path))
    with state.connection():
        pass
    replacement = tmp_path / "fresh.sqlite3"
    with sqlite3.connect(replacement) as conn:
        conn.execute("CREATE TABLE unrelated (value INTEGER)")
    replacement.replace(db_path)
    monkeypatch.setenv("CHRONUS_API_DB_PATH", str(tmp_path) + "/./api.sqlite3")
    with pytest.raises(RuntimeError, match="database replaced"):
        with state.connection():
            pass
    monkeypatch.setenv("CHRONUS_API_STATE_BACKEND", "memory")


def test_sqlite_rejects_unique_replacement_for_nonunique_expiry_index(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("CHRONUS_API_STATE_BACKEND", "sqlite")
    db_path = tmp_path / "api.sqlite3"
    monkeypatch.setenv("CHRONUS_API_DB_PATH", str(db_path))
    with state.connection():
        pass
    with sqlite3.connect(db_path) as conn:
        conn.execute("DROP INDEX api_idempotency_expires")
        conn.execute(
            "CREATE UNIQUE INDEX api_idempotency_expires "
            "ON api_idempotency (expires)"
        )
    with pytest.raises(RuntimeError, match="schema changed"):
        with state.connection():
            pass
    monkeypatch.setenv("CHRONUS_API_STATE_BACKEND", "memory")


def test_sqlite_rejects_unexpected_write_trigger(tmp_path, monkeypatch):
    monkeypatch.setenv("CHRONUS_API_STATE_BACKEND", "sqlite")
    db_path = tmp_path / "api.sqlite3"
    monkeypatch.setenv("CHRONUS_API_DB_PATH", str(db_path))
    with state.connection():
        pass
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TRIGGER deny_valid_writes BEFORE INSERT ON api_workloads "
            "BEGIN SELECT RAISE(ABORT, 'blocked'); END"
        )
    with pytest.raises(RuntimeError, match="schema changed"):
        with state.connection():
            pass
    monkeypatch.setenv("CHRONUS_API_STATE_BACKEND", "memory")


def test_sqlite_symlink_retarget_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("CHRONUS_API_STATE_BACKEND", "sqlite")
    first = tmp_path / "first.sqlite3"
    second = tmp_path / "second.sqlite3"
    link = tmp_path / "current.sqlite3"
    for db_path in (first, second):
        monkeypatch.setenv("CHRONUS_API_DB_PATH", str(db_path))
        with state.connection():
            pass
    link.symlink_to(first)
    monkeypatch.setenv("CHRONUS_API_DB_PATH", str(link))
    with state.connection():
        pass
    link.unlink()
    link.symlink_to(second)
    with pytest.raises(RuntimeError, match="database replaced"):
        with state.connection():
            pass
    monkeypatch.setenv("CHRONUS_API_STATE_BACKEND", "memory")


def test_sqlite_steady_state_connections_do_not_take_bootstrap_lock(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("CHRONUS_API_STATE_BACKEND", "sqlite")
    monkeypatch.setenv("CHRONUS_API_DB_PATH", str(tmp_path / "api.sqlite3"))
    with state.connection():
        pass

    class RejectBootstrapLock:
        def __enter__(self):
            raise AssertionError("regular connections should not take bootstrap lock")

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(state, "_SCHEMA_LOCK", RejectBootstrapLock())
    with state.connection() as conn:
        assert conn.execute("SELECT 1").fetchone()[0] == 1
    monkeypatch.setenv("CHRONUS_API_STATE_BACKEND", "memory")


def test_same_key_different_body_is_409(client):
    _post(client, ALPHA)
    response = _post(client, ALPHA, body={**BODY, "gpu_count": 2})
    assert response.status_code == 409
    assert response.json()["code"] == "idempotency_conflict"


def test_missing_idempotency_key_is_428(client):
    assert client.post("/v1/workloads", json=BODY, headers=ALPHA).status_code == 428


# --- tenancy and pagination -------------------------------------------------

def test_cross_tenant_read_is_404(client):
    workload_id = _post(client, ALPHA).json()["id"]
    assert client.get(f"/v1/workloads/{workload_id}", headers=BETA).status_code == 404


def test_pagination_walks_without_duplicates(client):
    for i in range(3):
        _post(client, ALPHA, key=f"idem-key-{i:04d}", body={**BODY, "gpu_count": i + 1})
    page1 = client.get("/v1/workloads?limit=2", headers=ALPHA).json()
    assert len(page1["items"]) == 2 and page1["next_cursor"]
    page2 = client.get(f"/v1/workloads?limit=2&cursor={page1['next_cursor']}",
                       headers=ALPHA).json()
    assert len(page2["items"]) == 1
    seen = {w["id"] for w in page1["items"]} | {w["id"] for w in page2["items"]}
    assert len(seen) == 3


def test_bad_cursor_is_400(client):
    assert client.get("/v1/workloads?cursor=!!!", headers=ALPHA).status_code == 400


def test_non_ascii_cursor_is_400(client):
    assert client.get("/v1/workloads?cursor=%C3%A9", headers=ALPHA).status_code == 400


# --- cancel and error shape -------------------------------------------------

def test_cancel_is_202_then_409(client):
    workload_id = _post(client, ALPHA).json()["id"]
    assert client.delete(f"/v1/workloads/{workload_id}", headers=ALPHA).status_code == 202
    assert client.delete(f"/v1/workloads/{workload_id}", headers=ALPHA).status_code == 409


def test_unknown_path_is_problem_json(client):
    response = client.get("/v1/nope", headers=ALPHA)
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_validation_error_names_the_field(client):
    response = _post(client, ALPHA, body={**BODY, "gpu_count": 99})
    assert response.status_code == 422
    assert response.json()["fields"][0]["location"] == "gpu_count"


def test_unknown_field_is_rejected(client):
    assert _post(client, ALPHA, body={**BODY, "typo": 1}).status_code == 422


# --- receipts ---------------------------------------------------------------

def test_receipt_is_minted_on_success(client):
    workload_id = _post(client, ALPHA).json()["id"]
    store.transition("acme", workload_id, WorkloadState.succeeded)
    receipt = client.get(f"/v1/workloads/{workload_id}/receipt", headers=ALPHA)
    assert receipt.status_code == 200
    assert receipt.json()["workload_id"] == workload_id
    # Same receipt reachable by id, and only by its own tenant.
    assert client.get(f"/v1/receipts/{receipt.json()['id']}",
                      headers=ALPHA).status_code == 200
    assert client.get(f"/v1/receipts/{receipt.json()['id']}",
                      headers=BETA).status_code == 404


def test_receipt_is_404_before_success(client):
    workload_id = _post(client, ALPHA).json()["id"]
    response = client.get(f"/v1/workloads/{workload_id}/receipt", headers=ALPHA)
    assert response.json()["code"] == "receipt_not_ready"


def test_cancel_and_success_are_serialized_across_workers(tmp_path, monkeypatch):
    monkeypatch.setenv("CHRONUS_API_STATE_BACKEND", "sqlite")
    monkeypatch.setenv("CHRONUS_API_DB_PATH", str(tmp_path / "api.sqlite3"))
    fresh = TestClient(create_app(), raise_server_exceptions=False)
    workload_id = _post(fresh, ALPHA, key="terminal-race-0001").json()["id"]

    def attempt(action):
        try:
            return "ok", action().state
        except ApiError as exc:
            return "error", exc.status

    actions = (
        lambda: store.cancel_workload("acme", workload_id),
        lambda: store.transition("acme", workload_id, WorkloadState.succeeded),
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, actions))

    assert [kind for kind, _ in outcomes].count("ok") == 1
    assert ("error", 409) in outcomes
    final = store.get_workload("acme", workload_id)
    assert final.state in {WorkloadState.cancelled, WorkloadState.succeeded}
    receipts = state.all_records("receipts")
    assert len(receipts) == (1 if final.state is WorkloadState.succeeded else 0)


# --- ops --------------------------------------------------------------------

def test_rate_limit_is_429_problem_json(monkeypatch):
    monkeypatch.setenv("CHRONUS_RATE_MAX", "2")
    reset_rate_limit()
    fresh = TestClient(create_app(), raise_server_exceptions=False)
    codes = [fresh.get("/v1/workloads", headers=ALPHA).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    response = fresh.get("/v1/workloads", headers=ALPHA)
    assert response.headers["content-type"].startswith("application/problem+json")
    assert "Retry-After" in response.headers


def test_sqlite_rate_limit_is_shared_across_app_instances(tmp_path, monkeypatch):
    monkeypatch.setenv("CHRONUS_API_STATE_BACKEND", "sqlite")
    monkeypatch.setenv("CHRONUS_API_DB_PATH", str(tmp_path / "api.sqlite3"))
    monkeypatch.setenv("CHRONUS_RATE_MAX", "2")
    reset_rate_limit()
    first = TestClient(create_app(), raise_server_exceptions=False)
    second = TestClient(create_app(), raise_server_exceptions=False)
    codes = [
        first.get("/v1/workloads", headers=ALPHA).status_code,
        second.get("/v1/workloads", headers=ALPHA).status_code,
        first.get("/v1/workloads", headers=ALPHA).status_code,
    ]
    assert codes == [200, 200, 429]


def test_readiness_fails_when_tokens_unset(monkeypatch):
    monkeypatch.delenv("CHRONUS_TENANT_TOKENS", raising=False)
    reset_token_cache()
    fresh = TestClient(create_app(), raise_server_exceptions=False)
    response = fresh.get("/health/ready")
    assert response.status_code == 503
    assert "auth_not_configured" in response.json()["reasons"]


# --- claim audit ------------------------------------------------------------

def test_supported_claim_without_evidence_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("CHRONUS_CLAIM_AUDIT", str(_audit(
        tmp_path,
        "version: 1\nreviewed_at: 2026-11-14\ncommit: x\nclaims:\n"
        "  - id: bad-claim\n    statement: s\n    disposition: supported\n"
        "    reviewer: r\n    evidence: []\n")))
    reset_claim_cache()
    with pytest.raises(ApiError) as err:
        claims.load_audit()
    assert err.value.code == "claim_audit_invalid"


def test_unknown_disposition_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("CHRONUS_CLAIM_AUDIT", str(_audit(
        tmp_path,
        "version: 1\nreviewed_at: 2026-11-14\ncommit: x\nclaims:\n"
        "  - id: bad-claim\n    statement: s\n    disposition: probably\n")))
    reset_claim_cache()
    with pytest.raises(ApiError):
        claims.load_audit()


def test_posture_is_not_qualified_while_any_claim_is_unverified(client):
    body = client.get("/v1/qualification", headers=ALPHA).json()
    assert body["posture"] == "not_qualified"
    assert body["counts"]["unverified"] >= 1
    assert body["blockers"]


def test_withdrawn_claim_is_served_as_withdrawn(client):
    items = client.get("/v1/capabilities?disposition=withdrawn", headers=ALPHA).json()
    assert any(c["id"] == "quantum-advantage" for c in items)


# --- lease ------------------------------------------------------------------

def _lease(tmp_path, monkeypatch, **fields):
    path = tmp_path / "lease.json"
    path.write_text(json.dumps({"tenant_id": "acme", "tier": "shared",
                                "entitlements": [], **fields}), encoding="utf-8")
    monkeypatch.setenv("CHRONUS_LEASE_FILE", str(path))


def test_expired_lease_blocks_submission(client, tmp_path, monkeypatch):
    _lease(tmp_path, monkeypatch, expires_at="2020-01-01T00:00:00+00:00")
    response = _post(client, ALPHA)
    assert response.status_code == 403
    assert response.json()["code"] == "lease_expired"


def test_revoked_lease_blocks_submission(client, tmp_path, monkeypatch):
    _lease(tmp_path, monkeypatch, revoked=True)
    assert _post(client, ALPHA).json()["code"] == "lease_revoked"


def test_kind_not_entitled_is_403(client, tmp_path, monkeypatch):
    _lease(tmp_path, monkeypatch, entitlements=["mining"])
    assert _post(client, ALPHA).json()["code"] == "kind_not_entitled"
