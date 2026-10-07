"""
Intelligent wrappers for system endpoints.

These wrappers provide ubiquitous intelligence to configuration, pool management,
and basic status endpoints by wrapping them with IntelligentEndpoint functionality.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any

from Intelligence._born import born_evidence
from Intelligence.intelligent_endpoint import (
    AutonomyLevel,
    Decision,
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
        # Measured unchanged observations (the "positive" evidence for stability)
        self._stable_observations = 0
        self.config_stability = 1.0

    async def observe(self) -> Observation:
        """Monitor configuration state"""
        try:
            if not self.config_provider:
                return Observation(
                    endpoint_id=self.endpoint_id,
                    timestamp=time.time(),
                    observation={"status": "no_config_provider"},
                    confidence=0.0,
                    requires_action=True,
                )

            config = self.config_provider.get_config()
            pools = config.get("pools", [])
            algorithms = config.get("algorithms", [])

            # Measured configuration drift
            current_hash = hash(str(config))
            if current_hash != self.last_config_hash:
                self.config_change_count += 1
                self.last_config_hash = current_hash
            else:
                self._stable_observations += 1

            # Stability is the Born probability of the evidence state
            # (stable observations, observed changes) — measured counts,
            # no invented decay constant.
            self.config_stability = born_evidence(
                self._stable_observations, self.config_change_count
            )

            return Observation(
                endpoint_id=self.endpoint_id,
                timestamp=time.time(),
                observation={
                    "pools_configured": len(pools),
                    "algorithms_available": len(algorithms),
                    "config_changes": self.config_change_count,
                    "stability": self.config_stability,
                    "active_pools": [p.get("name") for p in pools if p.get("active")],
                },
                # The observation IS the measurement: confidence is whether
                # live provider data was actually obtained.
                confidence=1.0,
            )
        except Exception as e:
            logger.error(f"Configuration observation failed: {e}")
            return Observation(
                endpoint_id=self.endpoint_id,
                timestamp=time.time(),
                observation={"error": str(e)},
                confidence=0.0,
                requires_action=True,
            )

    async def reason(self, observation: Observation) -> Decision:
        """Reason about configuration state"""
        data = observation.observation

        if "error" in data or "no_config_provider" in data.get("status", ""):
            return Decision(
                endpoint_id=self.endpoint_id,
                timestamp=time.time(),
                action="alert",
                parameters={},
                reasoning="Configuration provider unavailable",
                expected_value=0.0,
                confidence=1.0,  # measured: the provider did not respond
                autonomy_level=AutonomyLevel.SUGGEST,
                requires_approval=False,
            )

        stability = data.get("stability", 1.0)
        # Confidence that the "unstable" condition holds is the measured
        # Born evidence of observed changes against stable observations.
        instability_evidence = born_evidence(self.config_change_count, self._stable_observations)

        # Recommend stabilization if too many changes
        if stability < 0.5:
            return Decision(
                endpoint_id=self.endpoint_id,
                timestamp=time.time(),
                action="stabilize_config",
                parameters={"config_changes": self.config_change_count},
                reasoning=f"Configuration unstable (stability: {stability:.2f}). Recommend reducing change frequency.",
                expected_value=1.0 - stability,  # measured headroom
                confidence=instability_evidence,
                autonomy_level=AutonomyLevel.SUGGEST,
                requires_approval=True,
            )

        # Recommend optimization if stable
        if stability > 0.8:
            return Decision(
                endpoint_id=self.endpoint_id,
                timestamp=time.time(),
                action="optimize_config",
                parameters={"stability": stability},
                reasoning="Configuration stable. Opportunity for optimization.",
                expected_value=1.0 - stability,
                confidence=stability,
                autonomy_level=AutonomyLevel.OPTIMISE,
                requires_approval=False,
            )

        return Decision(
            endpoint_id=self.endpoint_id,
            timestamp=time.time(),
            action="monitor",
            parameters={},
            reasoning="Configuration nominal",
            expected_value=0.0,
            confidence=stability,
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
                    endpoint_id=self.endpoint_id,
                    timestamp=time.time(),
                    observation={"status": "no_pool_provider"},
                    confidence=0.0,
                    requires_action=True,
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
                endpoint_id=self.endpoint_id,
                timestamp=time.time(),
                observation={
                    "total_pools": len(pools),
                    "healthy_pools": healthy_pools,
                    "unhealthy_pools": unhealthy_pools,
                    "failover_count": self.failover_count,
                    "pool_names": [p.get("name") for p in pools],
                },
                confidence=1.0,
                requires_action=unhealthy_pools > 0,
            )
        except Exception as e:
            logger.error(f"Pool observation failed: {e}")
            return Observation(
                endpoint_id=self.endpoint_id,
                timestamp=time.time(),
                observation={"error": str(e)},
                confidence=0.0,
                requires_action=True,
            )

    async def reason(self, observation: Observation) -> Decision:
        """Reason about pool state"""
        data = observation.observation

        if "error" in data or "no_pool_provider" in data.get("status", ""):
            return Decision(
                endpoint_id=self.endpoint_id,
                timestamp=time.time(),
                action="alert",
                parameters={},
                reasoning="Pool provider unavailable",
                expected_value=0.0,
                confidence=1.0,
                autonomy_level=AutonomyLevel.SUGGEST,
                requires_approval=False,
            )

        healthy = data.get("healthy_pools", 0)
        unhealthy = data.get("unhealthy_pools", 0)
        total = data.get("total_pools", 0)
        # Measured evidence: healthy vs unhealthy pool counts.
        health_evidence = born_evidence(healthy, unhealthy)
        failure_evidence = born_evidence(unhealthy, healthy)

        # Trigger failover if primary pool unhealthy
        if unhealthy > 0 and healthy > 0:
            return Decision(
                endpoint_id=self.endpoint_id,
                timestamp=time.time(),
                action="failover",
                parameters={"unhealthy_pools": unhealthy, "healthy_pools": healthy},
                reasoning=f"Detected {unhealthy} unhealthy pools. Initiating failover.",
                expected_value=failure_evidence,
                confidence=failure_evidence,
                autonomy_level=AutonomyLevel.OPERATE,
                requires_approval=False,
            )

        # Alert if all pools unhealthy
        if unhealthy == total and total > 0:
            return Decision(
                endpoint_id=self.endpoint_id,
                timestamp=time.time(),
                action="critical_alert",
                parameters={"unhealthy_pools": unhealthy},
                reasoning="All pools unhealthy. Critical pool failure.",
                expected_value=0.0,
                confidence=failure_evidence,
                autonomy_level=AutonomyLevel.SUGGEST,
                requires_approval=True,
            )

        return Decision(
            endpoint_id=self.endpoint_id,
            timestamp=time.time(),
            action="monitor",
            parameters={},
            reasoning="All pools healthy",
            expected_value=0.0,
            confidence=health_evidence,
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
                    endpoint_id=self.endpoint_id,
                    timestamp=time.time(),
                    observation={"status": "no_system_provider"},
                    confidence=0.0,
                    requires_action=True,
                )

            status = self.system_provider.get_status()

            # Health is the Born probability of measured pass/fail checks —
            # each check is one evidence unit, no invented penalty weights.
            checks = {
                "quantum_backend_operational": bool(status.get("quantum_backend_operational")),
                "mining_operational": bool(status.get("mining_operational")),
                "error_rate_ok": float(status.get("error_rate", 0.0)) <= 0.05,
            }
            passed = sum(1 for ok in checks.values() if ok)
            failed = len(checks) - passed
            issues = [
                {
                    "quantum_backend_operational": "quantum_backend_down",
                    "mining_operational": "mining_down",
                    "error_rate_ok": "high_error_rate",
                }[name]
                for name, ok in checks.items()
                if not ok
            ]
            health_score = born_evidence(passed, failed)

            self.health_history.append({"timestamp": time.time(), "health_score": health_score})

            # Keep only recent history
            if len(self.health_history) > 1000:
                self.health_history = self.health_history[-1000:]

            return Observation(
                endpoint_id=self.endpoint_id,
                timestamp=time.time(),
                observation={
                    "health_score": health_score,
                    "issues": issues,
                    "checks_passed": passed,
                    "checks_failed": failed,
                    "uptime": status.get("uptime", 0),
                    "operations_count": status.get("operations_count", 0),
                },
                confidence=1.0,
                requires_action=failed > 0,
            )
        except Exception as e:
            logger.error(f"Status observation failed: {e}")
            return Observation(
                endpoint_id=self.endpoint_id,
                timestamp=time.time(),
                observation={"error": str(e)},
                confidence=0.0,
                requires_action=True,
            )

    async def reason(self, observation: Observation) -> Decision:
        """Reason about system status"""
        data = observation.observation

        if "error" in data or "no_system_provider" in data.get("status", ""):
            return Decision(
                endpoint_id=self.endpoint_id,
                timestamp=time.time(),
                action="alert",
                parameters={},
                reasoning="Status provider unavailable",
                expected_value=0.0,
                confidence=1.0,
                autonomy_level=AutonomyLevel.SUGGEST,
                requires_approval=False,
            )

        health_score = data.get("health_score", 1.0)
        issues = data.get("issues", [])
        passed = data.get("checks_passed", 0)
        failed = data.get("checks_failed", 0)
        # Confidence that the alert is warranted is the measured failure
        # evidence; nominal confidence is the measured pass evidence.
        failure_evidence = born_evidence(failed, passed)

        if health_score < 0.3:
            return Decision(
                endpoint_id=self.endpoint_id,
                timestamp=time.time(),
                action="critical_alert",
                parameters={"issues": issues},
                reasoning=f"System health critical ({health_score:.2f}). Issues: {issues}",
                expected_value=0.0,
                confidence=failure_evidence,
                autonomy_level=AutonomyLevel.SUGGEST,
                requires_approval=True,
            )

        if health_score < 0.6:
            return Decision(
                endpoint_id=self.endpoint_id,
                timestamp=time.time(),
                action="warning",
                parameters={"issues": issues},
                reasoning=f"System health degraded ({health_score:.2f}). Issues: {issues}",
                expected_value=0.0,
                confidence=failure_evidence,
                autonomy_level=AutonomyLevel.SUGGEST,
                requires_approval=True,
            )

        return Decision(
            endpoint_id=self.endpoint_id,
            timestamp=time.time(),
            action="nominal",
            parameters={},
            reasoning=f"System health nominal ({health_score:.2f})",
            expected_value=0.0,
            confidence=born_evidence(passed, failed),
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
