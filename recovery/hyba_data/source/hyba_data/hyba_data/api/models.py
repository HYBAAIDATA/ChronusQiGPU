"""
Pydantic models for HYBA_DATA API requests and responses.

All models follow McKinsey-grade API design: explicit, typed, documented.
"""
from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field


# ── Manifold Models ─────────────────────────────────────────────

class ManifoldInfo(BaseModel):
    name: str
    dimension: int
    embedding_dim: int
    curvature_type: str
    metric_type: str
    cache_enabled: bool


class EmbedRequest(BaseModel):
    manifold_type: str = Field(default="m32", description="Manifold type: m32, grassmannian, stiefel, golden_ratio_sphere, fibonacci_lattice, icosahedral, dodecahedral, lie_group")
    point: int = Field(..., ge=0, description="Integer point to embed")
    manifold_params: dict[str, Any] = Field(default_factory=dict, description="Additional manifold parameters")


class EmbedResponse(BaseModel):
    embedding: list[float]
    manifold: ManifoldInfo


class DistanceRequest(BaseModel):
    manifold_type: str = Field(default="m32")
    point1: int = Field(..., ge=0)
    point2: int = Field(..., ge=0)
    manifold_params: dict[str, Any] = Field(default_factory=dict)


class DistanceResponse(BaseModel):
    distance: float
    manifold: ManifoldInfo


# ── Oracle Models ───────────────────────────────────────────────

class EvaluateRequest(BaseModel):
    oracle_type: str = Field(default="phi_resonance", description="Oracle type: phi_resonance, combinatorial, rastrigin, rosenbrock, ackley, sphere")
    point: int = Field(..., ge=0)
    oracle_params: dict[str, Any] = Field(default_factory=dict)


class EvaluateResponse(BaseModel):
    value: float
    evaluation_count: int
    oracle_type: str


class BatchEvaluateRequest(BaseModel):
    oracle_type: str = Field(default="phi_resonance")
    points: list[int] = Field(..., min_length=1, max_length=10000)
    oracle_params: dict[str, Any] = Field(default_factory=dict)


class BatchEvaluateResponse(BaseModel):
    values: list[float]
    total_evaluations: int


# ── Optimization Models ─────────────────────────────────────────

class OptimizeRequest(BaseModel):
    manifold_type: str = Field(default="m32")
    oracle_type: str = Field(default="phi_resonance")
    operator_type: str = Field(default="mcmc", description="Operator: mcmc, quantum_walk, riemannian_flow, tensor_network, variational")
    solver_type: str = Field(default="mcmc", description="Solver: mcmc, quantum_walk, riemannian, hybrid, variational")
    initial_point: Optional[int] = Field(default=None, ge=0)
    num_runs: int = Field(default=1, ge=1, le=100)
    max_iterations: int = Field(default=1000, ge=1, le=1000000)
    max_time_seconds: float = Field(default=60.0, ge=0.1, le=3600.0)
    manifold_params: dict[str, Any] = Field(default_factory=dict)
    oracle_params: dict[str, Any] = Field(default_factory=dict)
    operator_params: dict[str, Any] = Field(default_factory=dict)
    verbose: bool = Field(default=False)


class OptimizeResponse(BaseModel):
    best_point: int
    best_value: float
    iterations: int
    elapsed_time: float
    converged: bool
    evaluation_count: int
    statistics: dict[str, Any]


# ── Manifold Search Models ──────────────────────────────────────

class ManifoldSearchRequest(BaseModel):
    manifold_type: str = Field(default="m32")
    oracle_type: str = Field(default="phi_resonance")
    operator_type: str = Field(default="mcmc")
    solver_type: str = Field(default="mcmc")
    num_runs: int = Field(default=3, ge=1, le=100)
    max_iterations: int = Field(default=500, ge=1, le=1000000)
    max_time_seconds: float = Field(default=30.0, ge=0.1, le=3600.0)
    enable_parallel: bool = Field(default=True)
    num_workers: int = Field(default=4, ge=1, le=64)
    verbose: bool = Field(default=False)


class ManifoldSearchResponse(BaseModel):
    best_point: int
    best_value: float
    iterations: int
    elapsed_time: float
    converged: bool
    evaluation_count: int
    statistics: dict[str, Any]
    configuration: dict[str, Any]


# ── Health & Telemetry Models ───────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
    uptime_seconds: float
    components: dict[str, str]


class ReadyResponse(BaseModel):
    ready: bool
    checks: dict[str, bool]


class TelemetryResponse(BaseModel):
    metrics: dict[str, Any]
    counters: dict[str, int]
    histograms: dict[str, dict[str, Any]]
    uptime_seconds: float


class ComponentListResponse(BaseModel):
    manifolds: list[dict[str, Any]]
    oracles: list[dict[str, Any]]
    operators: list[dict[str, Any]]
    solvers: list[dict[str, Any]]
    constructors: list[str]


class FaceInfoResponse(BaseModel):
    index: int
    centre: list[float]
    neighbors: list[int]
    resonance: float
    phi_weight: float
