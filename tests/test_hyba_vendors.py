"""Vendor probe + aggregated report regressions (no GPU required)."""

import json

from hyba import gpureport, vendors


def test_vendor_probes_report_honest_absence():
    """Each probe returns present flag + detail, never raises."""
    for probe in vendors.probe_all():
        doc = probe.as_dict()
        assert isinstance(doc["present"], bool)
        assert doc["detail"]
        assert isinstance(doc["devices"], list)


def test_probe_summary_selects_container_hint():
    """Summary exposes executing vs planning backends + hint."""
    summary = vendors.probe_summary()
    assert summary["executing_backends"] == ["opencl", "cpu"]
    assert "cpu" in summary["planning_backends"]
    assert summary["container_hint"]


def test_gpu_report_sections_serialize():
    """Aggregated report is JSON-safe and has all four sections."""
    doc = gpureport.report()
    assert set(doc) == {"opencl", "vendors", "hasher", "punch"}
    json.dumps(doc, default=str)
