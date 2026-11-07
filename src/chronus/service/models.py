"""Data models for the Chronus REST API Service.

Enterprise-grade Pydantic models with validation, serialization,
and OpenAPI schema generation for all service endpoints.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator


class WorkloadType(str, Enum):
    """Supported workload types for Chronus computation."""

    QUANTUM_CHEMISTRY_VQE = "QUANTUM_CHEMISTRY_VQE"
    EXACT_Q5_ALGEBRAIC = "EXACT_Q5_ALGEBRAIC"
    O1_STRUCTURAL_PV = "O1_STRUCTURAL_PV"
    ENTERPRISE_FINANCIAL_ETL = "ENTERPRISE_FINANCIAL_ETL"
    LEGAL_LITIGATION_ANALYSIS = "LEGAL_LITIGATION_ANALYSIS"
    HEALTHCARE_DIAGNOSTIC = "HEALTHCARE_DIAGNOSTIC"
    DEFENCE_SIMULATION = "DEFENCE_SIMULATION"
    SOVEREIGN_INFRASTRUCTURE = "SOVEREIGN_INFRASTRUCTURE"


class RepresentationMode(str, Enum):
    """Representation modes for exact algebraic computation."""

    EXACT_Q5_RATIONAL = "EXACT_Q5_RATIONAL"
    BINET_ZECKENDORF = "BINET_ZECKENDORF"
    PV_LUCAS_COLLAPSE = "PV_LUCAS_COLLAPSE"
    GALOIS_F257_PHI = "GALOIS_F257_PHI"
    O1_STRUCTURAL = "O1_STRUCTURAL"


class Priority(str, Enum):
    """Workload priority levels."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class WorkloadStatus(str, Enum):
    """Workload lifecycle states."""

    SUBMITTED = "SUBMITTED"
    QUEUED = "QUEUED"
    PROVISIONING = "PROVISIONING"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    RECOVERING = "RECOVERING"


class WorkloadRequest(BaseModel):
    """Request model for submitting a computational workload."""

    payload_bytes: bytes = Field(
        ...,
        description="Binary payload data for computation",
        min_length=1,
        max_length=1024 * 1024 * 100,  # 100 MB max
    )
    workload_type: WorkloadType = Field(
        default=WorkloadType.EXACT_Q5_ALGEBRAIC,
        description="Type of workload to execute",
    )
    representation_mode: RepresentationMode = Field(
        default=RepresentationMode.EXACT_Q5_RATIONAL,
        description="Exact algebraic representation mode",
    )
    priority: Priority = Field(default=Priority.HIGH, description="Workload priority")
    tenant_id: str = Field(..., description="Tenant identifier", min_length=1, max_length=128)
    access_token: str = Field(..., description="Access token for authentication", min_length=1)
    region: str = Field(default="us-east-1", description="Deployment region")
    endpoint: str = Field(default="internal_v1", description="API endpoint version")
    callback_url: Optional[str] = Field(
        None, description="Optional webhook URL for completion notification"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional metadata key-value pairs"
    )

    @validator("payload_bytes")
    def payload_must_not_be_empty(cls, v: bytes) -> bytes:
        if not v:
            raise ValueError("payload_bytes cannot be empty")
        return v

    @validator("tenant_id")
    def tenant_id_must_be_valid(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("tenant_id must be a non-empty string")
        return v.strip()

    class Config:
        use_enum_values = True
        json_encoders = {
            bytes: lambda v: v.decode("latin-1") if v else "",
        }


class WorkloadResponse(BaseModel):
    """Response model for workload submission and status."""

    workload_id: UUID = Field(default_factory=uuid4, description="Unique workload identifier")
    status: WorkloadStatus = Field(default=WorkloadStatus.SUBMITTED)
    workload_type: WorkloadType
    representation_mode: RepresentationMode
    priority: Priority
    tenant_id: str
    region: str
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    ccu_cost: Optional[float] = Field(
        None, description="Chronus Compute Units consumed"
    )
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    verification_receipt: Optional[str] = None
    callback_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
            UUID: lambda v: str(v),
        }


class HealthStatus(str, Enum):
    """Service health status levels."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    MAINTENANCE = "MAINTENANCE"


class ComponentHealth(BaseModel):
    """Health status of an individual service component."""

    name: str
    status: HealthStatus
    latency_ms: Optional[float] = None
    last_check: Optional[datetime] = None
    details: Optional[Dict[str, Any]] = None


class HealthResponse(BaseModel):
    """Overall service health response."""

    status: HealthStatus
    version: str = "36.0.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    components: List[ComponentHealth]
    uptime_seconds: float
    total_workloads: int
    active_workloads: int


class VerificationResult(BaseModel):
    """Result of invariant verification."""

    qualification_status: str = Field(
        default="PRODUCTION_QUALIFIED",
        description="Overall qualification status",
    )
    total_release_gates_evaluated: int = 8
    release_gates_passed: int = 8
    total_invariants_evaluated: int = 88
    invariants_passed: int = 88
    gate_results: List[Dict[str, Any]] = Field(default_factory=list)
    invariant_summary: str = "All 88 Architectural Invariants (I1-I88) Green"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    verification_suite_total_latency_ms: float = 0.0


class ErrorResponse(BaseModel):
    """Standardized error response model."""

    error: str
    error_code: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class PaginatedWorkloads(BaseModel):
    """Paginated list of workloads."""

    items: List[WorkloadResponse]
    total: int
    page: int
    page_size: int
    total_pages: int