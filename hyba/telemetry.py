"""HYBA iGPU telemetry — re-export of the canonical Chronus telemetry collector."""

from __future__ import annotations

from chronus.telemetry import (
    ChronusTelemetry,
    ChronusTelemetry as IGpuTelemetryCollector,
    attach_to_host,
    attach_to_host as attach_igpu_telemetry,
    attach_to_host as igpu_telemetry_hook,
    get_telemetry,
    get_telemetry as get_last_igpu_telemetry,
    reset_telemetry,
    reset_telemetry as reset_igpu_telemetry,
)

EUCLID_CHRONUS_TELEMETRY = "EUCLID_CHRONUS_TELEMETRY"

__all__ = [
    "ChronusTelemetry",
    "EUCLID_CHRONUS_TELEMETRY",
    "IGpuTelemetryCollector",
    "attach_igpu_telemetry",
    "attach_to_host",
    "get_last_igpu_telemetry",
    "get_telemetry",
    "igpu_telemetry_hook",
    "reset_igpu_telemetry",
    "reset_telemetry",
]
