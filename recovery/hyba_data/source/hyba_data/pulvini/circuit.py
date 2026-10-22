"""
Circuit Breaker - Loop-proof failure tracking
"""

from typing import Dict


class CircuitBreaker:
    """
    Circuit breaker to prevent cascading failures
    Opens after max failures in window, closes after timeout
    """

    def __init__(self, redis_client, max_failures: int = 5, window: int = 3600):
        self.redis = redis_client
        self.max_failures = max_failures
        self.window = window  # Window in seconds
        self.failures_key = "pulvini:drift_failures"
        self.circuit_key = "pulvini:circuit_breaker"

    async def record_failure(self) -> bool:
        """
        Record a failure and check if circuit should open

        Returns:
            True if circuit opened, False otherwise
        """
        # Increment failure counter with window expiration
        pipe = self.redis.pipeline()
        pipe.incr(self.failures_key)
        pipe.expire(self.failures_key, self.window)
        await pipe.execute()

        # Check if threshold exceeded
        failures = await self.redis.get(self.failures_key)
        failures = int(failures) if failures else 0

        if failures >= self.max_failures:
            await self.redis.set(self.circuit_key, "OPEN", ex=self.window)
            return True

        return False

    async def is_open(self) -> bool:
        """
        Check if circuit is currently open

        Returns:
            True if circuit is open, False otherwise
        """
        state = await self.redis.get(self.circuit_key)
        return state is not None

    async def reset(self):
        """Reset circuit breaker (close circuit)"""
        await self.redis.delete(self.circuit_key)
        await self.redis.delete(self.failures_key)

    async def get_state(self) -> Dict:
        """
        Get current circuit breaker state

        Returns:
            Dictionary with circuit state and failure count
        """
        failures = await self.redis.get(self.failures_key)
        failures = int(failures) if failures else 0
        is_open = await self.is_open()

        return {
            "is_open": is_open,
            "failures": failures,
            "max_failures": self.max_failures,
            "window": self.window,
        }

    async def record_success(self):
        """Record a success (optional - can decay failure count)"""
        # Optionally decay failure count on success
        # For now, we just keep the counter until window expires
