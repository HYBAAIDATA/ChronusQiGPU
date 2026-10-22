"""
Drift Protector - Fixed async Redis implementation with circuit breaker
"""

import os
from dataclasses import dataclass
from typing import Dict, List, Optional

try:
    from redis import asyncio as aioredis
except ImportError:
    import aioredis

from .circuit import CircuitBreaker


@dataclass
class JobRecord:
    """Job record for drift assessment"""

    timestamp: float
    h_eff_x: float
    theta: float
    difficulty: float
    nonce: Optional[int] = None


class DriftProtector:
    """
    Drift protector with async Redis initialization and circuit breaker
    Monitors H_eff drift from baseline and triggers remediation
    """

    REDEPLOY_THRESHOLD = 0.5  # 50% of baseline triggers redeploy
    WARNING_THRESHOLD = 0.7  # 70% of baseline triggers warning

    def __init__(self, baseline_eh_s: float = 10_000.0, redis_url: str = None):
        self.baseline_eh_s = float(os.getenv("BASELINE_EH_S", baseline_eh_s))
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_client = None  # Will be async initialized
        self.drift_count = 0
        self.circuit_breaker = None  # Will be initialized with redis_client

    async def initialize(self):
        """Async Redis initialization"""
        self.redis_client = await aioredis.from_url(self.redis_url)
        self.circuit_breaker = CircuitBreaker(self.redis_client)
        self.drift_count = await self._load_drift_count()

    async def _load_drift_count(self) -> int:
        """Load drift count from Redis"""
        if not self.redis_client:
            return 0
        count = await self.redis_client.get("pulvini:drift_count")
        return int(count) if count else 0

    async def _save_drift_count(self):
        """Save drift count to Redis"""
        if self.redis_client:
            await self.redis_client.set("pulvini:drift_count", self.drift_count)

    async def _increment_drift_count(self):
        """Increment and save drift count"""
        self.drift_count += 1
        await self._save_drift_count()

    async def _recommend_action(self, ratio: float, status: str) -> str:
        """
        Recommend action based on drift ratio and circuit breaker state

        Args:
            ratio: H_eff ratio to baseline
            status: Current drift status

        Returns:
            Recommended action string
        """
        if status == "CRITICAL_DRIFT":
            await self._increment_drift_count()

            # Check circuit breaker
            if self.circuit_breaker:
                circuit_open = await self.circuit_breaker.record_failure()
                if circuit_open:
                    return "CIRCUIT_OPEN_SAFE_MODE"  # 🔒 Human intervention required

            # Auto-redeploy after 3 drifts
            if self.drift_count >= 3:
                return "AUTO_REDEPLOY"

            return "WARNING"

        elif status == "DRIFT":
            return "WARNING"

        return "NO_ACTION"

    async def assess(self, jobs: List[JobRecord]) -> Dict:
        """
        Assess drift from baseline based on recent jobs

        Args:
            jobs: List of job records to assess

        Returns:
            Assessment dictionary with drift status and recommended actions
        """
        if not jobs:
            return {
                "h_eff_x": 0.0,
                "ratio": 0.0,
                "status": "NO_DATA",
                "action": "NO_ACTION",
                "theta": 47208.0,
                "circuit_open": False,
            }

        # Calculate H_eff from recent jobs
        recent_jobs = jobs[-100:] if len(jobs) > 100 else jobs
        h_eff_values = [j.h_eff_x for j in recent_jobs if j.h_eff_x > 0]

        if not h_eff_values:
            return {
                "h_eff_x": 0.0,
                "ratio": 0.0,
                "status": "NO_DATA",
                "action": "NO_ACTION",
                "theta": 47208.0,
                "circuit_open": False,
            }

        h_eff_x = sum(h_eff_values) / len(h_eff_values)
        ratio = h_eff_x / self.baseline_eh_s if self.baseline_eh_s > 0 else 0.0

        # Determine drift status
        if ratio < self.REDEPLOY_THRESHOLD:
            status = "CRITICAL_DRIFT"
        elif ratio < self.WARNING_THRESHOLD:
            status = "DRIFT"
        else:
            status = "STABLE"

        # Get recommended action with circuit breaker
        action = await self._recommend_action(ratio, status)

        # Check circuit state
        circuit_open = False
        if self.circuit_breaker:
            circuit_open = await self.circuit_breaker.is_open()

        return {
            "h_eff_x": h_eff_x,
            "ratio": ratio,
            "status": status,
            "action": action,
            "theta": jobs[-1].theta if jobs else 47208.0,
            "drift_count": self.drift_count,
            "baseline": self.baseline_eh_s,
            "circuit_open": circuit_open,
        }

    async def get_drift_count(self) -> int:
        """Get current drift count"""
        return self.drift_count

    async def reset_drift_count(self):
        """Reset drift count (after remediation)"""
        self.drift_count = 0
        await self._save_drift_count()

    async def reset_circuit_breaker(self):
        """Reset circuit breaker (after manual intervention)"""
        if self.circuit_breaker:
            await self.circuit_breaker.reset()

    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
