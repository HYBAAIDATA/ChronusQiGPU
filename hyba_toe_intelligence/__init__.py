"""Deprecated compatibility shim for hyba_toe_intelligence.

Consolidated into `euclid.intelligence.physics` under the unified EUCLID enterprise distribution.
"""
from __future__ import annotations

import warnings
from typing import Any

warnings.warn(
    "hyba_toe_intelligence is deprecated and has been consolidated into euclid.intelligence.physics. "
    "Please update your imports to `from euclid.intelligence import physics` or `import Intelligence.physics`.",
    DeprecationWarning,
    stacklevel=2,
)

import Intelligence.physics as physics

__all__ = [
    "physics",
]


def __getattr__(name: str) -> Any:
    if hasattr(physics, name):
        return getattr(physics, name)
    import Intelligence
    if hasattr(Intelligence, name):
        return getattr(Intelligence, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(globals()) | set(__all__) | set(dir(physics)))
