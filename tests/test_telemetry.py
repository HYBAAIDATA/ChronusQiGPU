"""Regression tests for truthful process-local telemetry."""

import pytest

from chronus.service.telemetry import PrometheusMetricsRegistry, current_trace_id, trace_span

pytestmark = pytest.mark.real


def test_hardware_metrics_are_absent_until_observed():
    registry = PrometheusMetricsRegistry()
    rendered = registry.render_metrics()
    assert "chronus_hardware_memory_bytes{" not in rendered
    assert registry.hardware_memory == {}


def test_hardware_metric_records_only_explicit_observation():
    registry = PrometheusMetricsRegistry()
    registry.set_hardware_memory("cpu:reference", "python", 4096)
    assert 'chronus_hardware_memory_bytes{device="cpu:reference",backend="python"} 4096' in registry.render_metrics()
    with pytest.raises(ValueError):
        registry.set_hardware_memory("cpu:reference", "python", -1)


def test_prometheus_labels_are_escaped():
    registry = PrometheusMetricsRegistry()
    registry.record_request('tenant"\nforged', "COMPLETED", "LUCAS")
    output = registry.render_metrics()
    assert 'tenant_id="tenant\\"\\nforged"' in output


def test_trace_context_is_restored_after_span():
    token = current_trace_id.set("outer")
    try:
        with trace_span("test-span"):
            pass
        assert current_trace_id.get() == "outer"
    finally:
        current_trace_id.reset(token)
