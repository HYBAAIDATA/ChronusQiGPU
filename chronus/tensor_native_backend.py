"""Chronus native CUDA/Metal tensor backends.

These adapters sit alongside the existing ``chronus-opencl`` backend. They
never substitute for one another internally and never fall back to CPU. The
Tensor router remains the only place where fallback policy may be applied.
"""
from __future__ import annotations

from importlib import import_module
from typing import Any, Dict, Sequence

from ..contracts import Precision, TensorOperationSpec
from ..errors import TensorBackendUnavailableError, TensorValidationError

SUPPORTED_OPERATIONS = ("matmul", "add", "scale", "kron", "hadamard")
SUPPORTED_DTYPES = (Precision.FLOAT32,)


def _shape_supported(operation: TensorOperationSpec) -> bool:
    shapes = operation.input_shapes
    if operation.name in {"add", "hadamard"}:
        return len(shapes) == 2 and shapes[0].dims == shapes[1].dims
    if operation.name == "scale":
        return len(shapes) == 2 and shapes[1].size == 1
    if operation.name == "matmul":
        return (
            len(shapes) == 2
            and len(shapes[0].dims) == 2
            and len(shapes[1].dims) == 2
            and shapes[0].dims[1] == shapes[1].dims[0]
            and operation.output_shape.dims
            == (shapes[0].dims[0], shapes[1].dims[1])
        )
    if operation.name == "kron":
        if len(shapes) != 2 or len(shapes[0].dims) != len(shapes[1].dims):
            return False
        if len(shapes[0].dims) == 1:
            return operation.output_shape.dims == (
                shapes[0].dims[0] * shapes[1].dims[0],
            )
        if len(shapes[0].dims) == 2:
            return operation.output_shape.dims == (
                shapes[0].dims[0] * shapes[1].dims[0],
                shapes[0].dims[1] * shapes[1].dims[1],
            )
    return False


class ChronusNativeBackend:
    """One fail-closed native vendor execution backend."""

    def __init__(self, execution_api: str) -> None:
        if execution_api not in {"cuda", "metal"}:
            raise ValueError("execution_api must be 'cuda' or 'metal'")
        self.execution_api = execution_api
        self._name = f"chronus-{execution_api}"
        self._device_id = "unprobed"
        self._last_probe: dict[str, Any] | None = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def backend_class(self) -> str:
        return "hardware"

    @property
    def device_id(self) -> str:
        if self._last_probe is None:
            self._probe()
        return self._device_id

    @staticmethod
    def _module():
        return import_module("chronus.native_tensor")

    def _probe(self) -> dict[str, Any]:
        try:
            module = self._module()
            probe_fn = getattr(module, f"probe_{self.execution_api}")
            report = probe_fn()
            data = report.as_dict() if hasattr(report, "as_dict") else dict(report)
        except Exception as exc:
            data = {
                "backend": self.execution_api,
                "available": False,
                "device_id": "unavailable",
                "device_name": "",
                "platform_name": self.execution_api.upper(),
                "reason": f"{type(exc).__name__}: {exc}",
                "opencl_required": False,
            }
        self._last_probe = data
        self._device_id = str(data.get("device_id") or "unavailable")
        return data

    def is_available(self) -> bool:
        return bool(self._probe().get("available", False))

    def capabilities(self) -> Dict[str, object]:
        report = self._probe()
        return {
            "operations": SUPPORTED_OPERATIONS,
            "dtypes": tuple(dtype.value for dtype in SUPPORTED_DTYPES),
            "deterministic_device_execution": True,
            "execution_api": self.execution_api,
            "native_vendor_path": True,
            "opencl_required": False,
            "device_name": report.get("device_name", ""),
            "platform_name": report.get("platform_name", ""),
            "status": "hardware-evidence-required",
            "available": bool(report.get("available", False)),
            "reason": report.get("reason", ""),
        }

    def supports(self, operation: TensorOperationSpec) -> bool:
        return (
            operation.name in SUPPORTED_OPERATIONS
            and operation.dtype in SUPPORTED_DTYPES
            and _shape_supported(operation)
        )

    def execute(
        self,
        operation: TensorOperationSpec,
        inputs: Sequence[Any],
        *,
        deterministic: bool,
    ):
        del deterministic
        if not self.supports(operation):
            raise TensorValidationError(
                f"{self.name} does not support {operation.name!r} at "
                f"{operation.dtype.value} for the declared shapes"
            )
        report = self._probe()
        if not report.get("available", False):
            raise TensorBackendUnavailableError(
                f"{self.name} tensor backend is unavailable on this host: "
                f"{report.get('reason', 'native GPU runtime unavailable')}; "
                "no silent OpenCL or CPU fallback"
            )
        try:
            module = self._module()
            runtime_fn = getattr(module, f"get_{self.execution_api}_runtime")
            runtime = runtime_fn()
            self._device_id = str(runtime.device_id)
            return runtime.execute(
                operation.name,
                inputs,
                tuple(shape.dims for shape in operation.input_shapes),
                operation.output_shape.dims,
            )
        except ValueError as exc:
            raise TensorValidationError(str(exc)) from exc
        except RuntimeError as exc:
            raise TensorBackendUnavailableError(
                f"{self.name} tensor execution failed closed: {exc}"
            ) from exc


def create_cuda() -> ChronusNativeBackend:
    return ChronusNativeBackend("cuda")


def create_metal() -> ChronusNativeBackend:
    return ChronusNativeBackend("metal")


__all__ = [
    "ChronusNativeBackend",
    "SUPPORTED_DTYPES",
    "SUPPORTED_OPERATIONS",
    "create_cuda",
    "create_metal",
]
