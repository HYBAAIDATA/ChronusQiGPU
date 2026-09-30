"""Compatibility facade for the existing ASIC solver."""

from importlib import import_module
from typing import Any

__all__ = ["ASICSolver"]


def __getattr__(name: str) -> Any:
    """Resolve the ASIC implementation without eager optional imports."""
    if name != "ASICSolver":
        raise AttributeError(name)
    module = import_module("python_backend.hyba.hybrid")
    return getattr(module, name)