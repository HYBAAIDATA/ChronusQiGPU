"""HYBA backend binding — fail-explicit re-export, not a fork.

The implementation lives in :mod:`Intelligence.backend_binding` (LUCAS
WIRING purity: algorithm modules must not import siblings). This module
only re-exports it so ``hyba`` is the one import site for operators.
"""

from __future__ import annotations

from Intelligence.backend_binding import (
    BackendBinder,
    BackendDetector,
    BackendType,
    BoundBackend,
    DetectedBackend,
    GPU_BACKENDS,
    GPUUnavailableError,
    PREFERENCE_ORDER,
    get_compute_backend,
    reset_compute_backend,
)

__all__ = [
    "BackendBinder",
    "BackendDetector",
    "BackendType",
    "BoundBackend",
    "DetectedBackend",
    "GPU_BACKENDS",
    "GPUUnavailableError",
    "PREFERENCE_ORDER",
    "get_compute_backend",
    "reset_compute_backend",
]
