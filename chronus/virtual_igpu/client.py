"""Fail-closed Chronus client for the Virtual iGPU ABI.

Delivery modes:
  * embedded — in-process RuntimeDaemon (default; no network)
  * local_sidecar / remote_service — HTTP JSON to wire daemon

Embedded mode works without network access and performs **no** automatic remote
discovery or cloud fallback. A failed remote request must not silently become
local execution.
"""
from __future__ import annotations

from typing import Any
import json
import os
import urllib.error
import urllib.request

from .abi import (
    ABI_VERSION,
    DeliveryMode,
    Workload,
    WorkloadResult,
)
from .runtime import RuntimeDaemon, get_embedded_daemon


class ChronusClientError(RuntimeError):
    pass


class ChronusClient:
    def __init__(
        self,
        *,
        delivery_mode: str = DeliveryMode.EMBEDDED.value,
        endpoint: str | None = None,
        timeout_s: float = 30.0,
        store: str | None = None,
        store_dir: str | None = None,
        daemon: RuntimeDaemon | None = None,
        auth_token: str | None = None,
    ) -> None:
        self.delivery_mode = str(delivery_mode)
        self.endpoint = endpoint or os.getenv("CHRONUS_VIGPU_ENDPOINT")
        self.timeout_s = float(timeout_s)
        self.store = store or store_dir
        self.auth_token = auth_token or os.getenv("CHRONUS_VIGPU_TOKEN")
        self._daemon = daemon
        if self.delivery_mode == DeliveryMode.EMBEDDED.value:
            if self._daemon is None:
                kwargs: dict[str, Any] = {}
                if self.store:
                    kwargs["root"] = self.store
                # Prefer a fresh daemon when store_dir is explicit (tests)
                if store_dir is not None:
                    self._daemon = RuntimeDaemon(root=store_dir)
                    self._daemon.attach()
                else:
                    self._daemon = get_embedded_daemon(**kwargs)
        else:
            if not self.endpoint:
                raise ChronusClientError(
                    f"{self.delivery_mode} requires endpoint= or CHRONUS_VIGPU_ENDPOINT"
                )

    def health(self) -> dict[str, Any]:
        if self.delivery_mode == DeliveryMode.EMBEDDED.value:
            assert self._daemon is not None
            return self._daemon.health()
        return self._rpc("GET", "/health")

    def submit(self, workload: Workload | dict[str, Any]) -> WorkloadResult:
        w = workload if isinstance(workload, Workload) else Workload.from_dict(workload)
        # Stamp delivery mode on workload for receipts
        if not getattr(w, "delivery_mode", None):
            w.delivery_mode = self.delivery_mode
        else:
            w.delivery_mode = self.delivery_mode
        if self.delivery_mode == DeliveryMode.EMBEDDED.value:
            assert self._daemon is not None
            return self._daemon.submit(w)
        # Remote: fail closed — no local fallback
        try:
            data = self._rpc("POST", "/submit", w.as_dict())
            return WorkloadResult.from_dict(data)
        except Exception as exc:
            raise ChronusClientError(f"remote submit failed (no local fallback): {exc}") from exc

    def poll(self, workload_id: str) -> WorkloadResult | None:
        if self.delivery_mode == DeliveryMode.EMBEDDED.value:
            assert self._daemon is not None
            return self._daemon.poll(workload_id)
        data = self._rpc("GET", f"/poll/{workload_id}")
        if data is None or data.get("status") == "pending":
            return None
        return WorkloadResult.from_dict(data)

    def cancel(self, workload_id: str) -> bool:
        if self.delivery_mode == DeliveryMode.EMBEDDED.value:
            assert self._daemon is not None
            return self._daemon.cancel(workload_id)
        data = self._rpc("POST", f"/cancel/{workload_id}", {})
        return bool(data.get("cancelled"))

    def _rpc(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        assert self.endpoint
        url = self.endpoint.rstrip("/") + path
        data = None
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        if body is not None:
            data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                raw = resp.read().decode("utf-8")
                if not raw:
                    return None
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            raise ChronusClientError(f"HTTP {exc.code}: {exc.read()[:200]!r}") from exc
        except urllib.error.URLError as exc:
            raise ChronusClientError(f"transport error: {exc}") from exc


__all__ = ["ChronusClient", "ChronusClientError", "ABI_VERSION"]
