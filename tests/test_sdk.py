import httpx
import pytest
from fastapi.testclient import TestClient

from chronus.sdk.client import ChronusAPISDK
from chronus.sdk.models import ServiceUnavailableError
from chronus.service.app import create_app
from chronus.service.dependencies import auth_service, service_config
from chronus.service.routers import workloads
from chronus.service.workload_store import SQLiteWorkloadStore


def _sdk_with_transport(handler):
    sdk = ChronusAPISDK(
        tenant_id="sdk-test",
        access_token="sdk-test-token",
        base_url="https://chronus.test",
    )
    headers = sdk._client.headers.copy()
    sdk.close()
    sdk._client = httpx.Client(
        base_url="https://chronus.test",
        transport=httpx.MockTransport(handler),
        headers=headers,
    )
    return sdk


def test_sdk_submits_and_retrieves_workload_through_service(tmp_path, monkeypatch):
    monkeypatch.setattr(service_config, "execution_backend_url", None)
    monkeypatch.setattr(
        workloads, "workload_store", SQLiteWorkloadStore(str(tmp_path / "test.sqlite3"))
    )
    auth_service.register_tenant("sdk-test", "sdk-test-token")
    service = TestClient(create_app())

    def forward(request):
        response = service.request(
            request.method,
            request.url.path,
            headers=dict(request.headers),
            content=request.content,
        )
        return httpx.Response(
            response.status_code,
            headers=response.headers,
            content=response.content,
            request=request,
        )

    sdk = _sdk_with_transport(forward)
    try:
        submitted = sdk.submit_workload(
            b'{"index":10}',
            workload_type="LUCAS_PV_SCALING",
            representation_mode="PV_LUCAS_COLLAPSE",
            backend_preference="python-math-reference",
        )
        retrieved = sdk.get_workload_status(submitted["workload_id"])
    finally:
        sdk.close()

    assert submitted["status"] == "COMPLETED"
    assert submitted["result"]["result"]["family"] == "scaling.v1"
    assert submitted["result"]["result"]["sequence_value"] == "123"
    assert retrieved["workload_id"] == submitted["workload_id"]


def test_sdk_does_not_retry_workload_submission_after_server_error():
    requests = []

    def fail(request):
        requests.append(request)
        return httpx.Response(503, json={"error": "unavailable"}, request=request)

    sdk = _sdk_with_transport(fail)
    try:
        with pytest.raises(ServiceUnavailableError):
            sdk.submit_workload(b'{"index":10}', workload_type="LUCAS_PV_SCALING")
    finally:
        sdk.close()

    assert len(requests) == 1


def test_sdk_accepts_no_content_cancel_response():
    def no_content(request):
        return httpx.Response(204, request=request)

    sdk = _sdk_with_transport(no_content)
    try:
        assert sdk.cancel_workload("00000000-0000-0000-0000-000000000001") is None
    finally:
        sdk.close()
