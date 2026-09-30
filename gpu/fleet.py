"""Lazy access to the existing heterogeneous fleet implementation."""

from importlib import import_module
from typing import Any

_EXPORTS = {
    "ClusterInventory": ("python_backend.hyba.inventory", "ClusterInventory"),
    "SuperGPU": ("python_backend.hyba.virtual_gpu", "SuperGPU"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    """Resolve fleet classes without probing local devices on import."""
    try:
        module_name, attribute = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    return getattr(import_module(module_name), attribute)