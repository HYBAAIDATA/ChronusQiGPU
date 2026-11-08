"""Prometheus-format metrics derived from process-local observations and telemetry registry."""

from fastapi import APIRouter, Depends, Response

from chronus.service.dependencies import get_current_tenant
from chronus.service.routers.workloads import workload_counts
from chronus.service.telemetry import metrics_registry

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get(
    "",
    response_class=Response,
    summary="Prometheus metrics endpoint",
    description="Returns Prometheus-formatted metrics for monitoring and alerting.",
)
async def get_metrics(
    tenant_id: str = Depends(get_current_tenant),
) -> Response:
    """Prometheus metrics derived from process-local observations and telemetry registry."""
    total_workloads, active_workloads = workload_counts()
    metrics_content = metrics_registry.render_metrics(
        total_workloads=total_workloads,
        active_workloads=active_workloads,
    )
    return Response(
        content=metrics_content,
        media_type="text/plain",
    )
