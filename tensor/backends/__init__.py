"""Backend protocol and registry for the ``tensor`` package.

A backend is any object implementing :class:`TensorBackend`. The registry
holds backend *factories* (zero-arg callables) rather than instances so that
constructing an optional backend (e.g. Chronus) never happens at import
time — only when it is actually requested or health-checked.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Protocol, runtime_checkable

from ..contracts import TensorOperationSpec
from ..errors import TensorBackendUnavailableError


@runtime_checkable
class TensorBackend(Protocol):
    """The contract every tensor execution backend must satisfy."""

    @property
    def name(self) -> str: ...

    @property
    def backend_class(self) -> str:
        """One of: ``reference``, ``hardware``, ``simulator``."""
        ...

    @property
    def device_id(self) -> str: ...

    def is_available(self) -> bool:
        """Honest hardware/runtime availability check. Never raises."""
        ...

    def capabilities(self) -> Dict[str, object]:
        """Declared supported operation names and limits."""
        ...

    def supports(self, operation: TensorOperationSpec) -> bool:
        """Whether this backend can execute ``operation`` at all."""
        ...

    def execute(self, operation: TensorOperationSpec, inputs: tuple, *, deterministic: bool):
        """Execute ``operation`` over ``inputs`` and return raw output data.

        Must raise :class:`tensor.errors.TensorBackendUnavailableError` if
        called while :meth:`is_available` is ``False`` instead of silently
        falling back to another backend.
        """
        ...


class BackendRegistry:
    """A registry of backend factories, keyed by backend name.

    Backends register a zero-argument factory. Construction — and any
    optional/lazy import it triggers — is deferred until :meth:`get` or
    :meth:`health_report` actually needs an instance.
    """

    def __init__(self) -> None:
        self._factories: Dict[str, Callable[[], TensorBackend]] = {}
        self._priorities: Dict[str, int] = {}
        self._order: List[str] = []

    def register(
        self, name: str, factory: Callable[[], TensorBackend], *, priority: int = 100
    ) -> None:
        if not name.strip():
            raise ValueError("backend name must be non-empty")
        self._factories[name] = factory
        self._priorities[name] = priority
        if name not in self._order:
            self._order.append(name)

    def names(self) -> tuple[str, ...]:
        """Registered backend names, lowest priority number (most preferred) first."""
        return tuple(sorted(self._order, key=lambda n: (self._priorities[n], self._order.index(n))))

    def get(self, name: str) -> TensorBackend:
        try:
            factory = self._factories[name]
        except KeyError as exc:
            raise TensorBackendUnavailableError(f"no backend registered as '{name}'") from exc
        return factory()

    def health_report(self) -> Dict[str, Dict[str, object]]:
        """Honestly report every registered backend's availability.

        Construction failures (e.g. an optional dependency raising at
        instantiation) are captured as ``available: False`` with the
        exception recorded, never silently swallowed into a false "healthy".
        """
        report: Dict[str, Dict[str, object]] = {}
        for name in self.names():
            try:
                backend = self.get(name)
                available = bool(backend.is_available())
                report[name] = {
                    "available": available,
                    "backend_class": backend.backend_class,
                    "device_id": backend.device_id,
                    "capabilities": backend.capabilities(),
                    "error": None,
                }
            except Exception as exc:  # noqa: BLE001 - honest capture, not control flow
                report[name] = {
                    "available": False,
                    "backend_class": "unknown",
                    "device_id": "unknown",
                    "capabilities": {},
                    "error": f"{type(exc).__name__}: {exc}",
                }
        return report


__all__ = ["TensorBackend", "BackendRegistry"]
