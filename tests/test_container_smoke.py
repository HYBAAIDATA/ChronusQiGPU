"""Fail-closed HTTP smoke regression fixtures (controlled HTTP responses)."""
from contextlib import contextmanager
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
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())

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
    {"valid": False}, {"valid": "true"}, {"ed25519_verified": False},
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
