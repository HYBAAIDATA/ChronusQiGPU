"""Fail-closed Chronus client for the Virtual iGPU ABI."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from .abi import ABI_VERSION, Workload, WorkloadResult


class VirtualIGPUClient:
    def __init__(
        self, endpoint: str, token: str | None = None, timeout: float = 30.0,
        verify_remote: bool = False,
    ):
        self.endpoint = endpoint.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.verify_remote = verify_remote

    def _request(self, method: str, path: str, value=None):
        data = None if value is None else json.dumps(value).encode()
        request = urllib.request.Request(
            self.endpoint + path, data=data, method=method,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        if self.token:
            request.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read())
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise RuntimeError(f"virtual iGPU unavailable: {exc}") from exc
        if not payload.get("ok"):
            raise RuntimeError(str(payload.get("error", "virtual iGPU request failed")))
        return payload.get("value")

    def health(self):
        value = self._request("GET", "/health")
        if value.get("protocol") != ABI_VERSION:
            raise RuntimeError("virtual iGPU ABI mismatch")
        return value

    def capabilities(self) -> set[str]:
        return set(self._request("GET", "/v1/capabilities"))

    def submit(self, workload: Workload) -> WorkloadResult:
        result = WorkloadResult.from_dict(
            self._request("POST", "/v1/workloads", workload.as_dict())
        )
        if not result.evidence_digest or not result.object_id:
            raise RuntimeError("runtime returned unpersisted or unattested result")
        if self.verify_remote:
            from .adapters import CPUEmulatorAdapter
            local = CPUEmulatorAdapter().execute(workload)
            if local.digest != result.digest:
                raise RuntimeError("remote result failed local digest verification")
        return result