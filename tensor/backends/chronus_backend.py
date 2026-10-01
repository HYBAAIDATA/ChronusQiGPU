"""Optional Chronus hardware accelerator adapter.

This adapter uses lazy, dynamic imports so that importing ``tensor`` (or
even this module) never requires Chronus, OpenCL, or any GPU driver to be
installed. Availability is reported honestly: when Chronus or a usable
device is absent, :meth:`ChronusBackend.is_available` returns ``False``
rather than raising, and :meth:`execute` raises
:class:`tensor.errors.TensorBackendUnavailableError` rather than silently
falling back to the CPU reference backend.

No Chronus namespace migration happens here — this module only calls the
existing public ``chronus`` package surface via ``importlib``, so it has no
import-time coupling to that package's internal layout.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any, Dict, Sequence

from ..contracts import TensorOperationSpec
from ..errors import TensorBackendUnavailableError, TensorValidationError

#: Chronus does not currently expose generic tensor compute kernels (it is
#: specialised for SHA-256d search). No operation is executable yet; this is
#: tracked honestly in the capability manifest as hardware-evidence-required.
SUPPORTED_OPERATIONS: tuple[str, ...] = ()


class ChronusBackend:
    """Lazy adapter over the optional ``chronus`` hardware package."""

    def __init__(self) -> None:
        self._name = "chronus-opencl"
        self._device_id = "unknown"

    @property
    def name(self) -> str:
        return self._name

    @property
    def backend_class(self) -> str:
        return "hardware"

    @property
    def device_id(self) -> str:
        return self._device_id

    def _detect(self) -> Any:
        """Dynamically import chronus.detect and run device detection.

        Returns ``None`` (never raises) when chronus, pyopencl, or a device
        is unavailable, so callers can report honest unavailability.
        """
        try:
            detect = import_module("chronus.detect")
            report = detect.detect_all()
        except Exception:  # noqa: BLE001 - any failure means "no evidence of hardware"
            return None
        devices = getattr(report, "devices", None)
        if not devices:
            return None
        return report

    def is_available(self) -> bool:
        return self._detect() is not None

    def capabilities(self) -> Dict[str, object]:
        report = self._detect()
        device_count = len(getattr(report, "devices", ())) if report is not None else 0
        return {
            "operations": SUPPORTED_OPERATIONS,
            "device_count": device_count,
            "deterministic": False,
            "status": "hardware-evidence-required",
        }

    def supports(self, operation: TensorOperationSpec) -> bool:
        return operation.name in SUPPORTED_OPERATIONS

    def execute(
        self, operation: TensorOperationSpec, inputs: Sequence[Any], *, deterministic: bool
    ):
        del inputs, deterministic
        if not self.is_available():
            raise TensorBackendUnavailableError(
                "chronus-opencl backend is unavailable on this host "
                "(no chronus-detectable OpenCL device); no silent CPU fallback"
            )
        raise TensorValidationError(
            f"chronus-opencl backend has no tensor kernel for operation "
            f"'{operation.name}' yet; this is tracked as "
            "hardware-evidence-required in the tensor capability manifest"
        )


def create() -> ChronusBackend:
    """Factory used by the default backend registry. Does not touch hardware."""
    return ChronusBackend()


__all__ = ["ChronusBackend", "SUPPORTED_OPERATIONS", "create"]
