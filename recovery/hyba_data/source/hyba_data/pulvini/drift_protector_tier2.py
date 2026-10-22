"""
Tier-2 Drift Protector - Fully integrated distributed drift detection
"""

import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from .coordinator import GlobalCoordinator
from .forecast import DriftForecaster
from .quorum import DriftQuorum
from .slo import SLOEngine


@dataclass
class JobRecord:
    """Job record for drift assessment"""

    timestamp: float
    h_eff_x: float
    theta: float
    nonce: Optional[int] = None


class BaseDriftProtector:
    """Base drift protector with local assessment logic"""

    def __init__(self, redis_client, theta_threshold: float = 47208.0):
        self.redis = redis_client
        self.theta_threshold = theta_threshold

    async def assess(self, jobs: List[JobRecord]) -> Dict:
        """Local drift assessment"""
        if not jobs:
            return {"h_eff_x": 0.0, "theta": self.theta_threshold, "status": "NO_DATA"}

        # Calculate H_eff from recent jobs
        recent_jobs = jobs[-10:] if len(jobs) > 10 else jobs
        h_eff_values = [j.h_eff_x for j in recent_jobs if j.h_eff_x > 0]

        if not h_eff_values:
            return {"h_eff_x": 0.0, "theta": self.theta_threshold, "status": "NO_DATA"}

        h_eff_x = sum(h_eff_values) / len(h_eff_values)

        # Determine drift status
        if h_eff_x < 50:
            status = "CRITICAL"
        elif h_eff_x < 100:
            status = "DRIFT"
        else:
            status = "STABLE"

        return {
            "h_eff_x": h_eff_x,
            "theta": self.theta_threshold,
            "status": status,
            "job_count": len(jobs),
        }


class Tier2DriftProtector(BaseDriftProtector):
    """
    Fully integrated Tier-2 drift protector with:
    - Distributed quorum consensus
    - SLO error budget enforcement
    - Predictive drift forecasting
    - Global cluster coordination
    """

    def __init__(
        self,
        redis_client,
        node_id: str,
        theta_threshold: float = 47208.0,
        quorum_size: int = 5,
        slo_target: float = 0.995,
    ):
        super().__init__(redis_client, theta_threshold)
        self.node_id = node_id
        self.quorum = DriftQuorum(redis_client, node_id, quorum_size)
        self.slo_engine = SLOEngine(redis_client, slo_target)
        self.forecaster = DriftForecaster()
        self.coordinator = GlobalCoordinator(redis_client, node_id)

    async def assess(self, jobs: List[JobRecord]) -> Dict:
        """
        Full Tier-2 assessment pipeline

        Args:
            jobs: List of job records to assess

        Returns:
            Complete assessment with all Tier-2 components
        """
        # 1. Local assessment
        assessment = await super().assess(jobs)
        assessment["node_id"] = self.node_id
        assessment["timestamp"] = time.time()

        # 2. Update forecaster
        self.forecaster.update(assessment["h_eff_x"])
        assessment["forecast"] = self.forecaster.forecast([1, 24])

        # 3. Quorum vote
        await self.quorum.submit_vote(assessment)
        quorum_decision = await self.quorum.get_quorum_decision()
        assessment["quorum"] = quorum_decision

        # 4. SLO budget
        await self.slo_engine.record_observation(assessment["h_eff_x"])
        slo_budget = await self.slo_engine.get_error_budget()
        assessment["slo"] = slo_budget

        # 5. Leader election + coordination
        is_leader = await self.coordinator.elect_leader()
        assessment["leader"] = is_leader

        # 6. Global policy enforcement
        global_action = await self._enforce_global_policy(assessment)
        assessment["global_action"] = global_action

        # 7. Add cluster state if leader
        if is_leader:
            cluster_state = await self.coordinator.get_cluster_state()
            assessment["cluster_state"] = cluster_state

        return assessment

    async def _enforce_global_policy(self, assessment: Dict) -> str:
        """Enforce global policy based on assessment"""
        slo_status = assessment["slo"].get("slo_status", "HEALTHY")
        quorum_decision = assessment["quorum"].get("decision", "GLOBAL_STABLE")
        forecast = assessment.get("forecast", {})

        # Priority 1: SLO breach
        if slo_status == "CRITICAL":
            return "SLO_BREACH_THROTTLE"

        # Priority 2: Quorum critical decision
        if quorum_decision == "GLOBAL_REDEPLOY":
            return "GLOBAL_REDEPLOY"
        elif quorum_decision == "GLOBAL_TUNE_THETA":
            return "GLOBAL_TUNE_THETA"

        # Priority 3: Predictive drift
        p_drift_1h = forecast.get("p_drift_1h", 0.0)
        if p_drift_1h > 0.5:
            return "PREDICTIVE_DRIFT_ALERT"

        # Priority 4: Quorum adjust
        if quorum_decision == "GLOBAL_ADJUST":
            return "GLOBAL_ADJUST"

        return "NO_ACTION"

    async def get_status(self) -> Dict:
        """Get current Tier-2 status"""
        is_leader = await self.coordinator.is_leader()
        slo_budget = await self.slo_engine.get_error_budget()
        quorum_decision = await self.quorum.get_quorum_decision()
        forecast = self.forecaster.forecast([1, 24])

        return {
            "node_id": self.node_id,
            "leader": is_leader,
            "slo": slo_budget,
            "quorum": quorum_decision,
            "forecast": forecast,
            "timestamp": time.time(),
        }

    async def maintain_leadership(self):
        """Maintain leadership heartbeat"""
        while await self.coordinator.heartbeat():
            await asyncio.sleep(10)

    async def step_down(self):
        """Step down from leadership"""
        await self.coordinator.step_down()

    async def get_cluster_state(self) -> Dict:
        """Get cluster state (leader only)"""
        if await self.coordinator.is_leader():
            return await self.coordinator.get_cluster_state()
        return {"error": "NOT_LEADER"}


# Import asyncio for maintain_leadership
import asyncio
