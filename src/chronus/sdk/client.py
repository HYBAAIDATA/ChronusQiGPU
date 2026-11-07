"""HTTP client for the Chronus workload service."""

import base64
import os
import time
from typing import Any, Dict, Optional
from uuid import UUID

import httpx

from chronus.sdk.models import (
    AuthenticationError,
    AuthorizationError,
    ChronusSDKError,
    RateLimitError,
    ServiceUnavailableError,
    WorkloadResult,
)


class ChronusAPISDK:
    """Synchronous client for a separately deployed Chronus API."""

    SDK_VERSION = "36.0.0"

    def __init__(
        self,
        tenant_id: str,
        access_token: str,
        region: str = "us-east-1",
        endpoint: str = "v1",
        base_url: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        verify_ssl: bool = True,
    ) -> None:
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required")
        if not access_token or not access_token.strip():
            raise ValueError("access_token is required")
        resolved_url = base_url or os.getenv("CHRONUS_API_URL")
        if not resolved_url:
            raise ValueError("base_url or CHRONUS_API_URL is required")
        if timeout <= 0 or max_retries < 1:
            raise ValueError("timeout and max_retries must be positive")

        self.tenant_id = tenant_id.strip()
        self.access_token = access_token.strip()
        self.region = region
        self.endpoint = endpoint
        self.base_url = resolved_url.rstrip("/")
        self.max_retries = max_retries
        self._request_count = 0
        self._total_latency_ms = 0.0
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            verify=verify_ssl,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "X-Tenant-ID": self.tenant_id,
                "X-Region": self.region,
                "X-Endpoint": self.endpoint,
                "X-SDK-Version": self.SDK_VERSION,
                "User-Agent": f"chronus-sdk/{self.SDK_VERSION}",
            },
        )

    def __enter__(self) -> "ChronusAPISDK":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _request(
        self,
        method: str,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        attempts = (
            self.max_retries
            if method.upper() in {"GET", "PUT", "DELETE"}
            else 1
        )
        for attempt in range(attempts):
            started = time.perf_counter()
            try:
                response = self._client.request(
                    method, path, json=json, params=params
                )
            except httpx.RequestError as exc:
                if attempt + 1 == attempts:
                    raise ServiceUnavailableError(
                        "Chronus API request failed", status_code=0
                    ) from exc
                time.sleep(min(2**attempt, 8))
                continue

            self._request_count += 1
            self._total_latency_ms += (time.perf_counter() - started) * 1000
            body: Dict[str, Any]
            try:
                decoded = response.json()
                body = decoded if isinstance(decoded, dict) else {"data": decoded}
            except ValueError:
                body = {}

            if response.status_code in (200, 202, 204):
                return body
            if response.status_code == 401:
                raise AuthenticationError(response=body)
            if response.status_code == 403:
                raise AuthorizationError(response=body)
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "60")
                raise RateLimitError(
                    retry_after=int(retry_after) if retry_after.isdigit() else 60,
                    response=body,
                )
            if response.status_code >= 500:
                error = ServiceUnavailableError(
                    f"Chronus API returned HTTP {response.status_code}",
                    status_code=response.status_code,
                    response=body,
                )
                if attempt + 1 < attempts:
                    time.sleep(min(2**attempt, 8))
                    continue
                raise error
            raise ChronusSDKError(
                f"Chronus API returned HTTP {response.status_code}",
                status_code=response.status_code,
                response=body,
            )
        raise ServiceUnavailableError("Chronus API request attempts exhausted")

    def submit_workload(
        self,
        payload_bytes: bytes,
        workload_type: str = "EXACT_Q5_ALGEBRAIC",
        representation_mode: str = "EXACT_Q5_RATIONAL",
        priority: str = "HIGH",
        callback_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        backend_preference: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not payload_bytes:
            raise ValueError("payload_bytes cannot be empty")
        payload: Dict[str, Any] = {
            "payload_bytes": "base64:"
            + base64.b64encode(payload_bytes).decode("ascii"),
            "workload_type": workload_type,
            "representation_mode": representation_mode,
            "priority": priority,
            "tenant_id": self.tenant_id,
            "region": self.region,
            "endpoint": self.endpoint,
        }
        if callback_url:
            payload["callback_url"] = callback_url
        if metadata:
            payload["metadata"] = metadata
        if backend_preference:
            payload["backend_preference"] = backend_preference

        response = self._request("POST", "/workloads/submit", json=payload)
        workload_id = response.get("workload_id")
        state = response.get("status")
        if not isinstance(workload_id, str) or not isinstance(state, str):
            raise ChronusSDKError(
                "Chronus API response is missing workload_id or status",
                status_code=502,
                response=response,
            )
        try:
            UUID(workload_id)
        except ValueError as exc:
            raise ChronusSDKError(
                "Chronus API returned an invalid workload_id",
                status_code=502,
                response=response,
            ) from exc

        return WorkloadResult(
            workload_id=workload_id,
            status=state,
            workload_type=workload_type,
            representation_mode=representation_mode,
            priority=priority,
            tenant_id=self.tenant_id,
            region=self.region,
            ccu_cost=response.get("ccu_cost"),
            result=response.get("result"),
            verification_receipt=response.get("verification_receipt"),
        ).to_dict()

    def get_workload_status(self, workload_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/workloads/{workload_id}")

    def list_workloads(self, page: int = 1, page_size: int = 50) -> Dict[str, Any]:
        return self._request(
            "GET",
            "/workloads",
            params={"page": page, "page_size": page_size},
        )

    def cancel_workload(self, workload_id: str) -> None:
        self._request("DELETE", f"/workloads/{workload_id}")

    def verify_hash(self, hash_value: str) -> Dict[str, Any]:
        return self._request("GET", f"/verify/{hash_value}")

    def get_health(self) -> Dict[str, Any]:
        return self._request("GET", "/health")

    def get_metrics(self) -> str:
        response = self._client.get("/metrics")
        if response.status_code != 200:
            raise ChronusSDKError(
                "Chronus metrics endpoint failed",
                status_code=response.status_code,
            )
        return response.text

    def get_stats(self) -> Dict[str, Any]:
        average = (
            self._total_latency_ms / self._request_count
            if self._request_count
            else 0.0
        )
        return {
            "sdk_version": self.SDK_VERSION,
            "tenant_id": self.tenant_id,
            "region": self.region,
            "request_count": self._request_count,
            "total_latency_ms": round(self._total_latency_ms, 3),
            "average_latency_ms": round(average, 3),
        }
