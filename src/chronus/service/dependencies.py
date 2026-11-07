"""Dependency injection for the Chronus REST API Service.

Provides authentication, authorization, rate limiting, and database
session dependencies for all route handlers.
"""

import time
import os
import json
from collections import defaultdict
from typing import Dict, Optional
from uuid import uuid4

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from chronus.service.models import ErrorResponse


# Security scheme
security = HTTPBearer(auto_error=False)


class ServiceConfig:
    """Runtime service configuration."""

    def __init__(self) -> None:
        self.max_workloads_per_tenant: int = 1000
        self.rate_limit_requests_per_minute: int = 600
        self.rate_limit_burst: int = 100
        self.max_payload_size_mb: int = 100
        self.default_region: str = "us-east-1"
        self.enable_post_quantum: bool = False
        self.enable_zero_auth_verify: bool = True
        self.execution_backend_url: Optional[str] = os.getenv(
            "CHRONUS_EXECUTION_BASE_URL"
        )


class RateLimiter:
    """Token bucket rate limiter per tenant."""

    def __init__(
        self, requests_per_minute: int = 600, burst: int = 100
    ) -> None:
        self.requests_per_minute = requests_per_minute
        self.burst = burst
        self._buckets: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {
                "tokens": float(burst),
                "last_refill": time.monotonic(),
            }
        )

    def check(self, tenant_id: str) -> bool:
        """Check if a request is allowed for the given tenant.

        Returns True if allowed, False if rate limited.
        """
        now = time.monotonic()
        bucket = self._buckets[tenant_id]

        # Refill tokens
        elapsed = now - bucket["last_refill"]
        refill_amount = elapsed * (self.requests_per_minute / 60.0)
        bucket["tokens"] = min(self.burst, bucket["tokens"] + refill_amount)
        bucket["last_refill"] = now

        if bucket["tokens"] >= 1.0:
            bucket["tokens"] -= 1.0
            return True

        return False


class AuthService:
    """Authentication and authorization service."""

    def __init__(self) -> None:
        self._tokens: Dict[str, Dict[str, str]] = {}
        self._rate_limiter = RateLimiter()
        configured_tokens = os.getenv("CHRONUS_TENANT_TOKENS", "{}")
        try:
            tenant_tokens = json.loads(configured_tokens)
        except json.JSONDecodeError as exc:
            raise ValueError("CHRONUS_TENANT_TOKENS must be a JSON object") from exc
        if not isinstance(tenant_tokens, dict):
            raise ValueError("CHRONUS_TENANT_TOKENS must be a JSON object")
        for tenant_id, token in tenant_tokens.items():
            self.register_tenant(tenant_id, token)

    def authenticate(
        self, credentials: Optional[HTTPAuthorizationCredentials]
    ) -> Optional[str]:
        """Authenticate a request using Bearer token.

        Returns tenant_id if authenticated, None otherwise.
        Supports zero-auth mode for /verify endpoint.
        """
        if credentials is None:
            return None

        token = credentials.credentials
        if token in self._tokens:
            return self._tokens[token].get("tenant_id")

        return None

    def check_rate_limit(self, tenant_id: Optional[str]) -> None:
        """Enforce rate limiting for authenticated tenants."""
        if tenant_id is None:
            # Zero-auth requests get minimal allowance
            return

        if not self._rate_limiter.check(tenant_id):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=ErrorResponse(
                    error="rate_limit_exceeded",
                    error_code="RL001",
                    message="Too many requests. Please slow down.",
                ).model_dump(),
            )

    def register_tenant(self, tenant_id: str, access_token: str) -> None:
        """Register a new tenant with an access token."""
        if not tenant_id or not tenant_id.strip() or not access_token:
            raise ValueError("tenant_id and access_token must be non-empty")
        existing = self._tokens.get(access_token)
        if existing and existing["tenant_id"] != tenant_id:
            raise ValueError("access_token is already assigned to another tenant")
        self._tokens[access_token] = {"tenant_id": tenant_id}


# Global service instances
service_config = ServiceConfig()
auth_service = AuthService()


def get_service_config() -> ServiceConfig:
    """Dependency for service configuration."""
    return service_config


def get_auth_service() -> AuthService:
    """Dependency for authentication service."""
    return auth_service


def get_current_tenant(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    auth: AuthService = Depends(get_auth_service),
) -> Optional[str]:
    """Extract and authenticate the current tenant from request.

    Supports zero-auth mode for public verify endpoints.
    Requires authentication for workload submission endpoints.
    """
    tenant_id = auth.authenticate(credentials)

    # Check rate limit
    auth.check_rate_limit(tenant_id)

    # For workload submission, require authentication
    protected_operation = request.method in ("POST", "PUT", "DELETE")
    protected_resource = request.url.path.startswith(
        ("/workloads", "/verify/receipt")
    )
    if tenant_id is None and (protected_operation or protected_resource):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorResponse(
                error="authentication_required",
                error_code="AUTH001",
                message="Valid authentication token required for this operation.",
            ).model_dump(),
        )

    return tenant_id


def get_request_id(request: Request) -> str:
    """Generate or extract a unique request ID."""
    request_id = request.headers.get("X-Request-ID")
    if not request_id:
        request_id = str(uuid4())
    return request_id