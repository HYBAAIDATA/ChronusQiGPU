"""Fail-closed HTTP smoke regression fixtures (controlled HTTP responses)."""
from contextlib import contextmanager
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
from threading import Thread

import pytest

pytestmark = pytest.mark.simulated

SPEC = importlib.util.spec_from_file_location(
    "container_smoke", Path(__file__).with_name("container_smoke.py")
)
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


@contextmanager
def response_server(status, payload):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        do_POST = do_GET

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize("expected", [200, 202, 401, 403])
def test_not_found_is_neither_success_nor_an_authorization_denial(monkeypatch, expected):
    with response_server(404, {"detail": "not found"}) as url:
        monkeypatch.setenv("CHRONUS_SMOKE_URL", url)
        with pytest.raises(AssertionError, match=f"expected HTTP {expected}, got 404"):
            smoke.request("/workloads/missing", expected_status=expected)


def test_exact_unauthorized_response_is_exercised(monkeypatch):
    with response_server(401, {"detail": {"error_code": "AUTH001"}}) as url:
        monkeypatch.setenv("CHRONUS_SMOKE_URL", url)
        assert smoke.request("/workloads", expected_status=401)["detail"]["error_code"] == "AUTH001"


def receipt():
    return {
        "valid": True, "ed25519_verified": True, "reason": "ok",
        "receipt_handle": "o1_ci_fixture",
        "metadata": {"tenant_id": "ci", "receipt_scope": "workload_result_digest"},
        "mldsa_sig": "NOT_EVALUATED", "zk_stark": "NOT_EVALUATED",
    }


@pytest.mark.parametrize("change", [
    {"valid": False}, {"valid": "true"}, {"valid": 1},
    {"ed25519_verified": False}, {"ed25519_verified": "true"},
    {"ed25519_verified": 1},
    {"reason": "not_found"}, {"receipt_handle": "o1_other_fixture"},
    {"metadata": {"tenant_id": "another-tenant", "receipt_scope": "workload_result_digest"}},
])
def test_bad_receipt_response_cannot_be_bypassed(monkeypatch, change):
    with response_server(200, {**receipt(), **change}) as url:
        monkeypatch.setenv("CHRONUS_SMOKE_URL", url)
        with pytest.raises(AssertionError):
            smoke.verify_receipt("o1_ci_fixture")


def test_valid_local_receipt_is_checked_without_promoting_release_evidence(monkeypatch):
    with response_server(200, receipt()) as url:
        monkeypatch.setenv("CHRONUS_SMOKE_URL", url)
        smoke.verify_receipt("o1_ci_fixture")


def denial(status):
    error, code = {
        401: ("authentication_required", "AUTH001"),
        403: ("tenant_mismatch", "AUTH002"),
    }[status]
    return {"detail": {"error": error, "error_code": code, "message": "Denied."}}


@pytest.mark.parametrize("status", [401, 403])
def test_exact_denial_requires_structured_authorization_error(monkeypatch, status):
    with response_server(status, denial(status)) as url:
        monkeypatch.setenv("CHRONUS_SMOKE_URL", url)
        smoke.denied("/workloads/submit", smoke.workload_payload(), expected_status=status)


@pytest.mark.parametrize("payload", [
    {}, {"detail": {}},
    {"detail": {"error": "authentication_required"}},
    {"detail": {"error": "authentication_required", "error_code": "AUTH001"}},
    {"detail": {"error": "not_found", "error_code": "AUTH001", "message": "Denied."}},
    {"detail": {"error": "authentication_required", "error_code": "OTHER", "message": "Denied."}},
    {"detail": {"error": "authentication_required", "error_code": "AUTH001", "message": " "}},
])
def test_denial_with_missing_or_wrong_fields_is_not_success(monkeypatch, payload):
    with response_server(401, payload) as url:
        monkeypatch.setenv("CHRONUS_SMOKE_URL", url)
        with pytest.raises((AssertionError, KeyError)):
            smoke.denied("/workloads/submit", smoke.workload_payload())


@pytest.mark.parametrize("status", [200, 202, 404, 500])
def test_success_not_found_and_server_errors_cannot_satisfy_denial(monkeypatch, status):
    with response_server(status, denial(401)) as url:
        monkeypatch.setenv("CHRONUS_SMOKE_URL", url)
        with pytest.raises(AssertionError, match=f"expected HTTP 401, got {status}"):
            smoke.denied("/workloads/submit", smoke.workload_payload())


@pytest.mark.parametrize("field", [
    ("valid",), ("ed25519_verified",), ("reason",), ("receipt_handle",),
    ("metadata",), ("metadata", "tenant_id"), ("metadata", "receipt_scope"),
    ("mldsa_sig",), ("zk_stark",),
])
def test_receipt_missing_a_required_field_is_not_success(monkeypatch, field):
    payload = deepcopy(receipt())
    parent = payload if len(field) == 1 else payload[field[0]]
    del parent[field[-1]]
    with response_server(200, payload) as url:
        monkeypatch.setenv("CHRONUS_SMOKE_URL", url)
        with pytest.raises(KeyError):
            smoke.verify_receipt("o1_ci_fixture")


@pytest.mark.parametrize("handle", [None, "", " "])
def test_missing_receipt_handle_fails_before_http(monkeypatch, handle):
    def unexpected_request(*args, **kwargs):
        pytest.fail("An absent receipt handle must fail before an HTTP request")
    monkeypatch.setattr(smoke, "request", unexpected_request)
    with pytest.raises(AssertionError, match="Receipt handle is required"):
        smoke.verify_receipt(handle)


def completed_workload():
    return {
        "workload_id": "00000000-0000-4000-8000-000000000001",
        "tenant_id": "ci", "status": "COMPLETED",
        "result": {"result": {"family": "scaling.v1", "sequence_value": "123"}},
        "verification_receipt": "o1_ci_fixture",
    }


@pytest.mark.parametrize("field", [
    ("status",), ("tenant_id",), ("result",), ("result", "result"),
    ("result", "result", "family"), ("result", "result", "sequence_value"),
    ("workload_id",), ("verification_receipt",),
])
def test_workload_missing_a_required_field_is_not_success(field):
    payload = completed_workload()
    parent = payload
    for key in field[:-1]:
        parent = parent[key]
    del parent[field[-1]]
    with pytest.raises(KeyError):
        smoke.completed(payload)


@pytest.mark.parametrize("operation", ["submit", "verify"])
def test_smoke_checks_missing_and_invalid_auth_before_accepting_workload(monkeypatch, operation):
    calls = []
    monkeypatch.setenv("CHRONUS_SMOKE_TOKEN", "ci-controlled-fixture")

    def response(path, data=None, *, bearer=None, expected_status=200):
        calls.append((path, bearer, expected_status))
        if expected_status in (401, 403):
            return denial(expected_status)
        return receipt() if path.startswith("/verify/") else completed_workload()

    monkeypatch.setattr(smoke, "request", response)
    if operation == "submit":
        assert smoke.submit() == completed_workload()["workload_id"]
        assert [c[2] for c in calls] == [401, 401, 403, 202, 200]
        assert calls[-1][0] == "/verify/o1_ci_fixture"
    else:
        smoke.verify(completed_workload()["workload_id"])
        assert [c[2] for c in calls] == [401, 401, 200]
    assert calls[0][1] is None
    assert calls[1][1] == "ci-controlled-fixture-invalid"
    assert calls[-2 if operation == "submit" else -1][1] == "ci-controlled-fixture"
