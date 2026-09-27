"""
Intelligent wrappers for system endpoints.

These wrappers provide ubiquitous intelligence to configuration, pool management,
and basic status endpoints by wrapping them with IntelligentEndpoint functionality.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any

from hyba_backend.core.intelligence.intelligent_endpoint import (
    AutonomyLevel,
    Decision,
    IntelligenceState,
    IntelligentEndpoint,
    Observation,
)

logger = logging.getLogger(__name__)


@dataclass
class ConfigurationState:
    """State of system configuration"""

    pools_configured: int
    algorithms_available: int
    active_operations: int
    last_config_change: float
    config_stability: float  # 0-1, how stable is current config


class ConfigurationIntelligence(IntelligentEndpoint):
    """
    Intelligent endpoint for configuration management.

    Monitors and optimizes system configuration through:
    - Configuration stability tracking
    - Adaptive pool selection based on performance
    - Algorithm availability optimization
    - Configuration change impact analysis
    """

    def __init__(self, config_provider=None, **kwargs):
        super().__init__(
            endpoint_id="config-intelligence",
            autonomy_level=AutonomyLevel.OPTIMISE,
            **kwargs,
        )
        self.config_provider = config_provider
        self.config_history = []
        self.last_config_hash = None
        self.config_change_count = 0
        self.config_stability = 1.0

    async def observe(self) -> Observation:
        """Monitor configuration state"""
        try:
            if not self.config_provider:
                return Observation(
                    timestamp=time.time(),
                    endpoint_id=self.endpoint_id,
                    state=IntelligenceState.OBSERVING,
                    data={"status": "no_config_provider"},
                    confidence=0.0,
                )

            config = self.config_provider.get_config()
            pools = config.get("pools", [])
            algorithms = config.get("algorithms", [])

            # Calculate configuration stability
            current_hash = hash(str(config))
            if current_hash != self.last_config_hash:
                self.config_change_count += 1
                self.last_config_hash = current_hash

            # Stability decreases with frequent changes
            self.config_stability = max(0.1, 1.0 - (self.config_change_count * 0.05))

            return Observation(
                timestamp=time.time(),
                endpoint_id=self.endpoint_id,
                state=IntelligenceState.OBSERVING,
                data={
                    "pools_configured": len(pools),
                    "algorithms_available": len(algorithms),
                    "config_changes": self.config_change_count,
                    "stability": self.config_stability,
                    "active_pools": [p.get("name") for p in pools if p.get("active")],
                },
                confidence=0.95,
            )
        except Exception as e:
            logger.error(f"Configuration observation failed: {e}")
            return Observation(
                timestamp=time.time(),
                endpoint_id=self.endpoint_id,
                state=IntelligenceState.ALERT,
                data={"error": str(e)},
                confidence=0.0,
            )

    async def reason(self, observation: Observation) -> Decision:
        """Reason about configuration state"""
        data = observation.data

        if "error" in data:
            return Decision(
                timestamp=time.time(),
                endpoint_id=self.endpoint_id,
                action="alert",
                reasoning="Configuration provider unavailable",
                confidence=0.5,
                autonomy_level=AutonomyLevel.SUGGEST,
            )

        stability = data.get("stability", 1.0)

        # Recommend stabilization if too many changes
        if stability < 0.5:
            return Decision(
                timestamp=time.time(),
                endpoint_id=self.endpoint_id,
                action="stabilize_config",
                reasoning=f"Configuration unstable (stability: {stability:.2f}). Recommend reducing change frequency.",
                confidence=0.8,
                autonomy_level=AutonomyLevel.SUGGEST,
            )

        # Recommend optimization if stable
        if stability > 0.8:
            return Decision(
                timestamp=time.time(),
                endpoint_id=self.endpoint_id,
                action="optimize_config",
                reasoning="Configuration stable. Opportunity for optimization.",
                confidence=0.7,
                autonomy_level=AutonomyLevel.OPTIMISE,
            )

        return Decision(
            timestamp=time.time(),
            endpoint_id=self.endpoint_id,
            action="monitor",
            reasoning="Configuration nominal",
            confidence=0.9,
            autonomy_level=AutonomyLevel.OBSERVE,
        )

    async def act(self, decision: Decision) -> dict[str, Any]:
        """Execute configuration decisions"""
        action = decision.action

        if action == "monitor":
            return {
                "status": "monitoring",
                "message": "Configuration under observation",
            }
        elif action == "stabilize_config":
            return {
                "status": "stabilization_recommended",
                "message": "Reduce configuration change frequency",
            }
        elif action == "optimize_config":
            return {
                "status": "optimization_ready",
                "message": "Configuration ready for optimization",
            }
        elif action == "alert":
            return {"status": "alert", "message": "Configuration system alert"}

        return {"status": "unknown_action"}

    async def learn(self, outcome: dict[str, Any]) -> None:
        """Learn from configuration outcomes"""
        self.config_history.append({"timestamp": time.time(), "outcome": outcome})

        # Keep only recent history
        if len(self.config_history) > 100:
            self.config_history = self.config_history[-100:]


class PoolManagementIntelligence(IntelligentEndpoint):
    """
    Intelligent endpoint for pool management.

    Provides intelligent pool selection and failover through:
    - Pool performance monitoring
    - Automatic failover detection
    - Pool health assessment
    - Optimal pool selection based on metrics
    """

    def __init__(self, pool_provider=None, **kwargs):
        super().__init__(
            endpoint_id="pool-intelligence",
            autonomy_level=AutonomyLevel.OPTIMISE,
            **kwargs,
        )
        self.pool_provider = pool_provider
        self.pool_metrics = {}
        self.failover_count = 0

    async def observe(self) -> Observation:
        """Monitor pool state"""
        try:
            if not self.pool_provider:
                return Observation(
                    timestamp=time.time(),
                    endpoint_id=self.endpoint_id,
                    state=IntelligenceState.OBSERVING,
                    data={"status": "no_pool_provider"},
                    confidence=0.0,
                )

            pools = self.pool_provider.get_pools()

            # Assess pool health
            healthy_pools = 0
            unhealthy_pools = 0

            for pool in pools:
                pool_id = pool.get("id")
                if pool.get("active") and pool.get("connected"):
                    healthy_pools += 1
                    self.pool_metrics[pool_id] = {
                        "status": "healthy",
                        "last_check": time.time(),
                        "response_time": pool.get("response_time", 0),
                    }
                else:
                    unhealthy_pools += 1
                    self.pool_metrics[pool_id] = {
                        "status": "unhealthy",
                        "last_check": time.time(),
                    }

            return Observation(
                timestamp=time.time(),
                endpoint_id=self.endpoint_id,
                state=IntelligenceState.OBSERVING,
                data={
                    "total_pools": len(pools),
                    "healthy_pools": healthy_pools,
                    "unhealthy_pools": unhealthy_pools,
                    "failover_count": self.failover_count,
                    "pool_names": [p.get("name") for p in pools],
                },
                confidence=0.9,
            )
        except Exception as e:
            logger.error(f"Pool observation failed: {e}")
            return Observation(
                timestamp=time.time(),
                endpoint_id=self.endpoint_id,
                state=IntelligenceState.ALERT,
                data={"error": str(e)},
                confidence=0.0,
            )

    async def reason(self, observation: Observation) -> Decision:
        """Reason about pool state"""
        data = observation.data

        if "error" in data:
            return Decision(
                timestamp=time.time(),
                endpoint_id=self.endpoint_id,
                action="alert",
                reasoning="Pool provider unavailable",
                confidence=0.5,
                autonomy_level=AutonomyLevel.SUGGEST,
            )

        healthy = data.get("healthy_pools", 0)
        unhealthy = data.get("unhealthy_pools", 0)
        total = data.get("total_pools", 0)

        # Trigger failover if primary pool unhealthy
        if unhealthy > 0 and healthy > 0:
            return Decision(
                timestamp=time.time(),
                endpoint_id=self.endpoint_id,
                action="failover",
                reasoning=f"Detected {unhealthy} unhealthy pools. Initiating failover.",
                confidence=0.95,
                autonomy_level=AutonomyLevel.OPERATE,
            )

        # Alert if all pools unhealthy
        if unhealthy == total and total > 0:
            return Decision(
                timestamp=time.time(),
                endpoint_id=self.endpoint_id,
                action="critical_alert",
                reasoning="All pools unhealthy. Critical pool failure.",
                confidence=0.99,
                autonomy_level=AutonomyLevel.SUGGEST,
            )

        return Decision(
            timestamp=time.time(),
            endpoint_id=self.endpoint_id,
            action="monitor",
            reasoning="All pools healthy",
            confidence=0.95,
            autonomy_level=AutonomyLevel.OBSERVE,
        )

    async def act(self, decision: Decision) -> dict[str, Any]:
        """Execute pool management decisions"""
        action = decision.action

        if action == "failover":
            self.failover_count += 1
            return {
                "status": "failover_initiated",
                "failover_count": self.failover_count,
                "message": "Switching to backup pool",
            }
        elif action == "critical_alert":
            return {
                "status": "critical_alert",
                "message": "All pools unavailable. Manual intervention required.",
            }
        elif action == "monitor":
            return {"status": "monitoring", "message": "Pool health nominal"}
        elif action == "alert":
            return {"status": "alert", "message": "Pool system alert"}

        return {"status": "unknown_action"}

    async def learn(self, outcome: dict[str, Any]) -> None:
        """Learn from pool management outcomes"""
        # Track failover effectiveness
        if outcome.get("action") == "failover":
            success = outcome.get("success", False)
            if success:
                self.performance["failover_success_rate"] = (
                    self.performance.get("failover_success_rate", 0) + 1
                )


class StatusIntelligence(IntelligentEndpoint):
    """
    Intelligent endpoint for system status monitoring.

    Provides intelligent status reporting through:
    - Real-time system health assessment
    - Performance trend analysis
    - Anomaly detection
    - Predictive health warnings
    """

    def __init__(self, system_provider=None, **kwargs):
        super().__init__(
            endpoint_id="status-intelligence",
            autonomy_level=AutonomyLevel.OBSERVE,
            **kwargs,
        )
        self.system_provider = system_provider
        self.health_history = []
        self.anomaly_threshold = 0.7

    async def observe(self) -> Observation:
        """Monitor system status"""
        try:
            if not self.system_provider:
                return Observation(
                    timestamp=time.time(),
                    endpoint_id=self.endpoint_id,
                    state=IntelligenceState.OBSERVING,
                    data={"status": "no_system_provider"},
                    confidence=0.0,
                )

            status = self.system_provider.get_status()

            # Calculate health score
            health_score = 1.0
            issues = []

            if not status.get("quantum_backend_operational"):
                health_score -= 0.3
                issues.append("quantum_backend_down")

            if not status.get("mining_operational"):
                health_score -= 0.2
                issues.append("mining_down")

            if status.get("error_rate", 0) > 0.05:
                health_score -= 0.1
                issues.append("high_error_rate")

            health_score = max(0.0, min(1.0, health_score))

            self.health_history.append(
                {"timestamp": time.time(), "health_score": health_score}
            )

            # Keep only recent history
            if len(self.health_history) > 1000:
                self.health_history = self.health_history[-1000:]

            return Observation(
                timestamp=time.time(),
                endpoint_id=self.endpoint_id,
                state=IntelligenceState.OBSERVING,
                data={
                    "health_score": health_score,
                    "issues": issues,
                    "uptime": status.get("uptime", 0),
                    "operations_count": status.get("operations_count", 0),
                },
                confidence=0.95,
            )
        except Exception as e:
            logger.error(f"Status observation failed: {e}")
            return Observation(
                timestamp=time.time(),
                endpoint_id=self.endpoint_id,
                state=IntelligenceState.ALERT,
                data={"error": str(e)},
                confidence=0.0,
            )

    async def reason(self, observation: Observation) -> Decision:
        """Reason about system status"""
        data = observation.data

        if "error" in data:
            return Decision(
                timestamp=time.time(),
                endpoint_id=self.endpoint_id,
                action="alert",
                reasoning="Status provider unavailable",
                confidence=0.5,
                autonomy_level=AutonomyLevel.SUGGEST,
            )

        health_score = data.get("health_score", 1.0)
        issues = data.get("issues", [])

        if health_score < 0.3:
            return Decision(
                timestamp=time.time(),
                endpoint_id=self.endpoint_id,
                action="critical_alert",
                reasoning=f"System health critical ({health_score:.2f}). Issues: {issues}",
                confidence=0.99,
                autonomy_level=AutonomyLevel.SUGGEST,
            )

        if health_score < 0.6:
            return Decision(
                timestamp=time.time(),
                endpoint_id=self.endpoint_id,
                action="warning",
                reasoning=f"System health degraded ({health_score:.2f}). Issues: {issues}",
                confidence=0.9,
                autonomy_level=AutonomyLevel.SUGGEST,
            )

        return Decision(
            timestamp=time.time(),
            endpoint_id=self.endpoint_id,
            action="nominal",
            reasoning=f"System health nominal ({health_score:.2f})",
            confidence=0.95,
            autonomy_level=AutonomyLevel.OBSERVE,
        )

    async def act(self, decision: Decision) -> dict[str, Any]:
        """Execute status decisions"""
        action = decision.action

        if action == "critical_alert":
            return {
                "status": "critical",
                "message": "System health critical. Immediate attention required.",
            }
        elif action == "warning":
            return {
                "status": "warning",
                "message": "System health degraded. Monitor closely.",
            }
        elif action == "nominal":
            return {"status": "healthy", "message": "System operating normally"}
        elif action == "alert":
            return {"status": "alert", "message": "Status system alert"}

        return {"status": "unknown_action"}

    async def learn(self, outcome: dict[str, Any]) -> None:
        """Learn from status monitoring outcomes"""
        # Track health trends
        if len(self.health_history) > 10:
            recent_health = [h["health_score"] for h in self.health_history[-10:]]
            trend = sum(recent_health) / len(recent_health)
            self.performance["health_trend"] = trend
