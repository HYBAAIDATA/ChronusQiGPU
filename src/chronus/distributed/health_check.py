"""Health Check Service for Chronus Distributed Systems.

Production-ready health checking with component-level status tracking,
failure detection, and automatic recovery coordination.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class NodeStatus(str, Enum):
    """Node status levels for distributed health checks."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"
    MAINTENANCE = "MAINTENANCE"


@dataclass
class HealthCheckResult:
    """Result of a single health check."""

    component: str
    status: NodeStatus
    latency_ms: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)



class HealthCheckService:
    """Distributed health check service with failure detection.

    Monitors health of all Chronus cluster nodes and components,
    detects failures, and coordinates recovery actions.
    """

    def __init__(
        self,
        check_interval_seconds: float = 10.0,
        unhealthy_threshold: int = 3,
        recovery_threshold: int = 2,
    ) -> None:
        self.check_interval_seconds = check_interval_seconds
        self.unhealthy_threshold = unhealthy_threshold
        self.recovery_threshold = recovery_threshold
        self._checks: Dict[str, Callable[[], HealthCheckResult]] = {}
        self._results: Dict[str, List[HealthCheckResult]] = {}
        self._failure_counts: Dict[str, int] = {}
        self._success_counts: Dict[str, int] = {}
        self._node_statuses: Dict[str, NodeStatus] = {}
        self._check_count = 0

    def register_check(
        self, component: str, check_func: Callable[[], HealthCheckResult]
    ) -> None:
        self._checks[component] = check_func
        self._results[component] = []
        self._failure_counts[component] = 0
        self._success_counts[component] = 0
        self._node_statuses[component] = NodeStatus.UNKNOWN

    def run_check(self, component: str) -> HealthCheckResult:
        if component not in self._checks:
            raise KeyError(f"Component '{component}' not registered")

        check_func = self._checks[component]
        result = check_func()
        self._results[component].append(result)
        self._check_count += 1

        if result.status in (NodeStatus.HEALTHY, NodeStatus.DEGRADED):
            self._success_counts[component] += 1
            self._failure_counts[component] = 0
        else:
            self._failure_counts[component] += 1
            self._success_counts[component] = 0

        if self._failure_counts[component] >= self.unhealthy_threshold:
            self._node_statuses[component] = NodeStatus.UNHEALTHY
        elif self._success_counts[component] >= self.recovery_threshold:
            self._node_statuses[component] = NodeStatus.HEALTHY
        elif result.status == NodeStatus.DEGRADED:
            self._node_statuses[component] = NodeStatus.DEGRADED

        return result

    def run_all_checks(self) -> Dict[str, HealthCheckResult]:
        results: Dict[str, HealthCheckResult] = {}
        for component in self._checks:
            results[component] = self.run_check(component)
        return results

    def get_component_status(self, component: str) -> NodeStatus:
        return self._node_statuses.get(component, NodeStatus.UNKNOWN)

    def is_cluster_healthy(self) -> bool:
        return all(
            status in (NodeStatus.HEALTHY, NodeStatus.DEGRADED)
            for status in self._node_statuses.values()
        )

    def get_unhealthy_components(self) -> List[str]:
        return [
            comp
            for comp, status in self._node_statuses.items()
            if status == NodeStatus.UNHEALTHY
        ]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "registered_components": len(self._checks),
            "total_checks": self._check_count,
            "healthy_components": sum(
                1 for s in self._node_statuses.values() if s == NodeStatus.HEALTHY
            ),
            "degraded_components": sum(
                1 for s in self._node_statuses.values() if s == NodeStatus.DEGRADED
            ),
            "unhealthy_components": sum(
                1 for s in self._node_statuses.values() if s == NodeStatus.UNHEALTHY
            ),
            "cluster_healthy": self.is_cluster_healthy(),
        }
    def to_dict(self) -> Dict[str, Any]:
        return {
            "component": self.component,
            "status": self.status.value,
            "latency_ms": self.latency_ms,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
            "details": self.details,
        }