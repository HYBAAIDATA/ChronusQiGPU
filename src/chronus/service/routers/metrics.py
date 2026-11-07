"""Prometheus-format metrics derived from process-local observations."""

import time

from fastapi import APIRouter, Depends, Response

from chronus.service.dependencies import get_current_tenant
from chronus.service.routers.workloads import workload_counts

router = APIRouter(prefix="/metrics", tags=["metrics"])

_METRICS_START_TIME = time.time()


@router.get(
    "",
    response_class=Response,
    summary="Prometheus metrics endpoint",
    description="Returns Prometheus-formatted metrics for monitoring and alerting.",
)
async def get_metrics(
    tenant_id: str = Depends(get_current_tenant),
) -> Response:
    """Prometheus metrics derived from process-local observations."""
    uptime = time.time() - _METRICS_START_TIME
    total_workloads, active_workloads = workload_counts()

    metrics_lines = [
        "# HELP chronus_uptime_seconds Service uptime in seconds",
        "# TYPE chronus_uptime_seconds gauge",
        f"chronus_uptime_seconds {uptime:.3f}",
        "",
        "# HELP chronus_workloads_total Workloads retained by this process",
        "# TYPE chronus_workloads_total gauge",
        f"chronus_workloads_total {total_workloads}",
        "# HELP chronus_workloads_active Workloads in an active lifecycle state",
        "# TYPE chronus_workloads_active gauge",
        f"chronus_workloads_active {active_workloads}",
    ]

    return Response(
        content="\n".join(metrics_lines) + "\n",
        media_type="text/plain",
    )