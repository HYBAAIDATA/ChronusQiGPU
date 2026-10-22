"""
REST API routes for HYBA_DATA.

McKinsey-grade endpoint design: versioned, documented, consistent.
All endpoints return typed responses with telemetry instrumentation.
"""
from __future__ import annotations
import time
from typing import Any

import numpy as np

from hyba_data import (
    M32Manifold, GrassmannianManifold, StiefelManifold,
    PhiResonanceOracle, CombinatorialOracle,
    RastriginOracle, RosenbrockOracle, AckleyOracle, SphereOracle,
    MCMCOperator, QuantumWalkOperator, RiemannianFlowOperator,
    TensorNetworkOperator, VariationalOperator,
    MCMCSolver, QuantumWalkSolver, RiemannianSolver, HybridSolver, VariationalSolver,
    ManifoldSearch, ManifoldSearchConfig,
    ManifoldConstructor, ManifoldType,
    SolverConfig,
)
from hyba_data import get_face_parameters, NUM_FACES

from .models import (
    EmbedRequest, EmbedResponse, DistanceRequest, DistanceResponse,
    EvaluateRequest, EvaluateResponse, BatchEvaluateRequest, BatchEvaluateResponse,
    OptimizeRequest, OptimizeResponse,
    ManifoldSearchRequest, ManifoldSearchResponse,
    HealthResponse, ReadyResponse, TelemetryResponse,
    ComponentListResponse, FaceInfoResponse,
    ManifoldInfo,
)
from .telemetry import telemetry


# ── Component Factories ─────────────────────────────────────────

MANIFOLD_FACTORIES = {
    "m32": lambda **kw: M32Manifold(),
    "grassmannian": lambda **kw: GrassmannianManifold(kw.get("p", 2), kw.get("n", 4)),
    "stiefel": lambda **kw: StiefelManifold(kw.get("p", 2), kw.get("n", 4)),
    "golden_ratio_sphere": lambda **kw: ManifoldConstructor().construct(ManifoldType.GOLDEN_RATIO_SPHERE, **kw),
    "fibonacci_lattice": lambda **kw: ManifoldConstructor().construct(ManifoldType.FIBONACCI_LATTICE, **kw),
    "icosahedral": lambda **kw: ManifoldConstructor().construct(ManifoldType.ICOSAHEDRAL),
    "dodecahedral": lambda **kw: ManifoldConstructor().construct(ManifoldType.DODECAHEDRAL),
    "lie_group": lambda **kw: ManifoldConstructor().construct(ManifoldType.LIE_GROUP, **kw),
}

ORACLE_FACTORIES = {
    "phi_resonance": lambda **kw: PhiResonanceOracle(),
    "combinatorial": lambda **kw: CombinatorialOracle(kw.get("cost_function", lambda x: float(x % 100))),
    "rastrigin": lambda **kw: RastriginOracle(dimension=kw.get("dimension", 5)),
    "rosenbrock": lambda **kw: RosenbrockOracle(dimension=kw.get("dimension", 5)),
    "ackley": lambda **kw: AckleyOracle(dimension=kw.get("dimension", 5)),
    "sphere": lambda **kw: SphereOracle(dimension=kw.get("dimension", 5)),
}

OPERATOR_FACTORIES = {
    "mcmc": lambda **kw: MCMCOperator(),
    "quantum_walk": lambda **kw: QuantumWalkOperator(walk_type=kw.get("walk_type", "continuous")),
    "riemannian_flow": lambda **kw: RiemannianFlowOperator(method=kw.get("method", "gradient_descent")),
    "tensor_network": lambda **kw: TensorNetworkOperator(max_bond_dim=kw.get("max_bond_dim", 32)),
    "variational": lambda **kw: VariationalOperator(method=kw.get("method", "qaoa"), num_layers=kw.get("num_layers", 3)),
}

SOLVER_FACTORIES = {
    "mcmc": lambda m, o, op, **kw: MCMCSolver(m, o, op, kw.get("config")),
    "quantum_walk": lambda m, o, op, **kw: QuantumWalkSolver(m, o, op, kw.get("config")),
    "riemannian": lambda m, o, op, **kw: RiemannianSolver(m, o, op, kw.get("config")),
    "variational": lambda m, o, op, **kw: VariationalSolver(m, o, op, kw.get("config")),
    "hybrid": lambda m, o, op, **kw: HybridSolver(m, o, op if isinstance(op, list) else [op], kw.get("config")),
}


def _manifold_info(manifold) -> ManifoldInfo:
    info = manifold.get_info()
    return ManifoldInfo(
        name=info.get("metadata", {}).get("name", "unknown"),
        dimension=info["dimension"],
        embedding_dim=info["embedding_dim"],
        curvature_type=info["curvature_type"],
        metric_type=info["metric_type"],
        cache_enabled=info["cache_enabled"],
    )


# ── Route Handlers ──────────────────────────────────────────────

def health() -> HealthResponse:
    telemetry.increment("api.health.requests")
    return HealthResponse(
        status="healthy",
        version="9.0.0",
        uptime_seconds=telemetry.get_metrics()["uptime_seconds"],
        components={
            "manifold": "ok",
            "oracle": "ok",
            "operator": "ok",
            "solver": "ok",
            "search": "ok",
        },
    )


def ready() -> ReadyResponse:
    checks = {
        "manifold_factory": bool(MANIFOLD_FACTORIES),
        "oracle_factory": bool(ORACLE_FACTORIES),
        "operator_factory": bool(OPERATOR_FACTORIES),
        "solver_factory": bool(SOLVER_FACTORIES),
    }
    return ReadyResponse(ready=all(checks.values()), checks=checks)


def list_components() -> ComponentListResponse:
    telemetry.increment("api.components.list")
    return ComponentListResponse(
        manifolds=[
            {"name": k, "params": {}}
            for k in MANIFOLD_FACTORIES
        ],
        oracles=[
            {"name": k, "params": {}}
            for k in ORACLE_FACTORIES
        ],
        operators=[
            {"name": k, "params": {}}
            for k in OPERATOR_FACTORIES
        ],
        solvers=[
            {"name": k, "params": {}}
            for k in SOLVER_FACTORIES
        ],
        constructors=[t.value for t in ManifoldType],
    )


def embed(req: EmbedRequest) -> EmbedResponse:
    start = time.perf_counter()
    telemetry.increment("api.embed.requests")
    manifold = MANIFOLD_FACTORIES[req.manifold_type](**req.manifold_params)
    emb = manifold.embed(req.point)
    elapsed = time.perf_counter() - start
    telemetry.observe("api.embed.duration", elapsed)
    return EmbedResponse(
        embedding=emb.tolist(),
        manifold=_manifold_info(manifold),
    )


def distance(req: DistanceRequest) -> DistanceResponse:
    start = time.perf_counter()
    telemetry.increment("api.distance.requests")
    manifold = MANIFOLD_FACTORIES[req.manifold_type](**req.manifold_params)
    d = manifold.distance(req.point1, req.point2)
    elapsed = time.perf_counter() - start
    telemetry.observe("api.distance.duration", elapsed)
    return DistanceResponse(
        distance=float(d),
        manifold=_manifold_info(manifold),
    )


def evaluate(req: EvaluateRequest) -> EvaluateResponse:
    start = time.perf_counter()
    telemetry.increment("api.evaluate.requests")
    oracle = ORACLE_FACTORIES[req.oracle_type](**req.oracle_params)
    oracle.reset_evaluation_count()
    val = oracle.evaluate(req.point)
    elapsed = time.perf_counter() - start
    telemetry.observe("api.evaluate.duration", elapsed)
    telemetry.increment(f"api.evaluate.oracle.{req.oracle_type}")
    return EvaluateResponse(
        value=float(val),
        evaluation_count=oracle.get_evaluation_count(),
        oracle_type=req.oracle_type,
    )


def batch_evaluate(req: BatchEvaluateRequest) -> BatchEvaluateResponse:
    start = time.perf_counter()
    telemetry.increment("api.batch_evaluate.requests")
    oracle = ORACLE_FACTORIES[req.oracle_type](**req.oracle_params)
    oracle.reset_evaluation_count()
    vals = oracle.evaluate_batch(req.points)
    elapsed = time.perf_counter() - start
    telemetry.observe("api.batch_evaluate.duration", elapsed)
    return BatchEvaluateResponse(
        values=[float(v) for v in vals],
        total_evaluations=oracle.get_evaluation_count(),
    )


def optimize(req: OptimizeRequest) -> OptimizeResponse:
    start = time.perf_counter()
    telemetry.increment("api.optimize.requests")
    telemetry.increment(f"api.optimize.solver.{req.solver_type}")
    manifold = MANIFOLD_FACTORIES[req.manifold_type](**req.manifold_params)
    oracle = ORACLE_FACTORIES[req.oracle_type](**req.oracle_params)
    operator = OPERATOR_FACTORIES[req.operator_type](**req.operator_params)
    config = SolverConfig(
        max_iterations=req.max_iterations,
        max_time_seconds=req.max_time_seconds,
        verbose=req.verbose,
    )
    solver = SOLVER_FACTORIES[req.solver_type](manifold, oracle, operator, config=config)
    result = solver.solve(req.initial_point)
    elapsed = time.perf_counter() - start
    telemetry.observe("api.optimize.duration", elapsed)
    telemetry.record_event("optimization",
        solver=req.solver_type, oracle=req.oracle_type,
        manifold=req.manifold_type, best_value=result.best_value,
        iterations=result.iterations, elapsed=elapsed,
    )
    return OptimizeResponse(
        best_point=result.best_point,
        best_value=float(result.best_value),
        iterations=result.iterations,
        elapsed_time=float(result.elapsed_time),
        converged=result.converged,
        evaluation_count=result.evaluation_count,
        statistics={},
    )


def manifold_search(req: ManifoldSearchRequest) -> ManifoldSearchResponse:
    start = time.perf_counter()
    telemetry.increment("api.search.requests")
    manifold = MANIFOLD_FACTORIES[req.manifold_type]()
    oracle = ORACLE_FACTORIES[req.oracle_type]()
    operator = OPERATOR_FACTORIES[req.operator_type]()
    config = SolverConfig(
        max_iterations=req.max_iterations,
        max_time_seconds=req.max_time_seconds,
        verbose=req.verbose,
    )
    solver = SOLVER_FACTORIES[req.solver_type](manifold, oracle, operator, config=config)
    search_config = ManifoldSearchConfig(
        enable_parallel=req.enable_parallel,
        num_workers=req.num_workers,
        verbose=req.verbose,
    )
    search = ManifoldSearch(manifold, oracle, operator, solver, search_config)
    result = search.optimize(num_runs=req.num_runs)
    stats = search.get_statistics()
    elapsed = time.perf_counter() - start
    telemetry.observe("api.search.duration", elapsed)
    telemetry.record_event("manifold_search",
        solver=req.solver_type, oracle=req.oracle_type,
        manifold=req.manifold_type, best_value=result.best_value,
        num_runs=req.num_runs, elapsed=elapsed,
    )
    return ManifoldSearchResponse(
        best_point=result.best_point,
        best_value=float(result.best_value),
        iterations=result.iterations,
        elapsed_time=float(result.elapsed_time),
        converged=result.converged,
        evaluation_count=result.evaluation_count,
        statistics={k: float(v) if isinstance(v, (int, float, np.floating)) else v for k, v in stats.items()},
        configuration={
            "manifold": req.manifold_type,
            "oracle": req.oracle_type,
            "operator": req.operator_type,
            "solver": req.solver_type,
        },
    )


def get_face_info(face_idx: int) -> FaceInfoResponse:
    if face_idx < 0 or face_idx >= NUM_FACES:
        raise ValueError(f"Face index must be 0-{NUM_FACES - 1}")
    params = get_face_parameters(face_idx)
    return FaceInfoResponse(
        index=params["index"],
        centre=params["centre"],
        neighbors=params["neighbors"],
        resonance=float(params["resonance"]),
        phi_weight=float(params["phi_weight"]),
    )


def get_telemetry() -> TelemetryResponse:
    metrics = telemetry.get_metrics()
    return TelemetryResponse(
        metrics=metrics,
        counters=metrics.get("counters", {}),
        histograms=telemetry.get_histograms(),
        uptime_seconds=metrics["uptime_seconds"],
    )


def get_prometheus_metrics() -> str:
    return telemetry.to_prometheus()
