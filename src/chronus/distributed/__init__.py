"""Chronus Quantum iGPU Distributed Systems Layer.

Production-ready distributed execution with failure injection, health checking,
cluster orchestration, and consensus protocols for hyperscale deployment.
"""

from chronus.distributed.failure_injection import (
    DistributedError,
    FailureInjected,
    FailureInjectionEngine,
    FailureType,
    NodeUnhealthy,
)
from chronus.distributed.health_check import (
    HealthCheckResult,
    HealthCheckService,
    NodeStatus,
)
from chronus.distributed.orchestrator import (
    ClusterOrchestrator,
    ConsensusProtocol,
    ClusterState,
    NodeInfo,
    WorkloadAssignment,
)

__version__ = "36.0.0"
__all__ = [
    "FailureInjectionEngine",
    "FailureType",
    "DistributedError",
    "FailureInjected",
    "NodeUnhealthy",
    "HealthCheckService",
    "HealthCheckResult",
    "NodeStatus",
    "ClusterOrchestrator",
    "ConsensusProtocol",
    "ClusterState",
    "NodeInfo",
    "WorkloadAssignment",
]