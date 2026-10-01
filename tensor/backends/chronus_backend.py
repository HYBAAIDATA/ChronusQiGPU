"""Chronus OpenCL tensor backend.

The adapter is import-light and fail-closed. ``chronus.tensor_compute`` is
loaded only when probed/executed; no OpenCL dependency is required to import
:mod:`tensor`. A result is reported as ``chronus-opencl`` only after physical
GPU/accelerator execution. CPU fallback remains Tensor-router policy.
"""
from __future__ import annotations

from importlib import import_module
from typing import Any, Dict, Sequence

from ..contracts import Precision, TensorOperationSpec
from ..errors import TensorBackendUnavailableError, TensorValidationError

SUPPORTED_OPERATIONS=("matmul","add","scale","kron","hadamard")
SUPPORTED_DTYPES=(Precision.FLOAT32,)


class ChronusBackend:
    def __init__(self) -> None:
        self._name="chronus-opencl"; self._device_id="unprobed"; self._last_probe=None

    @property
    def name(self): return self._name
    @property
    def backend_class(self): return "hardware"
    @property
    def device_id(self):
        if self._last_probe is None: self._probe()
        return self._device_id

    def _module(self): return import_module("chronus.tensor_compute")

    def _probe(self) -> dict[str,Any]:
        try:
            report=self._module().probe()
            data=report.as_dict() if hasattr(report,"as_dict") else dict(report)
        except Exception as exc:
            data={"available":False,"device_id":"unavailable","device_name":"",
                  "platform_name":"","reason":f"{type(exc).__name__}: {exc}"}
        self._last_probe=data; self._device_id=str(data.get("device_id") or "unavailable")
        return data

    def is_available(self) -> bool: return bool(self._probe().get("available",False))

    def capabilities(self) -> Dict[str,object]:
        report=self._probe()
        return {"operations":SUPPORTED_OPERATIONS,"dtypes":tuple(p.value for p in SUPPORTED_DTYPES),
                "deterministic_device_execution":True,"device_name":report.get("device_name",""),
                "platform_name":report.get("platform_name",""),"status":"hardware-evidence-required",
                "available":bool(report.get("available",False)),"reason":report.get("reason","")}

    @staticmethod
    def _shape_supported(operation: TensorOperationSpec) -> bool:
        shapes=operation.input_shapes
        if operation.name in {"add","hadamard"}:
            return len(shapes)==2 and shapes[0].dims==shapes[1].dims
        if operation.name=="scale": return len(shapes)==2 and shapes[1].size==1
        if operation.name=="matmul":
            return (len(shapes)==2 and len(shapes[0].dims)==2 and len(shapes[1].dims)==2
                    and shapes[0].dims[1]==shapes[1].dims[0]
                    and operation.output_shape.dims==(shapes[0].dims[0],shapes[1].dims[1]))
        if operation.name=="kron":
            if len(shapes)!=2 or len(shapes[0].dims)!=len(shapes[1].dims): return False
            if len(shapes[0].dims)==1:
                return operation.output_shape.dims==(shapes[0].dims[0]*shapes[1].dims[0],)
            if len(shapes[0].dims)==2:
                return operation.output_shape.dims==(
                    shapes[0].dims[0]*shapes[1].dims[0],shapes[0].dims[1]*shapes[1].dims[1])
        return False

    def supports(self, operation: TensorOperationSpec) -> bool:
        return (operation.name in SUPPORTED_OPERATIONS and operation.dtype in SUPPORTED_DTYPES
                and self._shape_supported(operation))

    def execute(self, operation: TensorOperationSpec, inputs: Sequence[Any], *, deterministic: bool):
        del deterministic
        if not self.supports(operation):
            raise TensorValidationError(
                f"chronus-opencl does not support {operation.name!r} at {operation.dtype.value} "
                "for the declared shapes")
        report=self._probe()
        if not report.get("available",False):
            raise TensorBackendUnavailableError(
                "chronus-opencl tensor backend is unavailable on this host: "
                f"{report.get('reason','no physical OpenCL GPU')}; no silent CPU fallback")
        try:
            runtime=self._module().get_runtime(); self._device_id=str(runtime.device_id)
            return runtime.execute(operation.name,inputs,
                                   tuple(shape.dims for shape in operation.input_shapes),
                                   operation.output_shape.dims)
        except ValueError as exc:
            raise TensorValidationError(str(exc)) from exc
        except RuntimeError as exc:
            raise TensorBackendUnavailableError(
                f"chronus-opencl tensor execution failed closed: {exc}") from exc


def create() -> ChronusBackend: return ChronusBackend()

__all__=["ChronusBackend","SUPPORTED_DTYPES","SUPPORTED_OPERATIONS","create"]
