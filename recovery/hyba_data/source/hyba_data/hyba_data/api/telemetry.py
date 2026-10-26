"""
Telemetry collection for HYBA_DATA API.

Provides McKinsey-grade observability: counters, histograms, gauges,
and structured event logging. Compatible with Prometheus exposition format.
"""
from __future__ import annotations
import time
import threading
from collections import defaultdict
from enum import Enum
from typing import Any


class MetricType(Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


class TelemetryCollector:
    """
    Thread-safe telemetry collector for API observability.

    Tracks:
    - Request counters (per endpoint, per method)
    - Response time histograms (per endpoint)
    - Optimization run counters (per solver type)
    - Evaluation counters (per oracle type)
    - Active gauge metrics (concurrent requests, cache sizes)
    - Error counters (per endpoint, per status code)
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._start_time = time.time()
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._events: list[dict[str, Any]] = []
        self._max_events = 1000

    def increment(self, name: str, value: int = 1) -> None:
        with self._lock:
            self._counters[name] += value

    def set_gauge(self, name: str, value: float) -> None:
        with self._lock:
            self._gauges[name] = value

    def observe(self, histogram_name: str, value: float) -> None:
        with self._lock:
            self._histograms[histogram_name].append(value)
            if len(self._histograms[histogram_name]) > 10000:
                self._histograms[histogram_name] = self._histograms[histogram_name][-5000:]

    def record_event(self, event_type: str, **kwargs) -> None:
        with self._lock:
            event = {"type": event_type, "timestamp": time.time(), **kwargs}
            self._events.append(event)
            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events // 2:]

    def get_metrics(self) -> dict[str, Any]:
        with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "uptime_seconds": time.time() - self._start_time,
            }

    def get_histograms(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            result = {}
            for name, values in self._histograms.items():
                if values:
                    sorted_v = sorted(values)
                    n = len(sorted_v)
                    result[name] = {
                        "count": n,
                        "sum": sum(sorted_v),
                        "min": sorted_v[0],
                        "max": sorted_v[-1],
                        "mean": sum(sorted_v) / n,
                        "p50": sorted_v[n // 2],
                        "p95": sorted_v[int(n * 0.95)] if n > 1 else sorted_v[0],
                        "p99": sorted_v[int(n * 0.99)] if n > 1 else sorted_v[0],
                    }
            return result

    def get_events(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            return self._events[-limit:]

    def to_prometheus(self) -> str:
        """Export metrics in Prometheus text exposition format."""
        lines = []
        with self._lock:
            for name, value in self._counters.items():
                lines.append(f"# TYPE {name} counter")
                lines.append(f"{name} {value}")
            for name, value in self._gauges.items():
                lines.append(f"# TYPE {name} gauge")
                lines.append(f"{name} {value}")
            for name, values in self._histograms.items():
                if values:
                    sorted_v = sorted(values)
                    n = len(sorted_v)
                    lines.append(f"# TYPE {name} histogram")
                    lines.append(f'{name}_count {n}')
                    lines.append(f'{name}_sum {sum(sorted_v)}')
                    for q, label in [(0.5, "0.5"), (0.95, "0.95"), (0.99, "0.99")]:
                        idx = min(int(n * q), n - 1)
                        lines.append(f'{name}{{quantile="{label}"}} {sorted_v[idx]}')
        return "\n".join(lines) + "\n"

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._events.clear()
            self._start_time = time.time()


# Global telemetry instance
telemetry = TelemetryCollector()
