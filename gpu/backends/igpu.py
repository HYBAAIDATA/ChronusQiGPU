"""Compatibility facade for the existing iGPU implementation."""

from importlib import import_module
from typing import Any

_EXPORTS = {
    "DeviceInfo": ("igpu", "DeviceInfo"),
    "IGPUConfig": ("igpu", "IGPUConfig"),
    "IGPUEngine": ("igpu", "IGPUEngine"),
    "Metrics": ("igpu", "Metrics"),
    "backend_available": ("igpu", "backend_available"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    """Resolve the legacy iGPU API only when an attribute is requested."""
    try:
        module_name, attribute = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    return getattr(import_module(module_name), attribute)