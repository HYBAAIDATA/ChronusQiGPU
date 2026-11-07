"""In-process cluster bookkeeping for Chronus.

Single-process node registry and workload assignment structures. This is
not a networked distributed runtime; no consensus or replication executes.
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