"""
HYBA_DATA Scalability Implementation

Institutional-grade scalability primitives for the quantum-geometric
optimization framework. Designed for horizontal scaling from laptop
development to sovereign infrastructure deployments.

Author: Andre Taylor-Morris — HYBA Software Ltd
"""
import time
import math
import threading
import queue
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

PHI = (1.0 + math.sqrt(5.0)) / 2.0


@dataclass
class ScalingConfig:
    """Configuration for the scalability subsystem."""
    min_replicas: int = 1
    max_replicas: int = 100
    target_cpu_utilization: float = 0.7
    target_latency_ms: float = 100.0
    scale_up_threshold: float = 0.8
    scale_down_threshold: float = 0.3
    phi_weighted_scaling: bool = True
    connection_pool_size: int = 20
    connection_timeout_seconds: float = 30.0
    health_check_interval: float = 5.0
    load_test_concurrent: int = 100
    load_test_duration_seconds: float = 10.0


@dataclass
class LoadTestResult:
    """Result of a load test run."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    min_latency_ms: float = 0.0
    throughput_rps: float = 0.0
    duration_seconds: float = 0.0
    errors: list = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests

    @property
    def error_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.failed_requests / self.total_requests


@dataclass
class ScalingMetrics:
    """Real-time scaling metrics for auto-scaling decisions."""
    cpu_utilization: float = 0.0
    memory_utilization: float = 0.0
    request_rate_rps: float = 0.0
    average_latency_ms: float = 0.0
    active_connections: int = 0
    queue_depth: int = 0
    replicas: int = 1
    timestamp: float = field(default_factory=time.time)

    @property
    def should_scale_up(self) -> bool:
        return (self.cpu_utilization > 0.8 or
                self.average_latency_ms > 100 or
                self.queue_depth > 100)

    @property
    def should_scale_down(self) -> bool:
        return (self.cpu_utilization < 0.3 and
                self.average_latency_ms < 50 and
                self.queue_depth < 10)


class LoadTester:
    """
    Concurrent load testing framework for HYBA_DATA.
    Simulates realistic request patterns and measures throughput,
    latency percentiles, and error rates.
    """

    def __init__(self, config: ScalingConfig = None):
        self.config = config or ScalingConfig()

    def run_load_test(self, request_fn: Callable, duration: float = None,
                      concurrent: int = None) -> LoadTestResult:
        """
        Run a load test against a request function.
        request_fn: callable that takes no args and returns a result or raises.
        """
        duration = duration or self.config.load_test_duration_seconds
        concurrent = concurrent or self.config.load_test_concurrent
        result = LoadTestResult()
        latencies = []
        errors = []
        start_time = time.time()
        end_time = start_time + duration

        def worker():
            local_latencies = []
            local_errors = []
            while time.time() < end_time:
                req_start = time.perf_counter()
                try:
                    request_fn()
                    local_latencies.append((time.perf_counter() - req_start) * 1000)
                except Exception as e:
                    local_errors.append(str(e))
            return local_latencies, local_errors

        with ThreadPoolExecutor(max_workers=concurrent) as executor:
            futures = [executor.submit(worker) for _ in range(concurrent)]
            for future in as_completed(futures):
                lats, errs = future.result()
                latencies.extend(lats)
                errors.extend(errs)

        result.duration_seconds = time.time() - start_time
        result.total_requests = len(latencies) + len(errors)
        result.successful_requests = len(latencies)
        result.failed_requests = len(errors)
        result.errors = errors[:100]  # cap error list

        if latencies:
            latencies.sort()
            n = len(latencies)
            result.average_latency_ms = sum(latencies) / n
            result.p50_latency_ms = latencies[n // 2]
            result.p95_latency_ms = latencies[int(n * 0.95)] if n > 1 else latencies[0]
            result.p99_latency_ms = latencies[int(n * 0.99)] if n > 1 else latencies[0]
            result.max_latency_ms = latencies[-1]
            result.min_latency_ms = latencies[0]

        if result.duration_seconds > 0:
            result.throughput_rps = result.total_requests / result.duration_seconds

        return result


class ConnectionPool:
    """
    Mock connection pool with health checking and phi-weighted sizing.
    Manages a pool of connections to backend resources.
    """

    def __init__(self, config: ScalingConfig = None, factory: Callable = None):
        self.config = config or ScalingConfig()
        self._factory = factory or (lambda: {"id": id({}), "healthy": True, "created": time.time()})
        self._pool = queue.Queue(maxsize=self.config.connection_pool_size)
        self._active = 0
        self._total_created = 0
        self._lock = threading.Lock()
        for _ in range(self.config.connection_pool_size):
            conn = self._factory()
            self._total_created += 1
            self._pool.put(conn)

    def acquire(self, timeout: float = None) -> Any:
        """Acquire a connection from the pool."""
        timeout = timeout or self.config.connection_timeout_seconds
        try:
            conn = self._pool.get(timeout=timeout)
            with self._lock:
                self._active += 1
            return conn
        except queue.Empty:
            raise TimeoutError("Connection pool exhausted")

    def release(self, conn: Any) -> None:
        """Release a connection back to the pool."""
        with self._lock:
            self._active -= 1
        self._pool.put(conn)

    def health_check(self) -> dict:
        """Check pool health."""
        return {
            "pool_size": self._pool.qsize(),
            "active_connections": self._active,
            "total_created": self._total_created,
            "utilization": self._active / max(1, self.config.connection_pool_size),
        }

    def get_phi_scaled_size(self, base: int) -> int:
        """Calculate phi-weighted pool size."""
        if self.config.phi_weighted_scaling:
            return int(base * PHI)
        return base


class ResourceMonitor:
    """
    Monitors system resources (CPU, memory, throughput) for scaling decisions.
    Uses phi-weighted sampling for efficient monitoring.
    """

    def __init__(self):
        self._samples = deque(maxlen=1000)
        self._start_time = time.time()
        self._request_count = 0
        self._lock = threading.Lock()

    def record_request(self, latency_ms: float) -> None:
        """Record a request with its latency."""
        with self._lock:
            self._request_count += 1
            self._samples.append({
                "timestamp": time.time(),
                "latency_ms": latency_ms,
            })

    def get_metrics(self) -> ScalingMetrics:
        """Get current scaling metrics."""
        now = time.time()
        elapsed = now - self._start_time
        recent = [s for s in self._samples if s["timestamp"] > now - 60]

        avg_latency = sum(s["latency_ms"] for s in recent) / len(recent) if recent else 0
        rps = len(recent) / 60 if recent else 0

        # Simulated CPU/memory (would use psutil in production)
        cpu = min(1.0, rps / 1000)
        mem = min(1.0, len(self._samples) / 1000)

        return ScalingMetrics(
            cpu_utilization=cpu,
            memory_utilization=mem,
            request_rate_rps=rps,
            average_latency_ms=avg_latency,
            active_connections=0,
            queue_depth=max(0, len(recent) - 100),
            replicas=1,
        )

    def get_percentiles(self) -> dict:
        """Get latency percentiles from samples."""
        if not self._samples:
            return {"p50": 0, "p95": 0, "p99": 0}
        latencies = sorted(s["latency_ms"] for s in self._samples)
        n = len(latencies)
        return {
            "p50": latencies[n // 2],
            "p95": latencies[int(n * 0.95)] if n > 1 else latencies[0],
            "p99": latencies[int(n * 0.99)] if n > 1 else latencies[0],
        }


class AutoScaler:
    """
    Phi-weighted auto-scaling controller.
    Makes scaling decisions based on resource metrics with golden-ratio
    weighted thresholds for optimal resource utilization.
    """

    def __init__(self, config: ScalingConfig = None):
        self.config = config or ScalingConfig()
        self._current_replicas = self.config.min_replicas
        self._scale_events = []
        self._phi = PHI

    def evaluate(self, metrics: ScalingMetrics) -> dict:
        """Evaluate metrics and return scaling decision."""
        decision = {
            "action": "hold",
            "current_replicas": self._current_replicas,
            "target_replicas": self._current_replicas,
            "reason": "Metrics within bounds",
            "metrics": metrics,
        }

        if metrics.should_scale_up:
            target = max(self._current_replicas + 1,
                        int(self._current_replicas * self._phi))
            target = min(target, self.config.max_replicas)
            if target > self._current_replicas:
                decision["action"] = "scale_up"
                decision["target_replicas"] = target
                decision["reason"] = f"CPU={metrics.cpu_utilization:.1%} or latency={metrics.average_latency_ms:.0f}ms"
                self._current_replicas = target
                self._scale_events.append({"action": "scale_up", "time": time.time(),
                                          "from": decision["current_replicas"], "to": target})

        elif metrics.should_scale_down:
            target = max(self.config.min_replicas,
                        int(self._current_replicas / self._phi))
            if target < self._current_replicas:
                decision["action"] = "scale_down"
                decision["target_replicas"] = target
                decision["reason"] = f"CPU={metrics.cpu_utilization:.1%} and latency={metrics.average_latency_ms:.0f}ms"
                self._current_replicas = target
                self._scale_events.append({"action": "scale_down", "time": time.time(),
                                          "from": decision["current_replicas"], "to": target})

        return decision

    def get_scaling_history(self) -> list:
        """Get scaling event history."""
        return self._scale_events

    @property
    def current_replicas(self) -> int:
        return self._current_replicas
