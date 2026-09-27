"""Backend binding surface for the HYBA composition layer.

Canonical implementation lives at :mod:`Intelligence.backend_binding`; this
module re-exports it so ``hyba`` operator code has one stable import surface.
The binders are fail-explicit: ``HYBA_REQUIRE_GPU`` / ``HYBA_REQUIRE_HYBA`` and
the device-identity env gates are enforced there, not reimplemented here.

LUCAS WIRING: coordinator module — re-exports only; adds no algorithm.
Substrate route: gap
"""

from __future__ import annotations

from Intelligence.backend_binding import (
    GPU_BACKENDS,
    PREFERENCE_ORDER,
    BackendBinder,
    BackendDetector,
    BackendType,
    BoundBackend,
    BoundBackends,
    DetectedBackend,
    GPUUnavailableError,
    get_compute_backend,
    reset_compute_backend,
)

__all__ = [
    "GPU_BACKENDS",
    "PREFERENCE_ORDER",
    "BackendBinder",
    "BackendDetector",
    "BackendType",
    "BoundBackend",
    "BoundBackends",
    "DetectedBackend",
    "GPUUnavailableError",
    "get_compute_backend",
    "reset_compute_backend",
]
