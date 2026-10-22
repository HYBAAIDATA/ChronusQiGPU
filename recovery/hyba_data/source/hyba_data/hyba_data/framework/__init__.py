"""
Generalized Quantum-Geometric Optimization Framework (v7.1–v9.0)

This framework abstracts quantum-mathematical machinery into a reusable,
pluggable library for attacking high-dimensional discrete optimization problems.

Core Components:
- Manifold: Abstract geometric space (M_32, Grassmannians, custom embeddings)
- Oracle: Cost function/fitness evaluation (cryptographic, combinatorial, physics)
- Operator: Quantum-inspired operators (quantum walk, Riemannian flow, tensor network)
- Solver: Composable solver algorithms (MCMC, hybrid, variational)

V9-V10 Extensions:
- Manifold Discovery: Automated symmetry detection and variational manifold learning
- Interference & Tunneling: First-class quantum-inspired primitives with scheduling
- Quantum Advantage: Empirical benchmarking for quantum advantage detection
- Visualization: Real-time rendering of search dynamics and manifold structure
- Collaboration: Interactive human-machine mathematical exploration interface
- Manifold Constructors: Extensible golden-ratio and Fibonacci-based structures

Author: Phi-Grover Development Team
Version: 9.0.0
Date: 2026-04-18
"""

from .manifold import Manifold, ManifoldConfig
from .manifolds import GrassmannianManifold, M32Manifold, StiefelManifold
from .oracle import Oracle, OracleConfig
from .operator import Operator, OperatorConfig
from .solver import Solver, SolverConfig, SolverResult
from .manifold_search import ManifoldSearch, ManifoldSearchConfig

# Concrete oracle implementations
from .oracles import CombinatorialOracle, ContinuousOracle, PhiResonanceOracle

# Concrete operator implementations
from .operators import (
    MCMCOperator,
    QuantumWalkOperator,
    RiemannianFlowOperator,
    TensorNetworkOperator,
    VariationalOperator,
)

# Concrete solver implementations
from .solvers import (
    HybridSolver,
    MCMCSolver,
    QuantumWalkSolver,
    RiemannianSolver,
    VariationalSolver,
)

# Manifold Constructors
from .manifold_constructors import (
    DodecahedralManifold,
    FibonacciConfig,
    FibonacciLatticeManifold,
    GoldenRatioConfig,
    GoldenRatioSphereManifold,
    IcosahedralManifold,
    LieGroupConfig,
    LieGroupManifold,
    ManifoldConstructor,
    ManifoldType,
    create_manifold_constructor,
)

__all__ = [
    # Core abstractions
    "Manifold", "ManifoldConfig", "Oracle", "OracleConfig",
    "Operator", "OperatorConfig", "Solver", "SolverConfig", "SolverResult",
    "ManifoldSearch", "ManifoldSearchConfig",
    # Concrete manifold implementations
    "M32Manifold", "GrassmannianManifold", "StiefelManifold",
    # Concrete oracle implementations
    "PhiResonanceOracle", "CombinatorialOracle", "ContinuousOracle",
    # Concrete operator implementations
    "MCMCOperator", "QuantumWalkOperator", "RiemannianFlowOperator",
    "TensorNetworkOperator", "VariationalOperator",
    # Concrete solver implementations
    "MCMCSolver", "QuantumWalkSolver", "RiemannianSolver",
    "HybridSolver", "VariationalSolver",
    # Manifold Constructors
    "ManifoldConstructor", "ManifoldType", "GoldenRatioConfig",
    "FibonacciConfig", "LieGroupConfig", "create_manifold_constructor",
    "GoldenRatioSphereManifold", "FibonacciLatticeManifold",
    "IcosahedralManifold", "DodecahedralManifold", "LieGroupManifold",
]

__version__ = "9.0.0"
