"""PYTHIA iGPU runtime package.

The package keeps hardware probing lazy: importing :mod:`igpu` never requires
OpenCL, CUDA, Metal or a physical accelerator. Public runtime objects are
loaded only when requested, so control-plane and audit tooling remain usable on
CPU-only hosts.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .detect import DetectionReport, DetectedDevice
    from .device import IGPU
    from .engine import IGPUOpenCLEngine
    from .telemetry import IgpuTelemetry

_EXPORTS = {
    "DetectionReport": ("igpu.detect", "DetectionReport"),
    "DetectedDevice": ("igpu.detect", "DetectedDevice"),
    "IGPU": ("igpu.device", "IGPU"),
    "IGPUOpenCLEngine": ("igpu.engine", "IGPUOpenCLEngine"),
    "IgpuTelemetry": ("igpu.telemetry", "IgpuTelemetry"),
    "attach_to_host": ("igpu.telemetry", "attach_to_host"),
    "detect_all": ("igpu.detect", "detect_all"),
    "get_telemetry": ("igpu.telemetry", "get_telemetry"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    """Load an optional hardware-facing symbol on first use."""
    try:
        module_name, attribute = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name), attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
