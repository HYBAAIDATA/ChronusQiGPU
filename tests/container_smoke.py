"""Exercise the built container over HTTP, including a container restart."""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from uuid import UUID


def request(path, data=None, *, bearer=None, expected_status=200):
    """Require the exact HTTP outcome, including for negative authorization probes."""
    headers = {}
    if bearer is not None:
        headers["Authorization"] = f"Bearer {bearer}"
    payload = None
    if data is not None:
        headers["Content-Type"] = "application/json"
        payload = json.dumps(data).encode()
    req = urllib.request.Request(os.environ["CHRONUS_SMOKE_URL"] + path,
                                 data=payload, headers=headers)
    try:
        response = urllib.request.urlopen(req, timeout=10)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        if response.status != expected_status:
            raise AssertionError(f"{path}: expected HTTP {expected_status}, got {response.status}")
        return json.load(response)


def workload_payload(tenant="ci"):
    return {
        "tenant_id": tenant,
        "workload_type": "LUCAS_PV_SCALING",
        "representation_mode": "PV_LUCAS_COLLAPSE",
        "payload_bytes": "base64:eyJpbmRleCI6MTB9",
    }


def completed(result):
    assert result["status"] == "COMPLETED"
    assert result["tenant_id"] == "ci"
    assert result["result"]["result"]["family"] == "scaling.v1"
    assert result["result"]["result"]["sequence_value"] == "123"
    assert str(UUID(result["workload_id"])) == result["workload_id"]
    assert isinstance(result["verification_receipt"], str) and result["verification_receipt"]


def verify_receipt(handle):
    result = request("/verify/" + urllib.parse.quote(handle, safe=""))
    assert result["valid"] is True, "Receipt must verify; missing or invalid is not success"
    assert result["ed25519_verified"] is True
    assert result["reason"] == "ok"
    assert result["receipt_handle"] == handle
    assert result["metadata"]["tenant_id"] == "ci"
    assert result["metadata"]["receipt_scope"] == "workload_result_digest"
    # A local receipt is not ML-DSA, hardware, or release-qualification evidence.
    assert result["mldsa_sig"] == "NOT_EVALUATED"
    assert result["zk_stark"] == "NOT_EVALUATED"


def submit():
    token = os.environ["CHRONUS_SMOKE_TOKEN"]
    request("/workloads/submit", workload_payload(), expected_status=401)
    request("/workloads/submit", workload_payload(), bearer=token + "-invalid",
            expected_status=401)
    request("/workloads/submit", workload_payload("another-tenant"), bearer=token,
            expected_status=403)
    result = request("/workloads/submit", workload_payload(), bearer=token,
                     expected_status=202)
    completed(result)
    verify_receipt(result["verification_receipt"])
    return result["workload_id"]


def verify(workload_id):
    request(f"/workloads/{workload_id}", expected_status=401)
    result = request(f"/workloads/{workload_id}", bearer=os.environ["CHRONUS_SMOKE_TOKEN"])
    completed(result)
    assert result["workload_id"] == workload_id
    # Receipts are process-local. Only the stored computation result is restart evidence.
    print("Persisted result verified; receipt verified before restart only.", file=sys.stderr)


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "submit":
        print(submit())
    elif len(sys.argv) == 3 and sys.argv[1] == "verify":
        verify(sys.argv[2])
    else:
        raise SystemExit("Expected submit or verify <workload-id>")


if __name__ == "__main__":
    main()
