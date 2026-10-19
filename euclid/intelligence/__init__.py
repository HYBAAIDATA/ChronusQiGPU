"""EUCLID Unified Intelligence Engine (`euclid.intelligence`).

Consolidates the entire intelligence substrate into a unified canonical architecture:
- `euclid.intelligence.physics`: TOE physical simulation, quantum operators, Lucas metallic walks.
- `euclid.intelligence.cognition`: Empirical state control, mathematical research, repository review.
- `euclid.intelligence.gatekeeper`: Unified AL HARAS security, pre-execution audit, and rollback.
"""
from __future__ import annotations

import importlib
from typing import Any

from . import physics
from . import cognition
from . import gatekeeper
from .gatekeeper import UnifiedIntelligenceGatekeeper

__all__ = [
    "physics",
    "cognition",
    "gatekeeper",
    "UnifiedIntelligenceGatekeeper",
]


def __getattr__(name: str) -> Any:
    # Fallback to top-level Intelligence package for legacy/leaf attributes
    import Intelligence
    if hasattr(Intelligence, name):
        val = getattr(Intelligence, name)
        globals()[name] = val
        return val

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    import Intelligence
    return sorted(set(globals()) | set(__all__) | set(dir(Intelligence)))
