"""
HYBA_DATA Python SDK Client.

Provides a unified interface for both local (in-process) and remote
(HTTP API) access to the HYBA_DATA optimization framework.
"""
from __future__ import annotations
import json
import urllib.request
import urllib.error
from typing import Any, Optional

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


class HybaDataClient:
    """
    Unified client for HYBA_DATA optimization framework.

    Modes:
    - Local (default): Direct in-process execution, no server needed.
    - Remote: HTTP requests to a running HYBA_DATA API server.

    Args:
        base_url: API server URL (None for local mode)
        timeout: HTTP request timeout in seconds (remote mode only)
    """

    MANIFOLDS = {
        "m32", "grassmannian", "stiefel", "golden_ratio_sphere",
        "fibonacci_lattice", "icosahedral", "dodecahedral", "lie_group",
    }
    ORACLES = {
        "phi_resonance", "combinatorial", "rastrigin",
        "rosenbrock", "ackley", "sphere",
    }
    OPERATORS = {
        "mcmc", "quantum_walk", "riemannian_flow",
        "tensor_network", "variational",
    }
    SOLVERS = {
        "mcmc", "quantum_walk", "riemannian", "hybrid", "variational",
    }

    def __init__(self, base_url: Optional[str] = None, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/") if base_url else None
        self.timeout = timeout
        self._local = base_url is None

    # ── Local component factories ───────────────────────────────

    def _make_manifold(self, manifold_type: str, **params):
        if manifold_type == "m32":
            return M32Manifold()
        elif manifold_type == "grassmannian":
            return GrassmannianManifold(params.get("p", 2), params.get("n", 4))
        elif manifold_type == "stiefel":
            return StiefelManifold(params.get("p", 2), params.get("n", 4))
        else:
            mc = ManifoldConstructor()
            mt_map = {
                "golden_ratio_sphere": ManifoldType.GOLDEN_RATIO_SPHERE,
                "fibonacci_lattice": ManifoldType.FIBONACCI_LATTICE,
                "icosahedral": ManifoldType.ICOSAHEDRAL,
                "dodecahedral": ManifoldType.DODECAHEDRAL,
                "lie_group": ManifoldType.LIE_GROUP,
            }
            return mc.construct(mt_map[manifold_type], **params)

    def _make_oracle(self, oracle_type: str, **params):
        factories = {
            "phi_resonance": lambda: PhiResonanceOracle(),
            "combinatorial": lambda: CombinatorialOracle(params.get("cost_function", lambda x: float(x % 100))),
            "rastrigin": lambda: RastriginOracle(dimension=params.get("dimension", 5)),
            "rosenbrock": lambda: RosenbrockOracle(dimension=params.get("dimension", 5)),
            "ackley": lambda: AckleyOracle(dimension=params.get("dimension", 5)),
            "sphere": lambda: SphereOracle(dimension=params.get("dimension", 5)),
        }
        return factories[oracle_type]()

    def _make_operator(self, operator_type: str, **params):
        factories = {
            "mcmc": lambda: MCMCOperator(),
            "quantum_walk": lambda: QuantumWalkOperator(walk_type=params.get("walk_type", "continuous")),
            "riemannian_flow": lambda: RiemannianFlowOperator(method=params.get("method", "gradient_descent")),
            "tensor_network": lambda: TensorNetworkOperator(max_bond_dim=params.get("max_bond_dim", 32)),
            "variational": lambda: VariationalOperator(method=params.get("method", "qaoa"), num_layers=params.get("num_layers", 3)),
        }
        return factories[operator_type]()

    def _make_solver(self, solver_type: str, manifold, oracle, operator, config):
        factories = {
            "mcmc": lambda: MCMCSolver(manifold, oracle, operator, config),
            "quantum_walk": lambda: QuantumWalkSolver(manifold, oracle, operator, config),
            "riemannian": lambda: RiemannianSolver(manifold, oracle, operator, config),
            "variational": lambda: VariationalSolver(manifold, oracle, operator, config),
            "hybrid": lambda: HybridSolver(manifold, oracle, operator if isinstance(operator, list) else [operator], config),
        }
        return factories[solver_type]()

    # ── Public API ──────────────────────────────────────────────

    def embed(self, manifold_type: str = "m32", point: int = 0, **params) -> list[float]:
        if self._local:
            m = self._make_manifold(manifold_type, **params)
            return m.embed(point).tolist()
        return self._post("/v1/manifold/embed", {
            "manifold_type": manifold_type, "point": point, "manifold_params": params,
        })["embedding"]

    def evaluate(self, oracle_type: str = "phi_resonance", point: int = 0, **params) -> float:
        if self._local:
            o = self._make_oracle(oracle_type, **params)
            return float(o.evaluate(point))
        return self._post("/v1/oracle/evaluate", {
            "oracle_type": oracle_type, "point": point, "oracle_params": params,
        })["value"]

    def optimize(
        self,
        manifold_type: str = "m32",
        oracle_type: str = "phi_resonance",
        operator_type: str = "mcmc",
        solver_type: str = "mcmc",
        initial_point: Optional[int] = None,
        max_iterations: int = 1000,
        max_time_seconds: float = 60.0,
        **params,
    ) -> dict[str, Any]:
        if self._local:
            manifold = self._make_manifold(manifold_type)
            oracle = self._make_oracle(oracle_type)
            operator = self._make_operator(operator_type)
            config = SolverConfig(max_iterations=max_iterations, max_time_seconds=max_time_seconds, verbose=False)
            solver = self._make_solver(solver_type, manifold, oracle, operator, config)
            result = solver.solve(initial_point)
            return {
                "best_point": result.best_point,
                "best_value": float(result.best_value),
                "iterations": result.iterations,
                "elapsed_time": float(result.elapsed_time),
                "converged": result.converged,
                "evaluation_count": result.evaluation_count,
            }
        return self._post("/v1/optimize", {
            "manifold_type": manifold_type, "oracle_type": oracle_type,
            "operator_type": operator_type, "solver_type": solver_type,
            "initial_point": initial_point, "max_iterations": max_iterations,
            "max_time_seconds": max_time_seconds,
        })

    def search(
        self,
        manifold_type: str = "m32",
        oracle_type: str = "phi_resonance",
        operator_type: str = "mcmc",
        solver_type: str = "mcmc",
        num_runs: int = 3,
        max_iterations: int = 500,
        max_time_seconds: float = 30.0,
        enable_parallel: bool = True,
        num_workers: int = 4,
    ) -> dict[str, Any]:
        if self._local:
            manifold = self._make_manifold(manifold_type)
            oracle = self._make_oracle(oracle_type)
            operator = self._make_operator(operator_type)
            config = SolverConfig(max_iterations=max_iterations, max_time_seconds=max_time_seconds, verbose=False)
            solver = self._make_solver(solver_type, manifold, oracle, operator, config)
            search = ManifoldSearch(
                manifold, oracle, operator, solver,
                ManifoldSearchConfig(enable_parallel=enable_parallel, num_workers=num_workers, verbose=False),
            )
            result = search.optimize(num_runs=num_runs)
            stats = search.get_statistics()
            return {
                "best_point": result.best_point,
                "best_value": float(result.best_value),
                "iterations": result.iterations,
                "elapsed_time": float(result.elapsed_time),
                "converged": result.converged,
                "evaluation_count": result.evaluation_count,
                "statistics": {k: float(v) if isinstance(v, (int, float)) else v for k, v in stats.items()},
            }
        return self._post("/v1/search", {
            "manifold_type": manifold_type, "oracle_type": oracle_type,
            "operator_type": operator_type, "solver_type": solver_type,
            "num_runs": num_runs, "max_iterations": max_iterations,
            "max_time_seconds": max_time_seconds, "enable_parallel": enable_parallel,
            "num_workers": num_workers,
        })

    def list_components(self) -> dict[str, Any]:
        if self._local:
            return {
                "manifolds": list(self.MANIFOLDS),
                "oracles": list(self.ORACLES),
                "operators": list(self.OPERATORS),
                "solvers": list(self.SOLVERS),
            }
        return self._get("/v1/components")

    def health(self) -> dict[str, Any]:
        if self._local:
            return {"status": "healthy", "version": "9.0.0"}
        return self._get("/health")

    def telemetry(self) -> dict[str, Any]:
        if self._local:
            return {"message": "Telemetry available in remote mode"}
        return self._get("/v1/telemetry")

    # ── HTTP helpers ────────────────────────────────────────────

    def _post(self, path: str, data: dict) -> dict:
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(
            url, data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"API error {e.code}: {e.read().decode()}") from e

    def _get(self, path: str) -> dict:
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"API error {e.code}: {e.read().decode()}") from e
