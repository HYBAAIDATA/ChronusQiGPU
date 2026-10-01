"""Deterministic backend router for the ``tensor`` package.

Routing rules (fail-closed by default):

* If ``request.backend_required`` names a specific backend, that backend is
  used or the call fails with :class:`TensorBackendUnavailableError` — there
  is never a silent substitution of a different backend when one was
  explicitly required.
* If ``request.backend_required`` is ``None`` (automatic mode), the router
  tries backends in registry priority order. It may only fall back past an
  unavailable or non-supporting backend when ``request.allow_fallback`` is
  ``True`` — the policy must explicitly allow it — and the fallback is
  always recorded in the returned :class:`tensor.contracts.TensorMeasurement`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .backends import BackendRegistry, TensorBackend
from .contracts import TensorOperationSpec, TensorRequest
from .errors import TensorBackendUnavailableError


@dataclass(frozen=True)
class RouteDecision:
    """The backend selected for one request, with fallback evidence."""

    backend: TensorBackend
    fallback_used: bool
    fallback_reason: str


def default_registry() -> BackendRegistry:
    """Build the default registry: NumPy reference first, Chronus optional."""
    from .backends import chronus_backend, numpy_backend

    registry = BackendRegistry()
    registry.register("numpy-cpu", numpy_backend.create, priority=10)
    registry.register("chronus-opencl", chronus_backend.create, priority=50)
    return registry


def route(
    request: TensorRequest,
    operation: TensorOperationSpec,
    registry: Optional[BackendRegistry] = None,
) -> RouteDecision:
    """Select a backend for ``operation`` according to ``request`` policy."""
    registry = registry if registry is not None else default_registry()

    if request.backend_required is not None:
        backend = registry.get(request.backend_required)
        if not backend.is_available():
            raise TensorBackendUnavailableError(
                f"backend '{request.backend_required}' was explicitly required "
                "but is not available on this host"
            )
        if not backend.supports(operation):
            raise TensorBackendUnavailableError(
                f"backend '{request.backend_required}' does not support "
                f"operation '{operation.name}'"
            )
        return RouteDecision(backend=backend, fallback_used=False, fallback_reason="")

    names = registry.names()
    if not names:
        raise TensorBackendUnavailableError("no backends are registered")

    preferred_name = names[0]
    preferred = registry.get(preferred_name)
    if preferred.is_available() and preferred.supports(operation):
        return RouteDecision(backend=preferred, fallback_used=False, fallback_reason="")

    if not request.allow_fallback:
        raise TensorBackendUnavailableError(
            f"preferred backend '{preferred_name}' is unavailable or does not "
            f"support '{operation.name}', and automatic fallback is not "
            "permitted by policy (request.allow_fallback=False)"
        )

    for name in names[1:]:
        candidate = registry.get(name)
        if candidate.is_available() and candidate.supports(operation):
            reason = (
                f"preferred backend '{preferred_name}' unavailable or unsupported "
                f"for '{operation.name}'; fell back to '{name}' per explicit policy"
            )
            return RouteDecision(backend=candidate, fallback_used=True, fallback_reason=reason)

    raise TensorBackendUnavailableError(
        f"no registered backend is available and supports operation '{operation.name}'"
    )


__all__ = ["RouteDecision", "default_registry", "route"]
