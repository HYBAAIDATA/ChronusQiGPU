"""
HYBA_DATA FastAPI Application — McKinsey-grade REST API.

Endpoints:
  GET  /health                    — Health check
  GET  /ready                      — Readiness check
  GET  /v1/components              — List all available components
  POST /v1/manifold/embed          — Embed a point on a manifold
  POST /v1/manifold/distance       — Compute geodesic distance
  GET  /v1/manifold/faces/{idx}    — Get face parameters
  POST /v1/oracle/evaluate          — Evaluate an oracle at a point
  POST /v1/oracle/evaluate/batch   — Batch oracle evaluation
  POST /v1/optimize                — Run single optimization
  POST /v1/search                  — Run ManifoldSearch orchestration
  GET  /v1/telemetry               — Get telemetry metrics
  GET  /metrics                    — Prometheus metrics endpoint
"""
from __future__ import annotations
import time
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from . import routes
from .al_haras_router import router as al_haras_router
from .themis_router import router as themis_router
from .telemetry import telemetry
from .models import (
    EmbedRequest, DistanceRequest,
    EvaluateRequest, BatchEvaluateRequest,
    OptimizeRequest, ManifoldSearchRequest,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="HYBA_DATA API",
        description="Quantum-Geometric Optimization Framework — McKinsey-grade REST API",
        version="9.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def telemetry_middleware(request: Request, call_next):
        start = time.perf_counter()
        telemetry.increment("api.total_requests")
        telemetry.set_gauge("api.active_requests", telemetry.get_metrics().get("gauges", {}).get("api.active_requests", 0) + 1)
        response = await call_next(request)
        elapsed = time.perf_counter() - start
        telemetry.observe("api.request_duration", elapsed)
        telemetry.increment(f"api.status_{response.status_code}")
        telemetry.set_gauge("api.active_requests", max(0, telemetry.get_metrics().get("gauges", {}).get("api.active_requests", 1) - 1))
        response.headers["X-Response-Time"] = f"{elapsed:.6f}"
        response.headers["X-Service"] = "hyba-data"
        response.headers["X-Version"] = "9.1.0"
        return response

    # ── Health & Readiness ─────────────────────────────────────
    @app.get("/health", response_model=None, tags=["Health"])
    async def health():
        return routes.health()

    @app.get("/ready", response_model=None, tags=["Health"])
    async def ready():
        return routes.ready()

    # ── Component Discovery ────────────────────────────────────
    @app.get("/v1/components", tags=["Discovery"])
    async def list_components():
        return routes.list_components()

    # ── Manifold Endpoints ──────────────────────────────────────
    @app.post("/v1/manifold/embed", tags=["Manifold"])
    async def embed(req: EmbedRequest):
        if req.manifold_type not in routes.MANIFOLD_FACTORIES:
            raise HTTPException(400, f"Unknown manifold type: {req.manifold_type}")
        try:
            return routes.embed(req)
        except Exception as e:
            telemetry.increment("api.embed.errors")
            raise HTTPException(500, str(e))

    @app.post("/v1/manifold/distance", tags=["Manifold"])
    async def distance(req: DistanceRequest):
        if req.manifold_type not in routes.MANIFOLD_FACTORIES:
            raise HTTPException(400, f"Unknown manifold type: {req.manifold_type}")
        try:
            return routes.distance(req)
        except Exception as e:
            telemetry.increment("api.distance.errors")
            raise HTTPException(500, str(e))

    @app.get("/v1/manifold/faces/{face_idx}", tags=["Manifold"])
    async def get_face(face_idx: int):
        try:
            return routes.get_face_info(face_idx)
        except ValueError as e:
            raise HTTPException(400, str(e))

    # ── Oracle Endpoints ────────────────────────────────────────
    @app.post("/v1/oracle/evaluate", tags=["Oracle"])
    async def evaluate(req: EvaluateRequest):
        if req.oracle_type not in routes.ORACLE_FACTORIES:
            raise HTTPException(400, f"Unknown oracle type: {req.oracle_type}")
        try:
            return routes.evaluate(req)
        except Exception as e:
            telemetry.increment("api.evaluate.errors")
            raise HTTPException(500, str(e))

    @app.post("/v1/oracle/evaluate/batch", tags=["Oracle"])
    async def batch_evaluate(req: BatchEvaluateRequest):
        if req.oracle_type not in routes.ORACLE_FACTORIES:
            raise HTTPException(400, f"Unknown oracle type: {req.oracle_type}")
        try:
            return routes.batch_evaluate(req)
        except Exception as e:
            telemetry.increment("api.batch_evaluate.errors")
            raise HTTPException(500, str(e))

    # ── Optimization Endpoints ──────────────────────────────────
    @app.post("/v1/optimize", tags=["Optimization"])
    async def optimize(req: OptimizeRequest):
        if req.solver_type not in routes.SOLVER_FACTORIES:
            raise HTTPException(400, f"Unknown solver type: {req.solver_type}")
        if req.manifold_type not in routes.MANIFOLD_FACTORIES:
            raise HTTPException(400, f"Unknown manifold type: {req.manifold_type}")
        if req.oracle_type not in routes.ORACLE_FACTORIES:
            raise HTTPException(400, f"Unknown oracle type: {req.oracle_type}")
        if req.operator_type not in routes.OPERATOR_FACTORIES:
            raise HTTPException(400, f"Unknown operator type: {req.operator_type}")
        try:
            return routes.optimize(req)
        except Exception as e:
            telemetry.increment("api.optimize.errors")
            raise HTTPException(500, str(e))

    @app.post("/v1/search", tags=["Optimization"])
    async def manifold_search(req: ManifoldSearchRequest):
        if req.solver_type not in routes.SOLVER_FACTORIES:
            raise HTTPException(400, f"Unknown solver type: {req.solver_type}")
        try:
            return routes.manifold_search(req)
        except Exception as e:
            telemetry.increment("api.search.errors")
            raise HTTPException(500, str(e))

    # ── Telemetry ───────────────────────────────────────────────
    @app.get("/v1/telemetry", tags=["Telemetry"])
    async def get_telemetry():
        return routes.get_telemetry()

    @app.get("/metrics", tags=["Telemetry"])
    async def prometheus_metrics():
        return Response(content=routes.get_prometheus_metrics(), media_type="text/plain")

    # -- AL HARAS Security Product --
    app.include_router(al_haras_router)

    # -- THEMIS Regulatory Report Generation Product --
    app.include_router(themis_router)

    return app


# Module-level app instance for uvicorn
app = create_app()
