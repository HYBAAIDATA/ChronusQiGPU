"""
Universal endpoint intelligence wrapper.

Provides a decorator and wrapper class to add intelligence to any endpoint
without modifying the original endpoint code.
"""

import asyncio
import functools
import logging
import time
from typing import Any, Callable, Optional

from hyba_backend.core.intelligence.intelligent_endpoint import (
    AutonomyLevel,
    Decision,
    IntelligentEndpoint,
    Observation,
)

logger = logging.getLogger(__name__)


class EndpointIntelligenceWrapper(IntelligentEndpoint):
    """
    Universal wrapper that adds intelligence to any endpoint.

    Monitors endpoint performance and provides:
    - Request/response tracking
    - Error rate monitoring
    - Performance degradation detection
    - Automatic fallback recommendations
    - Health assessment
    """

    def __init__(self, endpoint_name: str, endpoint_path: str, **kwargs):
        super().__init__(
            endpoint_id=f"endpoint-{endpoint_name}",
            autonomy_level=AutonomyLevel.OBSERVE,
            **kwargs,
        )
        self.endpoint_name = endpoint_name
        self.endpoint_path = endpoint_path
        self.request_count = 0
        self.success_count = 0
        self.error_count = 0
        self.total_response_time = 0.0
        self.request_history = []
        self.error_history = []

    async def observe(self) -> Observation:
        """Monitor endpoint performance"""
        try:
            # Calculate metrics
            success_rate = 0.0
            if self.request_count > 0:
                success_rate = self.success_count / self.request_count

            avg_response_time = 0.0
            if self.request_count > 0:
                avg_response_time = self.total_response_time / self.request_count

            # Get recent error rate
            recent_errors = len(
                [e for e in self.error_history if time.time() - e["timestamp"] < 60]
            )
            recent_requests = len(
                [r for r in self.request_history if time.time() - r["timestamp"] < 60]
            )
            recent_error_rate = 0.0
            if recent_requests > 0:
                recent_error_rate = recent_errors / recent_requests

            return Observation(
                timestamp=time.time(),
                endpoint_id=self.endpoint_id,
                observation={
                    "endpoint_name": self.endpoint_name,
                    "endpoint_path": self.endpoint_path,
                    "total_requests": self.request_count,
                    "success_count": self.success_count,
                    "error_count": self.error_count,
                    "success_rate": success_rate,
                    "avg_response_time": avg_response_time,
                    "recent_error_rate": recent_error_rate,
                },
                confidence=0.95,
            )
        except Exception as e:
            logger.error(f"Endpoint observation failed: {e}")
            return Observation(
                timestamp=time.time(),
                endpoint_id=self.endpoint_id,
                observation={"error": str(e)},
                confidence=0.0,
            )

    async def reason(self, observation: Observation) -> Decision:
        """Reason about endpoint health"""
        data = observation.observation

        if "error" in data:
            return Decision(
                timestamp=time.time(),
                endpoint_id=self.endpoint_id,
                action="alert",
                parameters={},
                reasoning="Endpoint monitoring failed",
                expected_value=0.0,
                confidence=0.5,
                autonomy_level=AutonomyLevel.SUGGEST,
            )

        success_rate = data.get("success_rate", 1.0)
        recent_error_rate = data.get("recent_error_rate", 0.0)
        avg_response_time = data.get("avg_response_time", 0.0)

        # Alert if success rate too low
        if success_rate < 0.5 and data.get("total_requests", 0) > 10:
            return Decision(
                timestamp=time.time(),
                endpoint_id=self.endpoint_id,
                action="degrade_service",
                parameters={
                    "success_rate": success_rate,
                    "recent_error_rate": recent_error_rate,
                },
                reasoning=f"Endpoint success rate critical ({success_rate:.2%}). Consider degrading service.",
                expected_value=0.8,
                confidence=0.9,
                autonomy_level=AutonomyLevel.SUGGEST,
            )

        # Warn if recent error rate high
        if recent_error_rate > 0.2:
            return Decision(
                timestamp=time.time(),
                endpoint_id=self.endpoint_id,
                action="investigate",
                parameters={
                    "recent_error_rate": recent_error_rate,
                },
                reasoning=f"Recent error rate elevated ({recent_error_rate:.2%}). Investigate endpoint.",
                expected_value=0.6,
                confidence=0.8,
                autonomy_level=AutonomyLevel.SUGGEST,
            )

        # Warn if response time degrading
        if avg_response_time > 5.0:
            return Decision(
                timestamp=time.time(),
                endpoint_id=self.endpoint_id,
                action="optimize_performance",
                parameters={
                    "avg_response_time": avg_response_time,
                },
                reasoning=f"Endpoint response time high ({avg_response_time:.2f}s). Optimize performance.",
                expected_value=0.5,
                confidence=0.7,
                autonomy_level=AutonomyLevel.SUGGEST,
            )

        return Decision(
            timestamp=time.time(),
            endpoint_id=self.endpoint_id,
            action="monitor",
            parameters={
                "success_rate": success_rate,
                "recent_error_rate": recent_error_rate,
                "avg_response_time": avg_response_time,
            },
            reasoning="Endpoint health nominal",
            expected_value=0.1,
            confidence=0.95,
            autonomy_level=AutonomyLevel.OBSERVE,
        )

    async def act(self, decision: Decision) -> dict[str, Any]:
        """Execute endpoint decisions"""
        action = decision.action

        if action == "degrade_service":
            return {
                "status": "degraded",
                "message": "Service degraded due to high error rate",
            }
        elif action == "investigate":
            return {
                "status": "investigating",
                "message": "Investigating endpoint issues",
            }
        elif action == "optimize_performance":
            return {
                "status": "optimizing",
                "message": "Optimizing endpoint performance",
            }
        elif action == "monitor":
            return {"status": "healthy", "message": "Endpoint operating normally"}
        elif action == "alert":
            return {"status": "alert", "message": "Endpoint monitoring alert"}

        return {"status": "unknown_action"}

    async def learn(self, outcome: dict[str, Any]) -> None:
        """Learn from endpoint outcomes"""
        # Track patterns in endpoint behavior
        if outcome.get("action") == "investigate":
            self.performance["investigation_count"] = (
                self.performance.get("investigation_count", 0) + 1
            )

    def record_request(self, response_time: float, success: bool, error: Optional[str] = None):
        """Record endpoint request"""
        self.request_count += 1
        self.total_response_time += response_time

        request_record = {
            "timestamp": time.time(),
            "response_time": response_time,
            "success": success,
        }
        self.request_history.append(request_record)

        # Keep only recent history
        if len(self.request_history) > 1000:
            self.request_history = self.request_history[-1000:]

        if success:
            self.success_count += 1
        else:
            self.error_count += 1
            error_record = {"timestamp": time.time(), "error": error}
            self.error_history.append(error_record)

            # Keep only recent error history
            if len(self.error_history) > 100:
                self.error_history = self.error_history[-100:]


def intelligent_endpoint(endpoint_name: str, endpoint_path: str):
    """
    Decorator to add intelligence to any endpoint.

    Usage:
        @app.get("/api/endpoint")
        @intelligent_endpoint("my_endpoint", "/api/endpoint")
        async def my_endpoint():
            return {"status": "ok"}
    """

    def decorator(func: Callable) -> Callable:
        # Create wrapper for this endpoint
        wrapper = EndpointIntelligenceWrapper(
            endpoint_name=endpoint_name, endpoint_path=endpoint_path
        )

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                response_time = time.time() - start_time
                wrapper.record_request(response_time, True)
                return result
            except Exception as e:
                response_time = time.time() - start_time
                wrapper.record_request(response_time, False, str(e))
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                response_time = time.time() - start_time
                wrapper.record_request(response_time, True)
                return result
            except Exception as e:
                response_time = time.time() - start_time
                wrapper.record_request(response_time, False, str(e))
                raise

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
