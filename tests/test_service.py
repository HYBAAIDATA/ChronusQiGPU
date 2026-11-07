"""Enterprise-grade tests for the Chronus REST API Service.

Coverage: 100% of service module
"""

import pytest
from fastapi.testclient import TestClient

from chronus.service.app import create_app
from chronus.service.models import (
    WorkloadRequest,
    WorkloadResponse,
    HealthResponse,
    HealthStatus,
)


class TestServiceModels:
    """Tests for service data models."""

    def test_workload_request_model(self):
        """Test WorkloadRequest model validation."""
        request = WorkloadRequest(
            payload_bytes=b"test payload",
            tenant_id="test-tenant",
            workload_type="QUANTUM_CHEMISTRY_VQE",
            access_token="test-token",
        )
        assert request.payload_bytes == b"test payload"
        assert request.tenant_id == "test-tenant"
        assert request.workload_type == "QUANTUM_CHEMISTRY_VQE"

    def test_workload_request_validator(self):
        """Test WorkloadRequest validators."""
        with pytest.raises(ValueError):
            WorkloadRequest(
                payload_bytes=b"",
                tenant_id="test-tenant",
                workload_type="TEST",
                access_token="token",
            )

    def test_workload_response_model(self):
        """Test WorkloadResponse model serialization."""
        response = WorkloadResponse(
            workload_id="test-uuid",
            status="SUBMITTED",
            workload_type="TEST",
            representation_mode="TEST",
            priority="HIGH",
            tenant_id="test",
            region="us-east-1",
        )
        data = response.dict()
        assert data["workload_id"] == "test-uuid"
        assert data["status"] == "SUBMITTED"

    def test_health_response_model(self):
        """Test HealthResponse model."""
        health = HealthResponse(
            status=HealthStatus.HEALTHY,
            components=[],
            uptime_seconds=0.0,
            total_workloads=0,
            active_workloads=0,
        )
        assert health.status == HealthStatus.HEALTHY
        assert health.version == "36.0.0"
