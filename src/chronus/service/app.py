"""Chronus Quantum iGPU REST API Service — Enterprise CIaaS Platform.

Production-ready FastAPI application exposing the Chronus computational
substrate via REST endpoints with OpenAPI specification, authentication,
rate limiting, CORS, compression, and comprehensive observability.
"""

import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from chronus.service.dependencies import auth_service, service_config
from chronus.service.routers import health_router, metrics_router, verify_router, workloads_router
from chronus.service.models import ErrorResponse

_SERVICE_START_TIME = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Handles startup and shutdown of the Chronus service including
    initialization of security components, distributed systems,
    and quantum integration layer.
    """
    print("Chronus Quantum iGPU v36.0 — Starting CIaaS Service...")
    print(f"  Post-Quantum Signatures: {service_config.enable_post_quantum}")
    print(f"  Zero-Auth Verify: {service_config.enable_zero_auth_verify}")
    print(f"  Max Payload Size: {service_config.max_payload_size_mb} MB")
    print(f"  Rate Limit: {service_config.rate_limit_requests_per_minute} req/min")

    yield

    print("Chronus Quantum iGPU v36.0 — Shutting down CIaaS Service...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Chronus Quantum iGPU CIaaS API",
        description="""
# Chronus Quantum iGPU — Representation-Aware Computational Infrastructure

Mathematics-First, Representation-Aware Computational Infrastructure & CIaaS Service Delivery Platform.

## Features

- **Exact Algebraic Computation**: O(1) constant structural RAM via Binet-Zeckendorf and PV Lucas collapse
- **Post-Quantum Security**: ML-DSA (FIPS 204) + Ed25519 signatures
- **Zero-Knowledge Verification**: zk-STARK FRI-based proof verification
- **Zero-Auth Verify**: `/verify/{hash}` endpoint with no authentication required (Invariant I7)
- **Enterprise SDK**: Python SDK with full type hints and async support
- **Distributed Execution**: Failure injection, health checking, cluster orchestration
- **Quantum Integration**: Holonomic Berry Connection, NVQLink QLDPC, CUDA-Q compiler

## Authentication

Most endpoints require a Bearer token in the `Authorization` header:
```
Authorization: Bearer <tenant_id>:<access_token>
```

The `/verify/{hash}` endpoint supports zero-auth access per Invariant I7.


    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Compression middleware
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Exception handlers
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse(
                error="validation_error",
                error_code="VAL001",
                message="Request validation failed",
                details={"errors": exc.errors()},
            ).dict(),
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error="internal_server_error",
                error_code="INT001",
                message="An unexpected error occurred",
                details={"exception": str(exc)},
            ).dict(),
        )

    # Health check middleware
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        response.headers["X-Service-Version"] = "36.0.0"
        return response

    # Register routers
    app.include_router(workloads_router)
    app.include_router(verify_router)
    app.include_router(health_router)
    app.include_router(metrics_router)

    # Root endpoint
    @app.get("/", include_in_schema=False)
    async def root():
        return {
            "service": "Chronus Quantum iGPU CIaaS",
            "version": "36.0.0",
            "status": "operational",
            "docs": "/docs",
            "health": "/health",
            "verify": "/verify/{hash}",
        }

    return app


# Create application instance
app = create_app()
## Rate Limiting

- 600 requests per minute per tenant
- 100 request burst allowance
- Zero-auth endpoints: minimal allowance
        """,
        version="36.0.0",
        contact={
            "name": "Chronus Systems",
            "url": "https://github.com/hybadatadevops1/Chronusv2",
        },
        license_info={
            "name": "MIT License",
            "url": "https://opensource.org/licenses/MIT",
        },
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )