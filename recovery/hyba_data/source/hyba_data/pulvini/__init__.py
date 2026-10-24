"""
PULVINI φ²⁰ - Tier-1, Tier-2 & Tier-3 Global Adaptive Reliability Fabric

Tier-1: Drift protection, circuit breaker, incident management, oracle ensemble, alerting
Tier-2: Distributed quorum, SLO engine, predictive forecasting, global coordination
Tier-3: Theta optimization, partition-tolerant rings, drift ledger, failover
"""

from .alerts import AlertManager
from .circuit import CircuitBreaker
from .coordinator import GlobalCoordinator

# Tier-1 Components
from .drift import DriftProtector, JobRecord
from .drift_protector_tier2 import BaseDriftProtector, Tier2DriftProtector
from .failover import FailoverOrchestrator
from .forecast import DriftForecaster
from .grafana import GrafanaAnnotations
from .incidents import DriftIncident, IncidentManager
from .ledger import DriftLedger
from .oracle import OracleEnsemble, PhiOracle

# Tier-2 Components
from .quorum import DriftQuorum, QuorumVote
from .quorum_ring import QuorumRing
from .slo import SLOEngine
from .supervisor import Tier3Supervisor

# Tier-3 Components
from .theta_optimizer import GlobalThetaOptimizer, ThetaProposal

__version__ = "1.0.0"
__all__ = [
    # Tier-1
    "DriftProtector",
    "JobRecord",
    "CircuitBreaker",
    "DriftIncident",
    "IncidentManager",
    "GrafanaAnnotations",
    "PhiOracle",
    "OracleEnsemble",
    "AlertManager",
    # Tier-2
    "DriftQuorum",
    "QuorumVote",
    "SLOEngine",
    "DriftForecaster",
    "GlobalCoordinator",
    "Tier2DriftProtector",
    "BaseDriftProtector",
    # Tier-3
    "GlobalThetaOptimizer",
    "ThetaProposal",
    "QuorumRing",
    "DriftLedger",
    "FailoverOrchestrator",
    "Tier3Supervisor",
]
