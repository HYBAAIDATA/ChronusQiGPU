"""Versioned API surface. Health and metrics stay outside /v1 on purpose."""

from __future__ import annotations

import hashlib
import logging
import os
import time
import uuid

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from chronus.service.api import claims, state
from chronus.service.api.errors import ApiError, install_error_handlers, problem_response
from chronus.service.api.lease import current_lease
from chronus.service.api.routers import capabilities, evidence, lease, nodes, workloads
from chronus.service.api.schemas import IntrospectionResult, Lease
from chronus.service.api.security import Principal, _token_table, current_principal
from chronus.service.metrics import router as metrics_router

logger = logging.getLogger("chronus.api")
_RATE_WINDOW_SECONDS = 60
_EXEMPT = {"/health", "/health/ready", "/metrics"}


def reset_rate_limit() -> None:
    state.reset_rate_limit()


def _rate_key(request: Request) -> str:
    authorization = request.headers.get("Authorization")
    if authorization:
        return hashlib.sha256(authorization.encode("utf-8")).hexdigest()
    client = request.client
    return client.host if client else "unknown"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assign and echo a request id, and log one line per request."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        logger.info("%s %s -> %s %.1fms request_id=%s", request.method,
                    request.url.path, response.status_code,
                    (time.perf_counter() - started) * 1000, request_id)
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Return a 429 problem response; middleware cannot use exception handlers."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path in _EXEMPT:
            return await call_next(request)

        limit = request.app.state.rate_max
        key = _rate_key(request)
        allowed, retry = state.rate_hit(key, limit, _RATE_WINDOW_SECONDS)
        if not allowed:
            return problem_response(request, 429, "rate_limited", "Too many requests",
                                    f"Retry in {retry}s.",
                                    headers={"Retry-After": str(retry)})
        return await call_next(request)


def create_app() -> FastAPI:
    docs_enabled = os.getenv("CHRONUS_ENABLE_DOCS", "1") != "0"
    app = FastAPI(
        title="Chronus Compute API",
        version="1.0.0",
        description="Submit, track and prove workloads on the Chronus compute fleet.",
        openapi_url="/v1/openapi.json",
        docs_url="/docs" if docs_enabled else None,
        redoc_url=None,
    )
    # Read per app, not at import: tests and deployments may change the value.
    app.state.rate_max = int(os.getenv("CHRONUS_RATE_MAX", "120"))

    install_error_handlers(app)
    # add_middleware prepends, so RequestContext is added last to be outermost.
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestContextMiddleware)

    v1 = APIRouter(prefix="/v1")
    v1.include_router(workloads.router, prefix="/workloads", tags=["workloads"])
    v1.include_router(nodes.router, prefix="/nodes", tags=["fleet"])
    v1.include_router(nodes.capacity_router, prefix="/capacity", tags=["fleet"])
    v1.include_router(capabilities.router, prefix="/capabilities", tags=["evidence"])
    v1.include_router(capabilities.qualification_router, prefix="/qualification",
                      tags=["evidence"])
    v1.include_router(evidence.router, prefix="/receipts", tags=["evidence"])
    v1.include_router(lease.router, prefix="/lease", tags=["tenant"])

    @v1.post("/tokens/introspect", response_model=IntrospectionResult,
             summary="Validate a token")
    async def introspect(principal: Principal = Depends(current_principal),
                         current: Lease = Depends(current_lease)):
        return IntrospectionResult(tenant_id=principal.tenant_id,
                                   scopes=sorted(principal.scopes), lease=current)

    app.include_router(v1)
    app.include_router(metrics_router)

    @app.get("/health", tags=["ops"], summary="Liveness")
    async def health():
        return {"status": "ok"}

    @app.get("/health/ready", tags=["ops"], summary="Readiness")
    async def ready():
        reasons = []
        for check in (_token_table, claims.load_audit, state.check_state):
            try:
                check()
            except ApiError as exc:
                reasons.append(exc.code)
            except (OSError, RuntimeError) as exc:
                logger.error("Readiness check failed: %s", exc)
                reasons.append("state_unavailable")
        if reasons:
            return JSONResponse({"status": "degraded", "reasons": reasons}, status_code=503)
        return {"status": "ready"}

    return app
