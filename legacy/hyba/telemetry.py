"""HYBA iGPU telemetry — re-export of the dispatch collector."""

from __future__ import annotations

from Intelligence.igpu_telemetry import (
    IGpuTelemetryCollector,
    attach_igpu_telemetry,
    get_last_igpu_telemetry,
    igpu_telemetry_hook,
    reset_igpu_telemetry,
)

__all__ = [
    "IGpuTelemetryCollector",
    "attach_igpu_telemetry",
    "get_last_igpu_telemetry",
    "igpu_telemetry_hook",
    "reset_igpu_telemetry",
]
