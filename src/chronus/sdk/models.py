"""Data models and errors for the Chronus Python SDK."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class ChronusSDKConfig(BaseModel):
    """SDK configuration model."""

    tenant_id: str = Field(..., description="Tenant identifier")
    access_token: str = Field(..., description="Access token")
    region: str = Field(default="us-east-1", description="Deployment region")
    endpoint: str = Field(default="internal_v1", description="API endpoint version")
    base_url: Optional[str] = Field(None, description="Custom base URL")
    timeout: float = Field(default=30.0, description="Request timeout in seconds")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    verify_ssl: bool = Field(default=True, description="Verify SSL certificates")


class WorkloadResult(BaseModel):
    """Workload submission result model."""

    workload_id: str = Field(default_factory=lambda: str(uuid4()))
    status: str = Field(default="SUBMITTED")
    workload_type: str
    representation_mode: str
    priority: str
    tenant_id: str
    region: str
    ccu_cost: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    verification_receipt: Optional[str] = None
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "workload_id": self.workload_id,
            "status": self.status,
            "workload_type": self.workload_type,
            "representation_mode": self.representation_mode,
            "priority": self.priority,
            "tenant_id": self.tenant_id,
            "region": self.region,
            "ccu_cost": self.ccu_cost,
            "result": self.result,
            "verification_receipt": self.verification_receipt,
            "submitted_at": self.submitted_at.isoformat(),
        }


class VerificationReceipt(BaseModel):
    """Signed verification receipt model."""

    receipt_id: str = Field(default_factory=lambda: str(uuid4()))
    hash_value: str
    ml_dsa_signature: Optional[str] = None
    ed25519_signature: Optional[str] = None
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "receipt_id": self.receipt_id,
            "hash_value": self.hash_value,
            "ml_dsa_signature": self.ml_dsa_signature,
            "ed25519_signature": self.ed25519_signature,
            "timestamp": self.timestamp,
            "latency_ms": self.latency_ms,
        }


# SDK Exception classes
class ChronusSDKError(Exception):
    """Base exception for Chronus SDK errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 0,
        response: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response = response or {}

    def __str__(self) -> str:
        return f"ChronusSDKError[{self.status_code}]: {self.message}"


class AuthenticationError(ChronusSDKError):
    """Authentication failed error."""

    def __init__(
        self,
        message: str = "Authentication failed",
        status_code: int = 401,
        response: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, status_code, response)


class AuthorizationError(ChronusSDKError):
    """Authorization failed error."""

    def __init__(
        self,
        message: str = "Authorization failed",
        status_code: int = 403,
        response: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, status_code, response)


class RateLimitError(ChronusSDKError):
    """Rate limit exceeded error."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        status_code: int = 429,
        retry_after: int = 60,
        response: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, status_code, response)
        self.retry_after = retry_after


class ServiceUnavailableError(ChronusSDKError):
    """Service unavailable error."""

    def __init__(
        self,
        message: str = "Service unavailable",
        status_code: int = 503,
        response: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, status_code, response)