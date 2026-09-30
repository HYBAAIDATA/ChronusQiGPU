"""Canonical lazy facade for the production Aethel manifold."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "GeodesicNavigator": ("aethel.manifold", "GeodesicNavigator"),
    "ManifoldCurvature": ("aethel.manifold", "ManifoldCurvature"),
    "ManifoldSector": ("aethel.manifold", "ManifoldSector"),
    "PrimeStorageManifold": ("aethel.manifold", "PrimeStorageManifold"),
    "SelfHealingSubstrate": ("aethel.manifold", "SelfHealingSubstrate"),
    "TensorCoreGPU_Context": ("aethel.gpu", "TensorCoreGPU_Context"),
    "TopologicalTensor": ("aethel.manifold", "TopologicalTensor"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    """Resolve manifold types without constructing or probing a device."""
    try:
        module_name, attribute = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    return getattr(import_module(module_name), attribute)