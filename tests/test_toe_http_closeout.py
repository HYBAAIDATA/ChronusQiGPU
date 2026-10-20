"""Real HTTP rejection tests; no production engine substituted or certified."""
import concurrent.futures
import http.client
import threading
import pytest
from toe.ciaas_api import CIaaSServer, CIaaSService, RateLimiter


@pytest.fixture
def server():
    # Only HTTP framing/auth is under test. Invalid requests must not execute TOE.
    service = CIaaSService(api_key="x" * 40)
    service.register_tenant("tenant-a")
    srv = CIaaSServer(host="127.0.0.1", port=0, service=service)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield srv
    srv.shutdown()
    srv.server_close()
    thread.join(timeout=5)


def request(server, body, length, authenticated=True, extra=None):
    conn = http.client.HTTPConnection(*server.server_address, timeout=5)
    conn.putrequest("POST", "/api/v1/ciaas/predict")
    conn.putheader("X-CIAAS-Tenant", "tenant-a")
    if authenticated:
        conn.putheader("X-CIAAS-Key", "x" * 40)
    if length is not None:
        conn.putheader("Content-Length", length)
    for key, value in extra or []:
        conn.putheader(key, value)
    conn.endheaders(body)
    response = conn.getresponse()
    status = response.status
    response.read()
    conn.close()
    return status


@pytest.mark.parametrize("length", [None, "-1", "abc", "0", "1000001"])
def test_bad_length_is_bounded_rejection(server, length):
    assert request(server, b"", length) == 400


@pytest.mark.parametrize("body", [b"null", b"[]", b"\xff", b"{", b'{"metadata":1}'])
def test_bad_body_is_400_not_handler_crash(server, body):
    assert request(server, body, str(len(body))) == 400


def test_transfer_encoding_rejected(server):
    assert request(server, b"", "0", extra=[("Transfer-Encoding", "chunked")]) == 400


def test_duplicate_length_rejected(server):
    assert request(server, b"{}", "2", extra=[("Content-Length", "2")]) == 400


def test_auth_before_body_read(server):
    assert request(server, b"", "900000", authenticated=False) == 401


def test_concurrent_limiter_never_exceeds_budget():
    limiter = RateLimiter(max_requests=5)
    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as executor:
        allowed = list(executor.map(lambda _: limiter.check("same-tenant"), range(200)))
    assert sum(allowed) == 5
    assert limiter.remaining("same-tenant") == 0
    assert limiter.check("other-tenant")


@pytest.mark.parametrize("field", ["receipt_id", "tenant_id", "payload_digest", "result_digest", "evidence_status", "receipt"])
def test_success_without_complete_receipt_is_rejected(field):
    from types import SimpleNamespace
    from toe.runtime import RuntimeResponse, RuntimeReceipt
    receipt = RuntimeReceipt("r", "tenant-a", "predict", "a"*64, "b"*64, 0.0,
                             "test", "MEASURED", True, False)
    response = RuntimeResponse(ok=True, tenant_id="tenant-a", operation="predict", receipt=receipt)
    if field == "receipt":
        response.receipt = None
    else:
        from dataclasses import replace
        response.receipt = replace(receipt, **{field: ""})
    runtime = SimpleNamespace(predict=lambda *args, **kwargs: response)
    service = CIaaSService(runtime=runtime, api_key="x"*40)
    service.register_tenant("tenant-a")
    result, status = service.handle_request("predict", {"x": 1}, "tenant-a", "x"*40)
    assert status == 502 and result.error.code == "receipt_invalid"
