"""Chronus — HYBA's canonical iGPU offering.

Turing is the computation substrate. Chronus is the hardware-facing offering
that binds Turing computation to measured device discovery, resident execution,
state memory, kernel dispatch, telemetry, routing and attestation.

Hardware probing stays lazy: importing :mod:`chronus` never requires OpenCL,
CUDA, Metal or a physical accelerator. Public runtime objects are loaded only
when requested, so control-plane and audit tooling remain usable on CPU-only
hosts.
"""
from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .detect import DetectedDevice, DetectionReport
    from .device import Chronus
    from .engine import ChronusOpenCLEngine, ChronusOpenCLUnavailable, ResidentChronusEnsemble, ResidentChronusState
    from .fabric import ChronusFabric, RouteDecision
    from .telemetry import ChronusTelemetry
    from .tensor_compute import ChronusTensorRuntime, ChronusTensorUnavailable, TensorDeviceProbe

_EXPORTS = {
    "CLAIM_BOUNDARY": ("chronus.device", "CLAIM_BOUNDARY"),
    "DEVICE_ID": ("chronus.device", "DEVICE_ID"),
    "Chronus": ("chronus.device", "Chronus"),
    "ChronusFabric": ("chronus.fabric", "ChronusFabric"),
    "ChronusOpenCLEngine": ("chronus.engine", "ChronusOpenCLEngine"),
    "ChronusOpenCLUnavailable": ("chronus.engine", "ChronusOpenCLUnavailable"),
    "ChronusTelemetry": ("chronus.telemetry", "ChronusTelemetry"),
    "DetectedDevice": ("chronus.detect", "DetectedDevice"),
    "DetectionReport": ("chronus.detect", "DetectionReport"),
    "ResidentChronusEnsemble": ("chronus.engine", "ResidentChronusEnsemble"),
    "ResidentChronusState": ("chronus.engine", "ResidentChronusState"),
    "RouteDecision": ("chronus.fabric", "RouteDecision"),
    "attach_to_host": ("chronus.telemetry", "attach_to_host"),
    "detect_all": ("chronus.detect", "detect_all"),
    "get_telemetry": ("chronus.telemetry", "get_telemetry"),
    "open_device": ("chronus.device", "open_device"),
    "ChronusTensorRuntime": ("chronus.tensor_compute", "ChronusTensorRuntime"),
    "ChronusTensorUnavailable": ("chronus.tensor_compute", "ChronusTensorUnavailable"),
    "TensorDeviceProbe": ("chronus.tensor_compute", "TensorDeviceProbe"),
    "get_tensor_runtime": ("chronus.tensor_compute", "get_tensor_runtime"),
    "probe_tensor": ("chronus.tensor_compute", "probe_tensor"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attribute = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name), attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
