"""Internal ASI compatibility service.

This service is intentionally evidence-first.  It does not manufacture
consciousness, health, optimisation or learning metrics.  ASI healing and
optimisation delegate to SALAMANDER; security/governance remains AL HARAS.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
import hmac
import logging
import os
import time
from typing import Any, Dict, Optional

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    FastAPI = Any  # type: ignore[misc,assignment]
    HTTPException = RuntimeError  # type: ignore[misc,assignment]
    Request = Any  # type: ignore[misc,assignment]
    CORSMiddleware = Any  # type: ignore[misc,assignment]
    JSONResponse = Any  # type: ignore[misc,assignment]

    class BaseModel:  # type: ignore[no-redef]
        pass

    def Field(default=None, *, default_factory=None, **_kwargs):  # type: ignore[no-redef]
        return default_factory() if default_factory is not None else default


from .problem_solver import NovelProblemSolver
from .quantum_creator import AlgorithmType, QuantumAlgorithmCreator
from .self_healing import SelfHealingEngine
from .system_optimizer import SystemOptimizer
from .web_learner import ContinuousWebLearner

logger = logging.getLogger(__name__)

_INTERNAL_KEY_HEADER = "X-HYBA-Internal-Key"
_INTERNAL_KEY = os.getenv("HYBA_INTERNAL_KEY", "").strip()
_INTERNAL_BYPASS_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}
_STARTED_MONOTONIC = time.monotonic()


class ASIRequest(BaseModel):
    task_type: str = Field(..., description="Requested compatibility task")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    # Historical field retained for wire compatibility only. It is not used
    # as a production signal and is never echoed as measured evidence.
    consciousness_level: Optional[float] = Field(
        None,
        description="Deprecated compatibility field; not a measured production signal",
    )


class ASIResponse(BaseModel):
    success: bool
    task_type: str
    result: Dict[str, Any]
    consciousness_metrics: Dict[str, Any] = Field(default_factory=dict)
    processing_time: float
    timestamp: str


class HealthResponse(BaseModel):
    status: str
    asi_components: Dict[str, bool]
    consciousness_level: Optional[float] = None
    system_integrity: Optional[float] = None
    uptime: str


asi_problem_solver: Optional[NovelProblemSolver] = None
quantum_creator: Optional[QuantumAlgorithmCreator] = None
self_healing: Optional[SelfHealingEngine] = None
system_optimizer: Optional[SystemOptimizer] = None
web_learner: Optional[ContinuousWebLearner] = None


async def initialize_asi_components() -> bool:
    """Compose adapters only; do not start hidden forever-loops."""
    global asi_problem_solver, quantum_creator, self_healing, system_optimizer, web_learner
    try:
        asi_problem_solver = NovelProblemSolver()
        quantum_creator = QuantumAlgorithmCreator()
        self_healing = SelfHealingEngine()
        system_optimizer = SystemOptimizer()
        web_learner = ContinuousWebLearner()
        return True
    except Exception:
        logger.exception("ASI compatibility composition failed")
        return False


def _unmeasured_metrics() -> Dict[str, Any]:
    return {
        "status": "UNAVAILABLE",
        "reason": "no independently measured consciousness metric is defined",
    }


def create_asi_app() -> FastAPI:
    if not FASTAPI_AVAILABLE:
        raise RuntimeError("FastAPI is required for ASI service")

    app = FastAPI(
        title="ASI compatibility service",
        description="Internal compatibility facade with canonical authority boundaries",
        version="1.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    allowed_origins = [
        value.strip()
        for value in os.getenv(
            "ASI_CORS_ORIGINS",
            "http://localhost:3000,http://localhost:8080",
        ).split(",")
        if value.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", _INTERNAL_KEY_HEADER],
    )

    @app.middleware("http")
    async def require_internal_key(request: Request, call_next):
        if request.url.path not in _INTERNAL_BYPASS_PATHS:
            if not _INTERNAL_KEY:
                return JSONResponse(
                    status_code=503,
                    content={
                        "error": "Unavailable",
                        "detail": "HYBA_INTERNAL_KEY is not configured",
                        "service": "asi",
                    },
                )
            provided = request.headers.get(_INTERNAL_KEY_HEADER, "")
            if not hmac.compare_digest(provided, _INTERNAL_KEY):
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": "Forbidden",
                        "detail": "valid internal service credential required",
                        "service": "asi",
                    },
                )
        return await call_next(request)

    @app.on_event("startup")
    async def startup_event():
        if not await initialize_asi_components():
            raise RuntimeError("Failed to initialize ASI compatibility components")

    @app.on_event("shutdown")
    async def shutdown_event():
        if self_healing:
            self_healing.stop_monitoring()
        if web_learner:
            web_learner.stop()

    @app.get("/health", response_model=HealthResponse)
    async def health_check():
        learner_available = False
        if web_learner is not None:
            try:
                learner_available = bool(web_learner.get_stats().get("backend_available"))
            except Exception:
                learner_available = False
        components = {
            "problem_solver": asi_problem_solver is not None,
            "quantum_creator": quantum_creator is not None,
            "self_healing_facade": self_healing is not None,
            "system_optimizer_facade": system_optimizer is not None,
            "web_research_backend": learner_available,
        }
        required = (
            components["problem_solver"]
            and components["quantum_creator"]
            and components["self_healing_facade"]
            and components["system_optimizer_facade"]
        )
        return HealthResponse(
            status="healthy" if required else "degraded",
            asi_components=components,
            consciousness_level=None,
            system_integrity=None,
            uptime=f"{time.monotonic() - _STARTED_MONOTONIC:.3f}s",
        )

    @app.post("/asi/solve", response_model=ASIResponse)
    async def solve_problem(request: ASIRequest):
        if not asi_problem_solver:
            raise HTTPException(status_code=503, detail="problem solver unavailable")
        started = time.monotonic()
        try:
            result = await asi_problem_solver.solve_problem(
                description=request.task_type,
                constraints=request.parameters,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"problem solving failed: {type(exc).__name__}: {exc}",
            ) from exc
        return ASIResponse(
            success=bool(result.get("solved")),
            task_type=request.task_type,
            result=result,
            consciousness_metrics=_unmeasured_metrics(),
            processing_time=time.monotonic() - started,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    @app.post("/asi/create", response_model=ASIResponse)
    async def quantum_create(request: ASIRequest):
        if not quantum_creator:
            raise HTTPException(status_code=503, detail="algorithm creator unavailable")
        started = time.monotonic()
        raw_type = str(request.parameters.get("algorithm_type", request.task_type)).lower()
        try:
            algorithm_type = AlgorithmType(raw_type)
        except ValueError:
            algorithm_type = AlgorithmType.CUSTOM
        try:
            algorithm = await quantum_creator.create_algorithm(
                problem_description=request.task_type,
                problem_type=algorithm_type,
                constraints=dict(request.parameters.get("constraints", {})),
            )
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"algorithm creation failed: {type(exc).__name__}: {exc}",
            ) from exc
        result = {
            "algorithm_id": algorithm.algorithm_id,
            "name": algorithm.name,
            "algorithm_type": algorithm.algorithm_type.value,
            "circuit_qubits": algorithm.circuit.num_qubits,
            "circuit_depth": algorithm.circuit.depth,
            "claim_boundary": "SOFTWARE_ALGORITHM_DESIGN_NOT_MEASURED_QUANTUM_ADVANTAGE",
        }
        return ASIResponse(
            success=True,
            task_type=request.task_type,
            result=result,
            consciousness_metrics=_unmeasured_metrics(),
            processing_time=time.monotonic() - started,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    @app.post("/asi/optimize", response_model=ASIResponse)
    async def optimize_system(request: ASIRequest):
        if not system_optimizer:
            raise HTTPException(status_code=503, detail="optimizer facade unavailable")
        started = time.monotonic()
        target = request.parameters.get("target", request.task_type)
        try:
            proposal = system_optimizer.optimize(str(target))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        result = {
            **asdict(proposal),
            "target": proposal.target.value,
            "authority": "SALAMANDER",
            "effect": "NONE_UNTIL_MEASURED_PROMOTION",
        }
        return ASIResponse(
            success=True,
            task_type=request.task_type,
            result=result,
            consciousness_metrics=_unmeasured_metrics(),
            processing_time=time.monotonic() - started,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    @app.get("/asi/status")
    async def asi_status():
        if not all((asi_problem_solver, quantum_creator, self_healing, system_optimizer)):
            raise HTTPException(status_code=503, detail="ASI compatibility components incomplete")
        web_stats = web_learner.get_stats() if web_learner else {
            "backend_available": False
        }
        return {
            "asi_status": "COMPATIBILITY_FACADE",
            "authority": {
                "healing": "SALAMANDER",
                "optimisation": "SALAMANDER",
                "security_governance": "AL_HARAS",
            },
            "consciousness_level": "Unavailable",
            "active_processes": {
                "self_healing_background_loop": False,
                "web_learning_background_loop": False,
            },
            "metrics": {
                "problem_solver": asi_problem_solver.get_stats(),
                "algorithm_creator": quantum_creator.get_stats(),
                "optimizer": system_optimizer.get_metrics(),
                "web_learning": web_stats,
            },
        }

    return app


if FASTAPI_AVAILABLE:
    app = create_asi_app()
else:
    app = None
    logger.warning("ASI service unavailable because FastAPI is not installed")
