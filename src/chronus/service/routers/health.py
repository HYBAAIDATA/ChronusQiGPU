"""Health check API routes."""

import time
from typing import List

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from chronus.execution import execution_router
from chronus.execution.qigpu import QiGPUOrchestrator
from chronus.service.dependencies import get_current_tenant, get_service_config
from chronus.service.routers.workloads import workload_counts
from chronus.service.models import (
    ComponentHealth,
    HealthResponse,
    HealthStatus,
)

router = APIRouter(prefix="/health", tags=["health"])

_SERVICE_START_TIME = time.time()


@router.get(
    "",
    response_model=HealthResponse,
    summary="Get service health status",
    description="Returns overall service health with component-level details, "
    "uptime, and workload statistics.",
)
async def get_health(
    tenant_id: str = Depends(get_current_tenant),
    config=Depends(get_service_config),
) -> HealthResponse:
    """Report observed API health and execution backend configuration."""
    _uptime = time.time() - _SERVICE_START_TIME
    total_workloads, active_workloads = workload_counts()
    remote_backend_status = await _remote_backend_status(config.execution_backend_url)
    if config.execution_backend_url:
        backend_status = (
            HealthStatus.HEALTHY
            if remote_backend_status["healthy"]
            else HealthStatus.UNHEALTHY
        )
        backend_details = {
            "mode": "remote-adapter",
            "configured": True,
            "health_status_code": remote_backend_status["status_code"],
        }
    else:
        backend_status = HealthStatus.HEALTHY
        backend_details = {
            "mode": "native-reference",
            "registered_backends": execution_router.list_backends(),
            "qigpu": QiGPUOrchestrator(execution_router).inventory(),
        }
    components: List[ComponentHealth] = [
        ComponentHealth(
            name="api_process",
            status=HealthStatus.HEALTHY,
            details={"version": "36.0.0"},
        ),
        ComponentHealth(
            name="execution_backend",
            status=backend_status,
            details=backend_details,
        ),
    ]
    overall_status = backend_status

    return HealthResponse(
        status=overall_status,
        components=components,
        uptime_seconds=round(_uptime, 3),
        total_workloads=total_workloads,
        active_workloads=active_workloads,
    )


@router.get(
    "/live",
    summary="Kubernetes liveness probe",
    description="Simple liveness check for container orchestration.",
)
async def liveness_probe() -> dict:
    """Liveness probe for Kubernetes."""
    return {"status": "alive", "timestamp": time.time()}


@router.get(
    "/ready",
    summary="Kubernetes readiness probe",
    description="Readiness check for container orchestration.",
)
async def readiness_probe() -> dict:
    """Readiness for accepting workload execution."""
    config = get_service_config()
    remote_status = await _remote_backend_status(config.execution_backend_url)
    if config.execution_backend_url and not remote_status["healthy"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "not_ready",
                "reason": "execution adapter health check failed",
            },
        )
    return {
        "status": "ready",
        "service": "chronus-quantum-igpu",
        "version": "36.0.0",
        "execution_mode": (
            "remote-adapter" if config.execution_backend_url else "native-reference"
        ),
    }


async def _remote_backend_status(url: str | None) -> dict:
    if not url:
        return {"healthy": True, "status_code": None}
    try:
        async with httpx.AsyncClient(base_url=url.rstrip("/"), timeout=2.0) as client:
            response = await client.get("/health/ready")
    except httpx.RequestError:
        return {"healthy": False, "status_code": None}
    return {
        "healthy": 200 <= response.status_code < 300,
        "status_code": response.status_code,
    }
