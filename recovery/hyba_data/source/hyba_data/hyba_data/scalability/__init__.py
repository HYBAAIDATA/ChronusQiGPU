"""
HYBA_DATA Scalability Module

Provides load testing, horizontal scaling configuration, connection pooling,
resource monitoring, and auto-scaling metrics for the HYBA_DATA framework.

Scalability layers:
  1. Load testing — concurrent request simulation with metrics
  2. Horizontal scaling — auto-scaling rules with phi-weighted thresholds
  3. Connection pooling — mock pool with health checks
  4. Resource monitoring — CPU, memory, throughput tracking
  5. Scaling metrics — throughput, latency, utilization baselines
"""
from .scaling import (
    LoadTester,
    LoadTestResult,
    ConnectionPool,
    ResourceMonitor,
    AutoScaler,
    ScalingConfig,
    ScalingMetrics,
)

__all__ = [
    "LoadTester",
    "LoadTestResult",
    "ConnectionPool",
    "ResourceMonitor",
    "AutoScaler",
    "ScalingConfig",
    "ScalingMetrics",
]
