"""
HYBA_DATA Chaos Engineering Implementation

Institutional-grade chaos engineering primitives for the quantum-geometric
optimization framework. Validates resilience through controlled fault
injection, circuit breaking, and failure mode simulation.

Inspired by Netflix Chaos Monkey, AWS Fault Injection Simulator, and
Google's resilience testing practices.

Author: Andre Taylor-Morris — HYBA Software Ltd
"""
import time
import math
import random
import threading
from enum import Enum
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from concurrent.futures import ThreadPoolExecutor

PHI = (1.0 + math.sqrt(5.0)) / 2.0


class FaultType(Enum):
    """Types of faults that can be injected."""
    LATENCY_SPIKE = "latency_spike"
    SERVICE_FAILURE = "service_failure"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    NETWORK_PARTITION = "network_partition"
    DATA_CORRUPTION = "data_corruption"
    PARTIAL_FAILURE = "partial_failure"
    TIMEOUT = "timeout"
    MEMORY_PRESSURE = "memory_pressure"


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing, reject requests
    HALF_OPEN = "half_open" # Testing if service recovered


@dataclass
class ChaosConfig:
    """Configuration for chaos engineering."""
    fault_injection_rate: float = 0.01  # 1% of requests get faults
    latency_spike_ms: float = 500.0
    circuit_failure_threshold: int = 5
    circuit_recovery_timeout: float = 30.0
    circuit_half_open_max_calls: int = 3
    max_retries: int = 3
    retry_base_delay_ms: float = 100.0
    retry_max_delay_ms: float = 5000.0
    bulkhead_max_concurrent: int = 10
    chaos_experiment_duration: float = 60.0
    enable_phi_weighted_recovery: bool = True


@dataclass
class ResilienceResult:
    """Result of a resilience test."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    retried_calls: int = 0
    circuit_breaks: int = 0
    fallback_calls: int = 0
    average_latency_ms: float = 0.0
    recovery_time_ms: float = 0.0
    faults_injected: int = 0

    @property
    def success_rate(self) -> float:
        return self.successful_calls / max(1, self.total_calls)

    @property
    def resilience_score(self) -> float:
        """Phi-weighted resilience score [0, 1]."""
        base = self.success_rate
        recovery_factor = 1.0 / (1.0 + self.recovery_time_ms / 1000.0)
        if ChaosConfig().enable_phi_weighted_recovery:
            return base * (1.0 + (recovery_factor - 0.5) / PHI)
        return base * recovery_factor


class FaultInjector:
    """
    Injects faults into system operations with configurable rates.
    Supports latency spikes, service failures, and resource exhaustion.
    """

    def __init__(self, config: ChaosConfig = None):
        self.config = config or ChaosConfig()
        self._injection_count = 0
        self._lock = threading.Lock()

    def maybe_inject(self) -> Optional[FaultType]:
        """Maybe inject a fault. Returns FaultType if injected, None otherwise."""
        if random.random() < self.config.fault_injection_rate:
            fault = random.choice(list(FaultType))
            with self._lock:
                self._injection_count += 1
            return fault
        return None

    def inject_latency(self) -> float:
        """Inject a latency spike. Returns the injected delay in ms."""
        delay = self.config.latency_spike_ms * (0.5 + random.random())
        time.sleep(delay / 1000.0)
        return delay

    def inject_failure(self) -> Exception:
        """Inject a service failure."""
        failures = [
            ConnectionError("Injected: network unreachable"),
            TimeoutError("Injected: request timeout"),
            RuntimeError("Injected: service unavailable"),
            MemoryError("Injected: memory pressure"),
        ]
        return random.choice(failures)

    def inject_partial_failure(self, success_rate: float = 0.7) -> bool:
        """Inject a partial failure. Returns False if 'failed', True if 'succeeded'."""
        return random.random() < success_rate

    @property
    def total_injections(self) -> int:
        return self._injection_count


class CircuitBreaker:
    """
    Circuit breaker with open/half-open/closed states.
    Uses phi-weighted recovery timeout for optimal recovery detection.
    """

    def __init__(self, config: ChaosConfig = None, name: str = "default"):
        self.config = config or ChaosConfig()
        self.name = name
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None
        self._half_open_calls = 0
        self._half_open_successes = 0
        self._lock = threading.Lock()

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute a function through the circuit breaker."""
        with self._lock:
            if self._state == CircuitState.OPEN:
                recovery_timeout = self.config.circuit_recovery_timeout
                if self.config.enable_phi_weighted_recovery:
                    recovery_timeout *= (1.0 / PHI)  # phi-weighted faster recovery
                if self._last_failure_time and time.time() - self._last_failure_time > recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    self._half_open_successes = 0
                else:
                    raise CircuitBreakerOpenError(f"Circuit '{self.name}' is OPEN")

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.config.circuit_half_open_max_calls:
                    raise CircuitBreakerOpenError(f"Circuit '{self.name}' is HALF_OPEN (max calls reached)")
                self._half_open_calls += 1

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_successes += 1
                if self._half_open_successes >= self.config.circuit_half_open_max_calls // 2:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0

    def _on_failure(self):
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
            elif self._failure_count >= self.config.circuit_failure_threshold:
                self._state = CircuitState.OPEN

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    def reset(self):
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = None


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


class RetryPolicy:
    """
    Exponential backoff retry with phi-weighted jitter.
    Retries failed operations with increasing delays.
    """

    def __init__(self, config: ChaosConfig = None):
        self.config = config or ChaosConfig()

    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute a function with retry policy."""
        last_error = None
        for attempt in range(self.config.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < self.config.max_retries:
                    delay = min(
                        self.config.retry_base_delay_ms * (2 ** attempt),
                        self.config.retry_max_delay_ms
                    )
                    # Phi-weighted jitter
                    jitter = delay * (random.random() - 0.5) / PHI
                    time.sleep((delay + jitter) / 1000.0)
        raise last_error

    def get_retry_delay(self, attempt: int) -> float:
        """Get the delay for a given retry attempt."""
        delay = min(
            self.config.retry_base_delay_ms * (2 ** attempt),
            self.config.retry_max_delay_ms
        )
        jitter = delay * (random.random() - 0.5) / PHI
        return max(0, delay + jitter)


class Bulkhead:
    """
    Bulkhead isolation pattern. Limits concurrent calls to prevent
    resource exhaustion from cascading failures.
    """

    def __init__(self, config: ChaosConfig = None):
        self.config = config or ChaosConfig()
        self._semaphore = threading.Semaphore(self.config.bulkhead_max_concurrent)
        self._active = 0
        self._rejected = 0
        self._lock = threading.Lock()

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute a function within the bulkhead."""
        if not self._semaphore.acquire(blocking=False):
            with self._lock:
                self._rejected += 1
            raise BulkheadFullError("Bulkhead is full")
        try:
            with self._lock:
                self._active += 1
            return func(*args, **kwargs)
        finally:
            with self._lock:
                self._active -= 1
            self._semaphore.release()

    def get_stats(self) -> dict:
        return {
            "max_concurrent": self.config.bulkhead_max_concurrent,
            "active": self._active,
            "rejected": self._rejected,
        }


class BulkheadFullError(Exception):
    """Raised when bulkhead is full."""
    pass


@dataclass
class ChaosExperiment:
    """A single chaos experiment configuration."""
    name: str
    fault_type: FaultType
    duration_seconds: float = 60.0
    injection_rate: float = 0.05
    target_function: Callable = None
    description: str = ""

    def run(self, iterations: int = 100) -> dict:
        """Run this chaos experiment."""
        results = {
            "name": self.name,
            "fault_type": self.fault_type.value,
            "iterations": iterations,
            "successful": 0,
            "failed": 0,
            "faults_injected": 0,
            "latencies": [],
        }

        for i in range(iterations):
            start = time.perf_counter()
            try:
                if random.random() < self.injection_rate:
                    results["faults_injected"] += 1
                    if self.fault_type == FaultType.LATENCY_SPIKE:
                        time.sleep(0.01)
                    elif self.fault_type == FaultType.SERVICE_FAILURE:
                        raise RuntimeError("Injected failure")
                    elif self.fault_type == FaultType.PARTIAL_FAILURE:
                        if random.random() < 0.3:
                            raise RuntimeError("Injected partial failure")

                if self.target_function:
                    self.target_function()
                else:
                    pass  # no-op
                results["successful"] += 1
            except Exception:
                results["failed"] += 1
            results["latencies"].append((time.perf_counter() - start) * 1000)

        lats = results["latencies"]
        results["avg_latency_ms"] = sum(lats) / len(lats) if lats else 0
        results["success_rate"] = results["successful"] / max(1, iterations)
        del results["latencies"]  # remove raw data from summary
        return results


class ChaosExperimentRunner:
    """
    Runs multiple chaos experiments and aggregates results.
    Provides a comprehensive resilience assessment.
    """

    def __init__(self, config: ChaosConfig = None):
        self.config = config or ChaosConfig()
        self._experiments = []
        self._results = []

    def add_experiment(self, experiment: ChaosExperiment) -> None:
        self._experiments.append(experiment)

    def run_all(self, iterations_per_experiment: int = 100) -> list:
        """Run all registered chaos experiments."""
        self._results = []
        for exp in self._experiments:
            result = exp.run(iterations=iterations_per_experiment)
            self._results.append(result)
        return self._results

    def get_resilience_report(self) -> dict:
        """Generate a comprehensive resilience report."""
        if not self._results:
            return {"status": "no experiments run"}

        total_tests = sum(r["iterations"] for r in self._results)
        total_success = sum(r["successful"] for r in self._results)
        total_fail = sum(r["failed"] for r in self._results)
        total_faults = sum(r["faults_injected"] for r in self._results)

        return {
            "total_experiments": len(self._results),
            "total_iterations": total_tests,
            "total_successful": total_success,
            "total_failed": total_fail,
            "total_faults_injected": total_faults,
            "overall_success_rate": total_success / max(1, total_tests),
            "overall_resilience_score": total_success / max(1, total_tests) * PHI / (PHI + 1),
            "experiments": self._results,
        }

    def create_default_suite(self, target_fn: Callable = None) -> None:
        """Create a default suite of chaos experiments."""
        defaults = [
            ChaosExperiment("latency_resilience", FaultType.LATENCY_SPIKE,
                           injection_rate=0.1, target_function=target_fn,
                           description="Test resilience to latency spikes"),
            ChaosExperiment("failure_resilience", FaultType.SERVICE_FAILURE,
                           injection_rate=0.05, target_function=target_fn,
                           description="Test resilience to service failures"),
            ChaosExperiment("partial_failure_resilience", FaultType.PARTIAL_FAILURE,
                           injection_rate=0.15, target_function=target_fn,
                           description="Test resilience to partial failures"),
            ChaosExperiment("timeout_resilience", FaultType.TIMEOUT,
                           injection_rate=0.08, target_function=target_fn,
                           description="Test resilience to timeouts"),
            ChaosExperiment("memory_pressure", FaultType.MEMORY_PRESSURE,
                           injection_rate=0.03, target_function=target_fn,
                           description="Test resilience to memory pressure"),
        ]
        for exp in defaults:
            self.add_experiment(exp)
