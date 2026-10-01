"""Lazy bridge from Tensor to the canonical exact PULVINI/Geodesic substrate."""
from __future__ import annotations

from importlib import import_module
from typing import Any

_MODULE = "python_backend.core_modules.geodesic_tensor_engine"


def load_geodesic_tensor_engine():
    return import_module(_MODULE)


def fold_exact(*args: Any, **kwargs: Any):
    return load_geodesic_tensor_engine().fold_exact(*args, **kwargs)


def unfold_partial(*args: Any, **kwargs: Any):
    return load_geodesic_tensor_engine().unfold_partial(*args, **kwargs)


__all__ = ["fold_exact", "load_geodesic_tensor_engine", "unfold_partial"]
