"""Local CPU/process/custody evidence; no sovereign deployment qualification."""
import json
import os
import multiprocessing
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from chronus.execution.authority import ExecutionAuthority, ExecutionBusyError
from chronus.service.app import create_app
from chronus.service.dependencies import auth_service


pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX execution limits require a POSIX host")


def _hold_slot(path, ready, release):
    authority = ExecutionAuthority(path, max_concurrent=1)
    with authority._slot():
        ready.set()
        release.wait(10)


@pytest.fixture
def authority(tmp_path):
    return ExecutionAuthority(str(tmp_path / "custody.sqlite3"), max_concurrent=1)


def test_cpu_result_and_receipt_survive_restart(authority):
    receipt = authority.execute("alice", b'{"index":10}', "LUCAS_PV_SCALING")
    assert receipt["status"] == "COMPLETED"
    assert receipt["result"]["result"]["fibonacci"] == "55"
    reopened = ExecutionAuthority(authority.custody.path, max_concurrent=1)
    assert reopened.status("alice", receipt["receipt_object_id"])["run_id"] == receipt["run_id"]
    assert reopened.custody.verify_journal_continuity("alice")
    with pytest.raises(KeyError):
        reopened.status("bob", receipt["receipt_object_id"])


def test_timeout_reaps_worker_and_releases_slot(authority):
    before = {p.pid for p in multiprocessing.active_children()}
    start = time.monotonic()
    receipt = authority.execute("alice", b'{"index":10}', "LUCAS_PV_SCALING", 0.001)
    assert receipt["status"] == "TIMED_OUT"
    assert time.monotonic() - start < 3
    assert {p.pid for p in multiprocessing.active_children()} == before
    assert authority.status("alice", receipt["receipt_object_id"])["status"] == "TIMED_OUT"
    assert authority.execute("alice", b'{"index":10}', "LUCAS_PV_SCALING")["status"] == "COMPLETED"


def test_slots_are_shared_across_processes(authority):
    ctx = multiprocessing.get_context("spawn")
    ready, release = ctx.Event(), ctx.Event()
    child = ctx.Process(target=_hold_slot, args=(authority.custody.path, ready, release))
    child.start()
    try:
        assert ready.wait(10)
        with pytest.raises(ExecutionBusyError):
            authority.execute("alice", b'{}', "LUCAS_PV_SCALING")
    finally:
        release.set()
        child.join(10)
        if child.is_alive():
            child.kill()
            child.join()
    assert child.exitcode == 0


def test_parallel_requests_cannot_exceed_limit(authority):
    with authority._slot(), ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(authority.execute, "alice", b'{}', "LUCAS_PV_SCALING") for _ in range(4)]
        for future in futures:
            with pytest.raises(ExecutionBusyError):
                future.result()


def test_failures_are_durable_and_custody_failure_blocks_execution(authority, monkeypatch):
    receipt = authority.execute("alice", b'not json', "LUCAS_PV_SCALING")
    assert receipt["status"] == "FAILED"
    assert authority.status("alice", receipt["receipt_object_id"])["error"]
    def fail(*args):
        raise OSError("custody unavailable")
    monkeypatch.setattr(authority.custody, "append_journal_event", fail)
    with pytest.raises(OSError):
        authority.execute("alice", b'{}', "LUCAS_PV_SCALING")


@pytest.mark.parametrize("budget", [0, -1, float("nan"), float("inf"), True, 31])
def test_invalid_budgets_rejected(authority, budget):
    with pytest.raises(ValueError):
        authority.execute("alice", b'{}', "LUCAS_PV_SCALING", budget)


def test_conflicting_policy_rejected(authority):
    with pytest.raises(ValueError, match="policy differs"):
        ExecutionAuthority(authority.custody.path, max_concurrent=2)


def test_api_authentication_tenant_isolation_and_restart(authority):
    auth_service.register_tenant("alice", "authority-alice-test")
    auth_service.register_tenant("bob", "authority-bob-test")
    app = create_app()
    app.state.execution_authority = authority
    client = TestClient(app)
    body = {"workload": {"tenant_id": "alice", "workload_type": "scaling.v1", "payload_bytes": '{"index":10}'}}
    headers = {"Authorization": "Bearer authority-alice-test"}
    assert client.post("/api/v1/execute", json=body).status_code == 401
    assert client.post("/api/v1/execute", json=body, headers={"Authorization": "Bearer authority-bob-test"}).status_code == 403
    response = client.post("/api/v1/execute", json=body, headers=headers)
    assert response.status_code == 200, response.text
    receipt = response.json()
    assert receipt["status"] == "COMPLETED"
    params = {"receipt_object_id": receipt["receipt_object_id"]}
    assert client.get("/api/v1/execute/status", params=params).status_code == 401
    assert client.get("/api/v1/execute/status", params=params, headers={"Authorization": "Bearer authority-bob-test"}).status_code == 404
    assert client.get("/api/v1/execute/status", params=params, headers=headers).json()["status"] == "COMPLETED"
    with authority._slot():
        assert client.post("/api/v1/execute", json=body, headers=headers).status_code == 429
    body["workload"]["backend_preference"] = "cuda"
    assert client.post("/api/v1/execute", json=body, headers=headers).status_code == 400


def test_execution_body_cap_before_parsing(authority):
    app = create_app()
    app.state.execution_authority = authority
    client = TestClient(app)
    response = client.post("/api/v1/execute", content=b"x" * (4 * 1024 * 1024 + 1))
    assert response.status_code == 413


def test_custody_corruption_does_not_return_success(authority):
    import sqlite3
    receipt = authority.execute("alice", b'{"index":10}', "LUCAS_PV_SCALING")
    with sqlite3.connect(authority.custody.path) as db:
        db.execute("UPDATE objects SET payload=? WHERE object_id=?", (b"corrupt", receipt["receipt_object_id"]))
    with pytest.raises(Exception, match="digest verification"):
        authority.status("alice", receipt["receipt_object_id"])


def test_terminal_custody_failure_never_returns_completed(authority, monkeypatch):
    real = authority.custody.append_journal_event
    def fail_terminal(tenant, event, payload):
        if event != "EXECUTION_ADMITTED":
            raise OSError("disk unavailable")
        return real(tenant, event, payload)
    monkeypatch.setattr(authority.custody, "append_journal_event", fail_terminal)
    with pytest.raises(OSError):
        authority.execute("alice", b'{"index":10}', "LUCAS_PV_SCALING")
    assert len(authority.custody.get_journal("alice")) == 1


def test_encrypted_custody_uses_unique_nonces_and_customer_key(tmp_path):
    import base64
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    key = AESGCM.generate_key(bit_length=256)
    path = str(tmp_path / "encrypted.sqlite3")
    authority = ExecutionAuthority(path, custody_key=key)
    receipts = [authority.execute("alice", b'{"index":10}', "LUCAS_PV_SCALING") for _ in range(2)]
    nonces = []
    for receipt in receipts:
        sealed = json.loads(authority.custody.reconstruct("alice", receipt["receipt_object_id"]))
        assert sealed["encryption"] == "AES-256-GCM"
        assert "fibonacci" not in json.dumps(sealed)
        nonces.append(base64.b64decode(sealed["nonce"]))
    assert nonces[0] != nonces[1]
    reopened = ExecutionAuthority(path, custody_key=key)
    assert reopened.replay("alice", receipts[0]["receipt_object_id"])["integrity_verified"]
    with pytest.raises(ValueError, match="policy differs"):
        ExecutionAuthority(path, custody_key=AESGCM.generate_key(bit_length=256))
    with pytest.raises(ValueError, match="policy differs"):
        ExecutionAuthority(path)


def test_minimal_service_excludes_legacy_execution_surfaces():
    from chronus.service.execution_app import create_execution_app
    app = create_execution_app()
    paths = set(app.openapi()["paths"])
    assert "/api/v1/execute" in paths
    assert "/workloads/submit" not in paths
    assert "/v1/mining/admin/start" not in paths


def test_bounded_mining_disallows_nested_worker_pools(authority):
    payload = json.dumps({"header_hex": "00" * 80, "target_hex": "ff" * 32,
                          "start": 0, "stop": 1, "workers": 2}).encode()
    assert authority.execute("alice", payload, "SHA256D_NONCE_SEARCH")["status"] == "FAILED"
