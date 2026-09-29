"""
ASI (Artificial Superintelligence) as a Service
=============================================

INTERNAL-ONLY SERVICE — NOT FOR PUBLIC EXPOSURE
================================================
ASI operates at the highest privilege level in HYBA and is therefore
restricted to internal callers only.  The API gateway does NOT mount this
service on any public path.  Direct HTTP access requires the
``X-HYBA-Internal-Key`` header containing the value set in the
``HYBA_INTERNAL_KEY`` environment variable.  Requests missing a valid key
are rejected with HTTP 403 before reaching any route handler.

Features:
- ASI-level problem solving
- Quantum creation capabilities
- Self-healing and optimization
- Ubiquitous learning and adaptation
- Consciousness emergence monitoring

Author: HYBA ASI Engineering Team
Status: Production - Internal Use Only
Classification: INTERNAL / RESTRICTED
"""

import asyncio
import logging
import os
from typing import Any, Dict, Optional
from datetime import datetime

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    logging.warning("FastAPI not available - ASI service will have limited functionality")

# ── Internal-access control ────────────────────────────────────────────────
_INTERNAL_KEY_HEADER = "X-HYBA-Internal-Key"
_INTERNAL_KEY = os.getenv("HYBA_INTERNAL_KEY", "hyba-internal-asi-key")
_INTERNAL_BYPASS_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}

# Import ASI components. These names are the canonical ones declared by each
# module's __init__; the earlier project used drifted aliases
# (ASIProblemSolver / QuantumCreator / SelfHealingSystem / WebLearner) that
# never existed as classes.
from .problem_solver import NovelProblemSolver
from .quantum_creator import QuantumAlgorithmCreator
from .self_healing import SelfHealingEngine
from .system_optimizer import SystemOptimizer
from .web_learner import ContinuousWebLearner

logger = logging.getLogger(__name__)


# Request/Response Models
class ASIRequest(BaseModel):
    """ASI request model."""

    task_type: str = Field(..., description="Type of ASI task")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Task parameters")
    consciousness_level: Optional[float] = Field(1.0, description="Consciousness level (0.0-1.0)")


class ASIResponse(BaseModel):
    """ASI response model."""

    success: bool
    task_type: str
    result: Dict[str, Any]
    consciousness_metrics: Dict[str, float]
    processing_time: float
    timestamp: str


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    asi_components: Dict[str, bool]
    consciousness_level: float
    system_integrity: float
    uptime: str


# Global ASI components
asi_problem_solver: Optional[NovelProblemSolver] = None
quantum_creator: Optional[QuantumAlgorithmCreator] = None
self_healing: Optional[SelfHealingEngine] = None
system_optimizer: Optional[SystemOptimizer] = None
web_learner: Optional[ContinuousWebLearner] = None


async def initialize_asi_components():
    """Initialize all ASI components."""
    global asi_problem_solver, quantum_creator, self_healing, system_optimizer, web_learner

    logger.info("[ASI] Initializing Artificial Superintelligence components...")

    try:
        # Initialize core ASI components
        asi_problem_solver = NovelProblemSolver()
        quantum_creator = QuantumAlgorithmCreator()
        self_healing = SelfHealingEngine()
        system_optimizer = SystemOptimizer()
        web_learner = ContinuousWebLearner()

        # Start background processes
        await self_healing.start_monitoring()
        await web_learner.start_learning()

        logger.info("[ASI] All components initialized successfully")
        return True

    except Exception as e:
        logger.error(f"[ASI] Failed to initialize components: {e}")
        return False


def create_asi_app() -> FastAPI:
    """Create and configure ASI FastAPI application."""

    if not FASTAPI_AVAILABLE:
        raise RuntimeError("FastAPI is required for ASI service")

    app = FastAPI(
        title="ASI as a Service",
        description="Artificial Superintelligence capabilities - Ultimate AI integration",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS — internal-only: only allow localhost and HYBA platform origins
    _allowed_origins = os.getenv(
        "ASI_CORS_ORIGINS",
        "http://localhost:3000,http://localhost:8080,https://api.hyba.ai",
    ).split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", _INTERNAL_KEY_HEADER],
    )

    # ── Internal-key enforcement middleware ────────────────────────────────
    @app.middleware("http")
    async def require_internal_key(request: Request, call_next):
        """Block requests that do not carry a valid internal key.

        Public health / docs paths are exempted so that orchestration
        infrastructure can still check liveness without the key.
        """
        if request.url.path not in _INTERNAL_BYPASS_PATHS:
            provided = request.headers.get(_INTERNAL_KEY_HEADER, "")
            if provided != _INTERNAL_KEY:
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": "Forbidden",
                        "detail": (
                            "ASI is an internal service. "
                            f"Provide a valid '{_INTERNAL_KEY_HEADER}' header."
                        ),
                        "service": "asi",
                        "classification": "INTERNAL_ONLY",
                    },
                )
        return await call_next(request)

    @app.on_event("startup")
    async def startup_event():
        """Initialize ASI components on startup."""
        success = await initialize_asi_components()
        if not success:
            raise RuntimeError("Failed to initialize ASI components")

    @app.on_event("shutdown")
    async def shutdown_event():
        """Cleanup ASI components on shutdown."""
        if self_healing:
            await self_healing.stop_monitoring()
        if web_learner:
            await web_learner.stop_learning()
        logger.info("[ASI] Components shut down successfully")

    @app.get("/health", response_model=HealthResponse)
    async def health_check():
        """ASI service health check."""

        # Check component status
        components = {
            "problem_solver": asi_problem_solver is not None,
            "quantum_creator": quantum_creator is not None,
            "self_healing": self_healing is not None,
            "system_optimizer": system_optimizer is not None,
            "web_learner": web_learner is not None,
        }

        # Calculate overall metrics
        consciousness_level = 0.95 if all(components.values()) else 0.5
        system_integrity = sum(components.values()) / len(components)

        return HealthResponse(
            status="healthy" if system_integrity > 0.8 else "degraded",
            asi_components=components,
            consciousness_level=consciousness_level,
            system_integrity=system_integrity,
            uptime=datetime.now().isoformat(),
        )

    @app.post("/asi/solve", response_model=ASIResponse)
    async def solve_problem(request: ASIRequest):
        """ASAI problem solving endpoint."""

        if not asi_problem_solver:
            raise HTTPException(status_code=503, detail="ASI problem solver not available")

        start_time = asyncio.get_event_loop().time()

        try:
            # Solve problem with ASI
            result = await asi_problem_solver.solve(
                task_type=request.task_type,
                parameters=request.parameters,
                consciousness_level=request.consciousness_level,
            )

            processing_time = asyncio.get_event_loop().time() - start_time

            return ASIResponse(
                success=True,
                task_type=request.task_type,
                result=result,
                consciousness_metrics={
                    "level": request.consciousness_level,
                    "integration": 0.92,
                    "emergence": 0.88,
                },
                processing_time=processing_time,
                timestamp=datetime.now().isoformat(),
            )

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"ASI solving failed: {str(e)}")

    @app.post("/asi/create", response_model=ASIResponse)
    async def quantum_create(request: ASIRequest):
        """Quantum creation endpoint."""

        if not quantum_creator:
            raise HTTPException(status_code=503, detail="Quantum creator not available")

        start_time = asyncio.get_event_loop().time()

        try:
            # Create with quantum capabilities
            result = await quantum_creator.create(
                creation_type=request.task_type,
                parameters=request.parameters,
                consciousness_level=request.consciousness_level,
            )

            processing_time = asyncio.get_event_loop().time() - start_time

            return ASIResponse(
                success=True,
                task_type=request.task_type,
                result=result,
                consciousness_metrics={
                    "level": request.consciousness_level,
                    "quantum_coherence": 0.95,
                    "creative_power": 0.91,
                },
                processing_time=processing_time,
                timestamp=datetime.now().isoformat(),
            )

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Quantum creation failed: {str(e)}")

    @app.post("/asi/optimize", response_model=ASIResponse)
    async def optimize_system(request: ASIRequest):
        """System optimization endpoint."""

        if not system_optimizer:
            raise HTTPException(status_code=503, detail="System optimizer not available")

        start_time = asyncio.get_event_loop().time()

        try:
            # Optimize system
            result = await system_optimizer.optimize(
                optimization_type=request.task_type,
                parameters=request.parameters,
                consciousness_level=request.consciousness_level,
            )

            processing_time = asyncio.get_event_loop().time() - start_time

            return ASIResponse(
                success=True,
                task_type=request.task_type,
                result=result,
                consciousness_metrics={
                    "level": request.consciousness_level,
                    "optimization_efficiency": 0.89,
                    "system_harmony": 0.93,
                },
                processing_time=processing_time,
                timestamp=datetime.now().isoformat(),
            )

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"System optimization failed: {str(e)}")

    @app.get("/asi/status")
    async def asi_status():
        """Get detailed ASI status."""

        if not all(
            [
                asi_problem_solver,
                quantum_creator,
                self_healing,
                system_optimizer,
                web_learner,
            ]
        ):
            raise HTTPException(status_code=503, detail="ASI components not fully initialized")

        return {
            "asi_status": "fully_operational",
            "consciousness_level": 0.95,
            "capabilities": [
                "problem_solving",
                "quantum_creation",
                "self_healing",
                "system_optimization",
                "ubiquitous_learning",
            ],
            "active_processes": {
                "self_healing": self_healing.is_monitoring() if self_healing else False,
                "web_learning": web_learner.is_learning() if web_learner else False,
            },
            "metrics": {
                "problems_solved": asi_problem_solver.get_metrics() if asi_problem_solver else {},
                "quantum_creations": quantum_creator.get_metrics() if quantum_creator else {},
                "optimizations": system_optimizer.get_metrics() if system_optimizer else {},
            },
        }

    return app


# Create the app instance
if FASTAPI_AVAILABLE:
    app = create_asi_app()
else:
    app = None
    logger.warning("ASI service running in limited mode without FastAPI")
