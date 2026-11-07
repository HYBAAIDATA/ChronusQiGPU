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
            if method.upper() in {"GET", "PUT", "PATCH", "DELETE"}
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

            if response.status_code in (200, 201, 202, 204):
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

    def instant_onboard_tenant(self, onboarding_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Trigger Zero-Friction instant tenant provisioning (<30s T0 SLA)."""
        return self._request("POST", "/v1/tenants/onboard/instant", json=onboarding_payload)

    def expand_capacity(
        self,
        requested_warp_capacity: int,
        expand_storage_gb: Optional[int] = None,
        reason: str = "SDK_SELF_SERVICE_EXPANSION",
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Dynamically expand active warps or storage under Enduring Capacity Addendum."""
        target_tenant = tenant_id or self.tenant_id
        payload: Dict[str, Any] = {
            "requested_warp_capacity": requested_warp_capacity,
            "reason": reason,
        }
        if expand_storage_gb is not None:
            payload["expand_storage_gb"] = expand_storage_gb
        return self._request("PATCH", f"/v1/tenants/{target_tenant}/capacity", json=payload)

    def get_capacity_status(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Retrieve Enduring Capacity Addendum and real-time Hermiten settlement status."""
        target_tenant = tenant_id or self.tenant_id
        return self._request("GET", f"/v1/tenants/{target_tenant}/capacity")

    def list_connector_specs(self) -> Dict[str, Any]:
        """Retrieve pre-built Zero-Copy Connector specifications and T3-T5 Data Movement Plane."""
        return self._request("GET", "/v1/connectors/specs")

    def authorize_eca(
        self,
        kms_provider: str = "AWS_KMS",
        kms_key_arn: Optional[str] = None,
        auto_schema_discovery: bool = True,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Authorize Tenant Enduring Capacity Addendum (ECA) & Customer KMS/PKCS#11 custody."""
        target_tenant = tenant_id or self.tenant_id
        payload: Dict[str, Any] = {
            "kms_provider": kms_provider,
            "auto_schema_discovery": auto_schema_discovery,
        }
        if kms_key_arn is not None:
            payload["kms_key_arn"] = kms_key_arn
        return self._request("POST", f"/v1/connectors/eca/{target_tenant}/authorize", json=payload)

    def register_connector(
        self,
        *,
        name: str,
        connector_type: str,
        endpoint_uri: str,
        source_region: str = "eu-west-2",
        pod_region: str = "eu-west-2",
        kms_provider: str = "AWS_KMS",
        kms_key_arn: Optional[str] = None,
        co_located: bool = False,
        access_class_override: Optional[str] = None,
        auto_discover: bool = True,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Bind a Day-1 Zero-Copy Native Representation Connector to client data at rest."""
        payload: Dict[str, Any] = {
            "tenant_id": tenant_id or self.tenant_id,
            "name": name,
            "connector_type": connector_type,
            "endpoint_uri": endpoint_uri,
            "source_region": source_region,
            "pod_region": pod_region,
            "kms_provider": kms_provider,
            "co_located": co_located,
            "auto_discover": auto_discover,
        }
        if kms_key_arn is not None:
            payload["kms_key_arn"] = kms_key_arn
        if access_class_override is not None:
            payload["access_class_override"] = access_class_override
        return self._request("POST", "/v1/connectors", json=payload)

    def list_connectors(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """List bound Zero-Copy Native Representation Connectors."""
        params: Optional[Dict[str, Any]] = {"tenant_id": tenant_id} if tenant_id else None
        return self._request("GET", "/v1/connectors", params=params)

    def ingest_zero_copy(
        self,
        connector_id: str,
        payload_bytes: bytes,
        *,
        object_path: str = "part-00000.parquet",
        byte_offset: int = 0,
        format_hint: Optional[str] = None,
        encrypt_with_customer_kms: bool = False,
        simulate_adversarial: bool = False,
    ) -> Dict[str, Any]:
        """Ingest external block via Binet-Zeckendorf Fold & return ptr_ovid_<hash> pointer."""
        if not payload_bytes:
            raise ValueError("payload_bytes cannot be empty")
        body: Dict[str, Any] = {
            "payload_b64": "base64:" + base64.b64encode(payload_bytes).decode("ascii"),
            "object_path": object_path,
            "byte_offset": byte_offset,
            "encrypt_with_customer_kms": encrypt_with_customer_kms,
            "simulate_adversarial": simulate_adversarial,
        }
        if format_hint is not None:
            body["format_hint"] = format_hint
        return self._request("POST", f"/v1/connectors/{connector_id}/ingest", json=body)

    def discover_connector_schemas(
        self,
        connector_id: str,
        additional_tables: Optional[list[str]] = None,
    ) -> Dict[str, Any]:
        """Run Automated Schema Discovery Middleware under Tenant ECA."""
        body: Dict[str, Any] = {}
        if additional_tables is not None:
            body["additional_tables"] = additional_tables
        return self._request("POST", f"/v1/connectors/{connector_id}/discover", json=body)

    def execute_zero_copy_pointer(
        self,
        pointer_id: str,
        operation: str = "PV_LATTICE_FOLD",
        scale_order: int = 8,
        metallic_m: int = 1,
    ) -> Dict[str, Any]:
        """Execute exact algebraic computation directly against ptr_ovid_<hash>."""
        return self._request(
            "POST",
            f"/v1/connectors/pointers/{pointer_id}/execute",
            json={
                "operation": operation,
                "scale_order": scale_order,
                "metallic_m": metallic_m,
            },
        )

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
