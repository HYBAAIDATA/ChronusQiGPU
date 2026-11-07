"""Exercise the built container over HTTP, including a container restart."""

import json
import os
import sys
import urllib.request


base_url = os.environ["CHRONUS_SMOKE_URL"]
token = os.environ["CHRONUS_SMOKE_TOKEN"]


def request(path, data=None):
    headers = {"Authorization": f"Bearer {token}"}
    payload = None
    if data is not None:
        headers["Content-Type"] = "application/json"
        payload = json.dumps(data).encode()
    req = urllib.request.Request(base_url + path, data=payload, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.load(response)


if sys.argv[1] == "submit":
    result = request(
        "/workloads/submit",
        {
            "tenant_id": "ci",
            "workload_type": "LUCAS_PV_SCALING",
            "representation_mode": "PV_LUCAS_COLLAPSE",
            "payload_bytes": "base64:eyJpbmRleCI6MTB9",
        },
    )
    assert result["status"] == "COMPLETED"
    assert result["result"]["result"]["lucas"] == "123"
    print(result["workload_id"])
elif sys.argv[1] == "verify":
    result = request(f"/workloads/{sys.argv[2]}")
    assert result["status"] == "COMPLETED"
    assert result["result"]["result"]["lucas"] == "123"
else:
    raise SystemExit("Expected submit or verify")
