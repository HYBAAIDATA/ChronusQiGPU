"""Deprecated compatibility shim for hyba_euclid_intelligence.

Consolidated into `euclid.intelligence` under the unified EUCLID enterprise distribution.
"""
from __future__ import annotations

import warnings
from typing import Any

warnings.warn(
    "hyba_euclid_intelligence is deprecated and has been consolidated into euclid.intelligence. "
    "Please update your imports to `import euclid.intelligence` or `import Intelligence`.",
    DeprecationWarning,
    stacklevel=2,
)

import euclid.intelligence as intelligence

__all__ = [
    "intelligence",
]


def __getattr__(name: str) -> Any:
    if hasattr(intelligence, name):
        return getattr(intelligence, name)
    import euclid
    if hasattr(euclid, name):
        return getattr(euclid, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(globals()) | set(__all__) | set(dir(intelligence)))
