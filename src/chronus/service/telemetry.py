"""Process-local tracing, Prometheus-style metrics, and structured JSON logging.

Provides basic in-process observability for Chronus API:
- OpenTelemetry SDK integration for spans across API ingestion, algebraic folding,
  OVID storage, and execution dispatch.
- Standard Prometheus metrics with p50, p95, p99 latency quantiles, CCU tracking,
  and hardware memory gauges.
- Structured JSON logging with tenant_id, workload_id, and trace_id context propagation.
"""

import contextvars
import json
import logging
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional, Tuple

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from chronus import __version__ as _CHRONUS_VERSION

# -----------------------------------------------------------------------------
# Context Variables for Distributed Tracing & Logging
# -----------------------------------------------------------------------------

current_tenant_id: contextvars.ContextVar[str] = contextvars.ContextVar("current_tenant_id", default="")
current_workload_id: contextvars.ContextVar[str] = contextvars.ContextVar("current_workload_id", default="")
current_trace_id: contextvars.ContextVar[str] = contextvars.ContextVar("current_trace_id", default="")

# -----------------------------------------------------------------------------
# Structured JSON Logging
# -----------------------------------------------------------------------------

class StructuredJSONFormatter(logging.Formatter):
    """Formats log records as structured JSON including tenant_id, workload_id, and trace_id."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "tenant_id": getattr(record, "tenant_id", current_tenant_id.get() or "system"),
            "workload_id": getattr(record, "workload_id", current_workload_id.get() or ""),
            "trace_id": getattr(record, "trace_id", current_trace_id.get() or ""),
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def setup_structured_logging(level: int = logging.INFO) -> None:
    """Configure root logger to output structured JSON."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredJSONFormatter())
    root_logger = logging.getLogger()
    # Replace existing handlers
    root_logger.handlers = [handler]
    root_logger.setLevel(level)


# -----------------------------------------------------------------------------
# OpenTelemetry Tracing Engine
# -----------------------------------------------------------------------------

_span_exporter = InMemorySpanExporter()
_tracer_provider = TracerProvider()
_tracer_provider.add_span_processor(SimpleSpanProcessor(_span_exporter))
trace.set_tracer_provider(_tracer_provider)
tracer = trace.get_tracer("chronus.execution.fabric", _CHRONUS_VERSION)


@contextmanager
def trace_span(name: str, attributes: Optional[Dict[str, Any]] = None) -> Generator[trace.Span, None, None]:
    """Emit an in-memory span and restore the prior trace context on exit."""
    trace_token = None
    with tracer.start_as_current_span(name) as span:
        ctx = span.get_span_context()
        if ctx.is_valid:
            trace_hex = format(ctx.trace_id, "032x")
            trace_token = current_trace_id.set(trace_hex)
            span.set_attribute("chronus.trace_id", trace_hex)

        tenant = current_tenant_id.get()
        if tenant:
            span.set_attribute("chronus.tenant_id", tenant)

        workload = current_workload_id.get()
        if workload:
            span.set_attribute("chronus.workload_id", workload)

        if attributes:
            for k, v in attributes.items():
                if isinstance(v, (str, bool, int, float)):
                    span.set_attribute(k, v)
                else:
                    span.set_attribute(k, str(v))

        try:
            yield span
        finally:
            if trace_token is not None:
                current_trace_id.reset(trace_token)


# -----------------------------------------------------------------------------
# Prometheus Metrics Registry
# -----------------------------------------------------------------------------

class PrometheusMetricsRegistry:
    """Process-local Prometheus metrics registry; not thread-safe or distributed."""

    def __init__(self) -> None:
        self.request_counts: Dict[str, int] = {}
        self.latencies: List[float] = []
        self.ccu_consumed: Dict[str, float] = {}
        # Only emit device metrics explicitly observed by an adapter.
        self.hardware_memory: Dict[str, int] = {}
        self.start_time = time.time()

    @staticmethod
    def _escape_label(value: str) -> str:
        return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', chr(92) + '"')

    def record_request(self, tenant_id: str, status: str, workload_type: str) -> None:
        tenant_id = self._escape_label(tenant_id)
        status = self._escape_label(status)
        workload_type = self._escape_label(workload_type)
        key = f'tenant_id="{tenant_id}",status="{status}",workload_type="{workload_type}"'
        self.request_counts[key] = self.request_counts.get(key, 0) + 1

    def record_execution_latency(self, duration_seconds: float) -> None:
        self.latencies.append(duration_seconds)
        if len(self.latencies) > 10000:
            self.latencies = self.latencies[-5000:]

    def record_ccu(self, tenant_id: str, ccu: float) -> None:
        tenant_id = self._escape_label(tenant_id)
        self.ccu_consumed[tenant_id] = self.ccu_consumed.get(tenant_id, 0.0) + ccu

    def set_hardware_memory(self, device: str, backend: str, bytes_allocated: int) -> None:
        if not isinstance(bytes_allocated, int) or isinstance(bytes_allocated, bool) or bytes_allocated < 0:
            raise ValueError("bytes_allocated must be a non-negative integer")
        device = self._escape_label(device)
        backend = self._escape_label(backend)
        key = f'device="{device}",backend="{backend}"'
        self.hardware_memory[key] = bytes_allocated

    def _calculate_quantiles(self) -> Tuple[float, float, float]:
        if not self.latencies:
            return 0.0, 0.0, 0.0
        s = sorted(self.latencies)
        n = len(s)
        p50 = s[int(n * 0.50)]
        p95 = s[min(int(n * 0.95), n - 1)]
        p99 = s[min(int(n * 0.99), n - 1)]
        return p50, p95, p99

    def render_metrics(self, total_workloads: int = 0, active_workloads: int = 0) -> str:
        """Render standard Prometheus format metrics text."""
        uptime = time.time() - self.start_time
        p50, p95, p99 = self._calculate_quantiles()

        lines = [
            "# HELP chronus_uptime_seconds Service uptime in seconds",
            "# TYPE chronus_uptime_seconds gauge",
            f"chronus_uptime_seconds {uptime:.3f}",
            "",
            "# HELP chronus_workloads_total Workloads retained by this process",
            "# TYPE chronus_workloads_total gauge",
            f"chronus_workloads_total {total_workloads}",
            "# HELP chronus_workloads_active Workloads in an active lifecycle state",
            "# TYPE chronus_workloads_active gauge",
            f"chronus_workloads_active {active_workloads}",
            "",
            "# HELP chronus_workload_requests_total Total number of workload requests received",
            "# TYPE chronus_workload_requests_total counter",
        ]

        if not self.request_counts:
            lines.append('chronus_workload_requests_total{tenant_id="default",status="PROCESSED",workload_type="ALL"} 0')
        else:
            for labels, count in sorted(self.request_counts.items()):
                lines.append(f"chronus_workload_requests_total{{{labels}}} {count}")

        lines.extend([
            "",
            "# HELP chronus_execution_latency_seconds Execution duration percentiles (p50, p95, p99)",
            "# TYPE chronus_execution_latency_seconds summary",
            f'chronus_execution_latency_seconds{{quantile="0.50"}} {p50:.6f}',
            f'chronus_execution_latency_seconds{{quantile="0.95"}} {p95:.6f}',
            f'chronus_execution_latency_seconds{{quantile="0.99"}} {p99:.6f}',
            f'chronus_execution_latency_seconds_count {len(self.latencies)}',
            f'chronus_execution_latency_seconds_sum {sum(self.latencies):.6f}',
            "",
            "# HELP chronus_ccu_consumed_total Chronus Capacity Units (CCU) consumed by tenants",
            "# TYPE chronus_ccu_consumed_total counter",
        ])

        if not self.ccu_consumed:
            lines.append('chronus_ccu_consumed_total{tenant_id="default"} 0.0')
        else:
            for tenant, ccu in sorted(self.ccu_consumed.items()):
                lines.append(f'chronus_ccu_consumed_total{{tenant_id="{tenant}"}} {ccu:.4f}')

        lines.extend([
            "",
            "# HELP chronus_hardware_memory_bytes Observed hardware memory bytes reported by an adapter",
            "# TYPE chronus_hardware_memory_bytes gauge",
        ])

        for labels, mem_bytes in sorted(self.hardware_memory.items()):
            lines.append(f"chronus_hardware_memory_bytes{{{labels}}} {mem_bytes}")

        return "\n".join(lines) + "\n"


metrics_registry = PrometheusMetricsRegistry()
