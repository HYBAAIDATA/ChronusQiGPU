"""API route routers for the Chronus REST Service."""

from chronus.service.routers.workloads import router as workloads_router
from chronus.service.routers.verify import router as verify_router
from chronus.service.routers.health import router as health_router
from chronus.service.routers.metrics import router as metrics_router
from chronus.service.routers.console import router as console_router
from chronus.service.routers.billing import router as billing_router
from chronus.service.routers.v1 import router as v1_router
from chronus.service.routers.ciaas import router as ciaas_router

__all__ = [
    "workloads_router",
    "verify_router",
    "health_router",
    "metrics_router",
    "console_router",
    "billing_router",
    "v1_router",
    "ciaas_router",
]