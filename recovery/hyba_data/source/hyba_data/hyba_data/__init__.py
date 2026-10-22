"""HYBA_DATA — Quantum-Geometric Optimization Framework.

pip install pulvini

Core: M32 manifold, φ-resonance oracle, structured geodesic search.
Resultant VQC integration for variational quantum circuits.

Author: Andre Taylor-Morris
Version: 9.0.0
"""

__version__ = "9.0.0"

# Core manifold geometry
from .core import (
    M32, ADJ, NUM_FACES,
    voronoi_cached, clear_voronoi_cache,
    embed_on_manifold, phi_resonance_face, get_face_parameters,
)

# Framework abstractions
from .framework.manifold import Manifold, ManifoldConfig
from .framework.manifolds import M32Manifold, GrassmannianManifold, StiefelManifold
from .framework.oracle import Oracle, OracleConfig
from .framework.oracles import (
    PhiResonanceOracle, CombinatorialOracle, ContinuousOracle,
    RastriginOracle, RosenbrockOracle, AckleyOracle, SphereOracle,
)
from .framework.manifold_search import ManifoldSearch, ManifoldSearchConfig
from .framework.manifold_constructors import (
    ManifoldConstructor, ManifoldType,
    GoldenRatioConfig, FibonacciConfig, LieGroupConfig,
    GoldenRatioSphereManifold, FibonacciLatticeManifold,
    IcosahedralManifold, DodecahedralManifold, LieGroupManifold,
    create_manifold_constructor,
)

# Operators and solvers may require optional dependencies
try:
    from .framework.operator import Operator, OperatorConfig
    from .framework.operators import (
        MCMCOperator, QuantumWalkOperator,
        RiemannianFlowOperator, TensorNetworkOperator, VariationalOperator,
    )
except ImportError:
    pass

try:
    from .framework.solver import Solver, SolverConfig, SolverResult
    from .framework.solvers import (
        MCMCSolver, QuantumWalkSolver, RiemannianSolver,
        HybridSolver, VariationalSolver,
    )
except ImportError:
    pass

# Security, Scalability, Chaos Engineering
try:
    from .security import (
        InputValidator, RateLimiter, APIKeyManager, AuditLogger,
        EncryptionManager, SecurityContext, SecurityConfig,
    )
except ImportError:
    pass

try:
    from .scalability import (
        LoadTester, LoadTestResult, ConnectionPool, ResourceMonitor,
        AutoScaler, ScalingConfig, ScalingMetrics,
    )
except ImportError:
    pass

try:
    from .chaos import (
        FaultInjector, FaultType, CircuitBreaker, CircuitState,
        RetryPolicy, Bulkhead, ChaosExperiment, ChaosExperimentRunner,
        ChaosConfig, ResilienceResult,
    )
except ImportError:
    pass

# Enterprise/Government modules
try:
    from .compliance import (
        ComplianceFramework, ComplianceRequirement,
        ComplianceEngine, ComplianceReport,
    )
except ImportError:
    pass

try:
    from .audit import (
        AuditEvent, AuditTrail, ForensicsReport,
    )
except ImportError:
    pass

try:
    from .disaster_recovery import (
        Region, ReplicationConfig, DisasterRecoveryEngine,
        FailoverResult, DRHealthReport,
    )
except ImportError:
    pass

try:
    from .zero_trust import (
        SecurityLevel, AccessDecision, UserContext, Resource,
        ZeroTrustSecurity, SessionManager,
    )
except ImportError:
    pass

try:
    from .data_sovereignty import (
        DataClassification, DataSovereigntyEngine,
        SovereigntyReport, RegionalKeyManager,
    )
except ImportError:
    pass



# Hermitten Billing System (25% of GPU savings)
try:
    from .hermitten_billing import (
        GPUMetrics, WorkloadSavings, HermittenBill,
        WorkloadCategory, WORKLOAD_CATEGORIES,
        HermittenBillingService,
    )
except Exception:
    pass

# Subscription & Tier Management (5 tiers: Free, Pro, Team, Enterprise, Government)
try:
    from .subscription import (
        Tier, BillingPeriod, TierQuota, TierFeatures, Pricing, TierDefinition,
        TIER_DEFINITIONS, TIER_ORDER,
        SubscriptionService, Subscription, UsageRecord, Invoice,
        TierMiddleware, require_feature, require_quota, require_tier,
    )
except Exception:
    pass

# Enterprise Platform (complete 6-layer stack)
try:
    from .enterprise import (
        CompleteSovereigntyEngine, PlatformConfig, PlatformStatus, PlatformLayer,
        ROICalculator, ROIReport,
    )
except ImportError:
    pass

__all__ = [
        "GPUMetrics", "WorkloadSavings", "HermittenBill",
        "WorkloadCategory", "WORKLOAD_CATEGORIES",
        "HermittenBillingService",

        "Tier", "BillingPeriod", "TierQuota", "TierFeatures", "Pricing",
        "TierDefinition", "TIER_DEFINITIONS", "TIER_ORDER",
        "SubscriptionService", "Subscription", "UsageRecord", "Invoice",
        "TierMiddleware", "require_feature", "require_quota", "require_tier",

    # Core
    "M32", "ADJ", "NUM_FACES",
    "voronoi_cached", "clear_voronoi_cache", "embed_on_manifold", "phi_resonance_face", "get_face_parameters",
    # Framework
    "Manifold", "ManifoldConfig",
    "M32Manifold", "GrassmannianManifold", "StiefelManifold",
    "Oracle", "OracleConfig",
    "PhiResonanceOracle", "CombinatorialOracle", "ContinuousOracle",
    "RastriginOracle", "RosenbrockOracle", "AckleyOracle", "SphereOracle",
    "ManifoldSearch", "ManifoldSearchConfig",
    "ManifoldConstructor", "ManifoldType",
    "GoldenRatioSphereManifold", "FibonacciLatticeManifold",
    "IcosahedralManifold", "DodecahedralManifold", "LieGroupManifold",
    # Operators
    "Operator", "OperatorConfig",
    "MCMCOperator", "QuantumWalkOperator",
    "RiemannianFlowOperator", "TensorNetworkOperator", "VariationalOperator",
    # Solvers
    "Solver", "SolverConfig", "SolverResult",
    "MCMCSolver", "QuantumWalkSolver", "RiemannianSolver",
    "HybridSolver", "VariationalSolver",
    # Security
    "InputValidator", "RateLimiter", "APIKeyManager", "AuditLogger",
    "EncryptionManager", "SecurityContext", "SecurityConfig",
    # Scalability
    "LoadTester", "LoadTestResult", "ConnectionPool", "ResourceMonitor",
    "AutoScaler", "ScalingConfig", "ScalingMetrics",
    # Chaos Engineering
    "FaultInjector", "FaultType", "CircuitBreaker", "CircuitState",
    "RetryPolicy", "Bulkhead", "ChaosExperiment", "ChaosExperimentRunner",
    "ChaosConfig", "ResilienceResult",
    # Compliance
    "ComplianceFramework", "ComplianceRequirement",
    "ComplianceEngine", "ComplianceReport",
    # Audit & Forensics
    "AuditEvent", "AuditTrail", "ForensicsReport",
    # Disaster Recovery
    "Region", "ReplicationConfig", "DisasterRecoveryEngine",
    "FailoverResult", "DRHealthReport",
    # Zero-Trust Security
    "SecurityLevel", "AccessDecision", "UserContext", "Resource",
    "ZeroTrustSecurity", "SessionManager",
    # Data Sovereignty
    "DataClassification", "DataSovereigntyEngine",
    "SovereigntyReport", "RegionalKeyManager",
    # Enterprise Platform
    "CompleteSovereigntyEngine", "PlatformConfig", "PlatformStatus", "PlatformLayer",
    "ROICalculator", "ROIReport",
]
