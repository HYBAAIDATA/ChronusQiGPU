"""Chronus Quantum iGPU Python SDK Client.

Production-ready async/sync SDK for interacting with Chronus CIaaS services.
Supports authentication, workload submission, verification, post-quantum
signed receipts, and comprehensive error handling.
"""

import hashlib
import time
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

import httpx

from chronus.sdk.models import (
    ChronusSDKConfig,
    WorkloadResult,
    VerificationReceipt,
    ChronusSDKError,
    AuthenticationError,
    AuthorizationError,
    RateLimitError,
    ServiceUnavailableError,
)


class ChronusAPISDK:
    """Chronus Quantum iGPU SDK Client.

    Provides a production-ready interface to the Chronus CIaaS platform
    with automatic retries, authentication, rate limit handling, and
    post-quantum signed receipt verification.

    Example:
        ```python
        client = ChronusAPISDK(
            tenant_id="tenant_alpha",
            access_token="sec_token_v36",
            region="us-east-1"
        )
        job = client.submit_workload(
            payload_bytes=b"Quantum Chemistry Hamiltonian Input",
            workload_type="QUANTUM_CHEMISTRY_VQE",
            representation_mode="EXACT_Q5_RATIONAL"
        )
        ```
    """

    SDK_VERSION = "36.0.0"

    def __init__(
        self,
        tenant_id: str,
        access_token: str,
        region: str = "us-east-1",
        endpoint: str = "internal_v1",
        base_url: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        verify_ssl: bool = True,
    ) -> None:
        """Initialize the Chronus SDK client.

        Args:
            tenant_id: Tenant identifier for authentication.
            access_token: Access token for API authentication.
            region: Deployment region (default: us-east-1).
            endpoint: API endpoint version (default: internal_v1).
            base_url: Base URL for the Chronus CIaaS service.
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retry attempts.
            verify_ssl: Whether to verify SSL certificates.
        # HTTP client with connection pooling
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            verify=verify_ssl,
            headers={
                "Authorization": f"Bearer {tenant_id}:{access_token}",
                "X-Tenant-ID": tenant_id,
                "X-Region": region,
                "X-Endpoint": endpoint,
                "X-SDK-Version": self.SDK_VERSION,
                "User-Agent": f"chronus-sdk/{self.SDK_VERSION}",
            },
        )

        # Request statistics
        self._request_count = 0
        self._total_latency_ms = 0.0

    def __enter__(self) -> "ChronusAPISDK":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def close(self) -> None:
        """Close the HTTP client connection pool."""
        self._client.close()

    def _request(
        self,
        method: str,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make an authenticated HTTP request with retry logic.

        Args:
            method: HTTP method.
            path: API path.
            json: JSON body.
            params: Query parameters.

        Returns:
            Parsed JSON response.

        Raises:
            AuthenticationError: If authentication fails.
            AuthorizationError: If authorization fails.
            RateLimitError: If rate limit is exceeded.
            ServiceUnavailableError: If service is unavailable.
            ChronusSDKError: For other SDK errors.
        """
        last_exception: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                start_time = time.time()
                response = self._client.request(
                    method=method,
                    url=path,
                    json=json,
                    params=params,
                )
                latency_ms = (time.time() - start_time) * 1000
                self._request_count += 1
                self._total_latency_ms += latency_ms

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 202:
                    return response.json()
                elif response.status_code == 401:
                    raise AuthenticationError(
                        "Invalid authentication credentials",
                        status_code=401,
                        response=response.json() if response.content else {},
                    )
                elif response.status_code == 403:
                    raise AuthorizationError(
                        "Insufficient permissions",
                        status_code=403,
                        response=response.json() if response.content else {},
                    )
                elif response.status_code == 429:
                    retry_after = response.headers.get("Retry-After", "60")
                    raise RateLimitError(
                        "Rate limit exceeded",
                        status_code=429,
                        retry_after=int(retry_after) if retry_after.isdigit() else 60,
                        response=response.json() if response.content else {},
                    )
                elif response.status_code == 404:
                    raise ChronusSDKError(
                        "Resource not found",
                        status_code=404,
                        response=response.json() if response.content else {},
                    )
                elif response.status_code >= 500:
                    raise ServiceUnavailableError(
                        f"Service error: {response.status_code}",
    def submit_workload(
        self,
        payload_bytes: bytes,
        workload_type: str = "EXACT_Q5_ALGEBRAIC",
        representation_mode: str = "O1_STRUCTURAL_PV",
        priority: str = "HIGH",
        callback_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Submit a computational workload to Chronus.

        Args:
            payload_bytes: Binary payload data for computation.
            workload_type: Type of workload (default: EXACT_Q5_ALGEBRAIC).
            representation_mode: Exact algebraic representation mode.
            priority: Workload priority (LOW, MEDIUM, HIGH, CRITICAL).
            callback_url: Optional webhook for completion notification.
            metadata: Optional metadata key-value pairs.

        Returns:
            Dictionary containing workload_id, status, and ccu_cost.

        Raises:
            ChronusSDKError: If submission fails.
        """
        payload = {
            "payload_bytes": payload_bytes.decode("latin-1") if payload_bytes else "",
            "workload_type": workload_type,
            "representation_mode": representation_mode,
            "priority": priority,
            "tenant_id": self.tenant_id,
            "access_token": self.access_token,
            "region": self.region,
            "endpoint": self.endpoint,
        }

        if callback_url:
            payload["callback_url"] = callback_url
        if metadata:
            payload["metadata"] = metadata

        response = self._request("POST", "/workloads/submit", json=payload)

        return WorkloadResult(
            workload_id=response.get("workload_id", str(uuid4())),
            status=response.get("status", "SUBMITTED"),
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
        """Get the status and results of a submitted workload.

        Args:
            workload_id: Unique workload identifier.

        Returns:
            Dictionary containing workload status and results.

        Raises:
            ChronusSDKError: If the workload is not found or request fails.
        """
        response = self._request("GET", f"/workloads/{workload_id}")
        return response

    def list_workloads(
        self,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """List workloads with pagination.

        Args:
            page: Page number (1-indexed).
            page_size: Number of items per page.

        Returns:
            Paginated list of workloads.
        """
        params = {"page": page, "page_size": page_size}
        return self._request("GET", "/workloads", params=params)

    def cancel_workload(self, workload_id: str) -> None:
        """Cancel a pending or running workload.

        Args:
            workload_id: Unique workload identifier.

        Raises:
            ChronusSDKError: If cancellation fails.
        """
        self._request("DELETE", f"/workloads/{workload_id}")

    def verify_hash(
        self,
        hash_value: str,
        auth_required: bool = False,
    ) -> Dict[str, Any]:
        """Verify a hash value via the zero-auth verify endpoint.

        Per Invariant I7: /verify/{hash} returns {valid: true} with no auth required.

        Args:
            hash_value: Hash value to verify.
            auth_required: Whether to include authentication token.

        Returns:
            Verification result dictionary.
        """
        headers = {}
        if auth_required:
            headers["Authorization"] = f"Bearer {self.tenant_id}:{self.access_token}"

        response = self._client.get(
            f"/verify/{hash_value}",
            headers=headers,
        )

        if response.status_code == 200:
            return response.json()
        else:
            raise ChronusSDKError(
                f"Verification failed: {response.status_code}",
                status_code=response.status_code,
                response=response.json() if response.content else {},
            )

    def get_health(self) -> Dict[str, Any]:
        """Get service health status.

        Returns:
            Health status dictionary with component details.
        """
        return self._request("GET", "/health")

    def get_metrics(self) -> str:
        """Get Prometheus-formatted metrics.

        Returns:
            Metrics in Prometheus text format.
        """
        response = self._client.get("/metrics")
        if response.status_code == 200:
            return response.text
        raise ChronusSDKError(
            f"Metrics unavailable: {response.status_code}",
            status_code=response.status_code,
            response={},
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get SDK client statistics.

        Returns:
            Dictionary with request count and total latency.
        """
        avg_latency = (
            self._total_latency_ms / self._request_count
            if self._request_count > 0
            else 0.0
        )
        return {
            "sdk_version": self.SDK_VERSION,
            "tenant_id": self.tenant_id,
            "region": self.region,
            "request_count": self._request_count,
            "total_latency_ms": round(self._total_latency_ms, 3),
            "average_latency_ms": round(avg_latency, 3),
        }
                        status_code=response.status_code,
                        response=response.json() if response.content else {},
                    )
                else:
                    raise ChronusSDKError(
                        f"Unexpected response: {response.status_code}",
                        status_code=response.status_code,
                        response=response.json() if response.content else {},
                    )

            except (AuthenticationError, AuthorizationError, RateLimitError):
                raise
            except ServiceUnavailableError as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                raise
            except httpx.RequestError as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise ChronusSDKError(
                    f"Request failed: {str(e)}",
                    status_code=0,
                    response={},
                )

        if last_exception:
            raise last_exception
        raise ChronusSDKError("Max retries exceeded", status_code=0, response={})
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required")
        if not access_token or not access_token.strip():
            raise ValueError("access_token is required")

        self.tenant_id = tenant_id.strip()
        self.access_token = access_token.strip()
        self.region = region
        self.endpoint = endpoint
        self.base_url = base_url or f"https://chronus-api.{region}.chronus-systems.com"
        self.timeout = timeout
        self.max_retries = max_retries
        self.verify_ssl = verify_ssl