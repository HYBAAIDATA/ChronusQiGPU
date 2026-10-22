"""
HYBA_DATA Chaos Engineering Module

Provides fault injection, circuit breakers, resilience testing, and
chaos experiment runners for the HYBA_DATA framework.

Chaos engineering layers:
  1. Fault injection — random failures, latency injection, resource exhaustion
  2. Circuit breaker — failure detection with open/half-open/closed states
  3. Resilience patterns — retry, timeout, bulkhead, fallback
  4. Failure modes — network partition, memory pressure, CPU spike
  5. Chaos experiment runner — controlled failure injection with metrics
"""
from .chaos_engine import (
    FaultInjector,
    FaultType,
    CircuitBreaker,
    CircuitState,
    RetryPolicy,
    Bulkhead,
    ChaosExperiment,
    ChaosExperimentRunner,
    ChaosConfig,
    ResilienceResult,
)

__all__ = [
    "FaultInjector",
    "FaultType",
    "CircuitBreaker",
    "CircuitState",
    "RetryPolicy",
    "Bulkhead",
    "ChaosExperiment",
    "ChaosExperimentRunner",
    "ChaosConfig",
    "ResilienceResult",
]
