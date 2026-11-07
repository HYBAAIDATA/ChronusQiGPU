"""Chronus API application factory."""

import logging
import os
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from chronus.service.dependencies import service_config
from chronus.service.models import ErrorResponse
from chronus.service.routers import (
    billing_router,
    ciaas_router,
    console_router,
    health_router,
    metrics_router,
    v1_router,
    verify_router,
    workloads_router,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info(
        "Chronus API starting; execution_backend_configured=%s",
        bool(service_config.execution_backend_url),
    )
    yield
    logger.info("Chronus API stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Chronus Quantum iGPU API",
        version="36.0.0",
        description=(
            "Chronus is a mathematics-first, representation-aware computational "
            "substrate. Its execution model is designed to operate on a native "
            "mathematical reference backend and to extend workloads to client or "
            "fleet accelerators through backend adapters. This API currently "
            "executes supported workloads on the native reference backend or "
            "forwards them to an explicitly configured compatible execution service."
        ),
        lifespan=lifespan,
    )

    allowed_origins = [
        origin.strip()
        for origin in os.getenv("CHRONUS_CORS_ORIGINS", "").split(",")
        if origin.strip()
    ]
    if allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=[
                "Authorization",
                "Content-Type",
                "X-Request-ID",
                "X-Tenant-ID",
                "X-Region",
                "X-Endpoint",
                "X-SDK-Version",
            ],
        )
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=jsonable_encoder(
                ErrorResponse(
                    error="validation_error",
                    error_code="VAL001",
                    message="Request validation failed",
                    details={
                        "errors": [
                            {key: error[key] for key in ("type", "loc", "msg") if key in error}
                            for error in exc.errors()
                        ]
                    },
                )
            ),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request, exc: HTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=jsonable_encoder({"detail": exc.detail}),
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception("Unhandled request error for %s", request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=jsonable_encoder(
                ErrorResponse(
                    error="internal_server_error",
                    error_code="INT001",
                    message="An unexpected error occurred",
                )
            ),
        )

    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Process-Time"] = str(time.perf_counter() - started)
        response.headers["X-Service-Version"] = app.version
        return response

    app.include_router(workloads_router)
    app.include_router(verify_router)
    app.include_router(health_router)
    app.include_router(metrics_router)
    app.include_router(console_router)
    app.include_router(billing_router)
    app.include_router(v1_router)
    app.include_router(ciaas_router)

    @app.get("/", include_in_schema=False)
    async def root():
        return {
            "service": "Chronus Quantum iGPU API",
            "version": app.version,
            "status": (
                "remote_adapter"
                if service_config.execution_backend_url
                else "native_reference"
            ),
            "docs": "/docs",
            "health": "/health",
            "readiness": "/health/ready",
        }

    return app


app = create_app()
