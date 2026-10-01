"""Always-available NumPy/CPU reference backend.

This backend is the deterministic ground truth every other backend is
measured against. It has no optional dependencies beyond NumPy (already a
hard dependency of this project) and is always reported available.
"""

from __future__ import annotations

from typing import Dict, Sequence

import numpy as np

from ..contracts import Precision, TensorOperationSpec
from ..errors import TensorValidationError

_DTYPE_MAP = {
    Precision.FLOAT32: np.float32,
    Precision.FLOAT64: np.float64,
    Precision.COMPLEX64: np.complex64,
    Precision.COMPLEX128: np.complex128,
}

#: Operation names this backend declares support for.
SUPPORTED_OPERATIONS = ("matmul", "add", "scale", "kron", "hadamard")


class NumpyBackend:
    """Deterministic CPU reference backend over NumPy arrays."""

    def __init__(self) -> None:
        self._name = "numpy-cpu"
        self._device_id = "cpu:0"

    @property
    def name(self) -> str:
        return self._name

    @property
    def backend_class(self) -> str:
        return "reference"

    @property
    def device_id(self) -> str:
        return self._device_id

    def is_available(self) -> bool:
        # NumPy is a hard dependency; this backend never silently degrades.
        return True

    def capabilities(self) -> Dict[str, object]:
        return {
            "operations": SUPPORTED_OPERATIONS,
            "dtypes": tuple(p.value for p in _DTYPE_MAP),
            "deterministic": True,
        }

    def supports(self, operation: TensorOperationSpec) -> bool:
        return operation.name in SUPPORTED_OPERATIONS and operation.dtype in _DTYPE_MAP

    def execute(
        self, operation: TensorOperationSpec, inputs: Sequence[np.ndarray], *, deterministic: bool
    ):
        del deterministic  # NumPy's CPU arithmetic below is already deterministic.
        if not self.supports(operation):
            raise TensorValidationError(
                f"numpy-cpu backend does not support operation '{operation.name}' "
                f"at dtype {operation.dtype.value}"
            )
        dtype = _DTYPE_MAP[operation.dtype]
        arrays = [np.asarray(value, dtype=dtype) for value in inputs]
        for array, shape in zip(arrays, operation.input_shapes):
            if tuple(array.shape) != tuple(shape.dims):
                raise TensorValidationError(
                    f"input shape {array.shape} does not match declared shape {shape.dims}"
                )
        if operation.name == "matmul":
            if len(arrays) != 2:
                raise TensorValidationError("matmul requires exactly two inputs")
            result = np.matmul(arrays[0], arrays[1])
        elif operation.name == "add":
            if len(arrays) != 2:
                raise TensorValidationError("add requires exactly two inputs")
            result = arrays[0] + arrays[1]
        elif operation.name == "hadamard":
            if len(arrays) != 2:
                raise TensorValidationError("hadamard requires exactly two inputs")
            result = arrays[0] * arrays[1]
        elif operation.name == "scale":
            if len(arrays) != 2:
                raise TensorValidationError("scale requires a tensor and a scalar array")
            result = arrays[0] * arrays[1]
        elif operation.name == "kron":
            if len(arrays) != 2:
                raise TensorValidationError("kron requires exactly two inputs")
            result = np.kron(arrays[0], arrays[1])
        else:  # pragma: no cover - guarded by supports() above
            raise TensorValidationError(f"unsupported operation '{operation.name}'")
        if tuple(result.shape) != tuple(operation.output_shape.dims):
            raise TensorValidationError(
                f"computed output shape {result.shape} does not match declared "
                f"output shape {operation.output_shape.dims}"
            )
        return result


def create() -> NumpyBackend:
    """Factory used by the default backend registry."""
    return NumpyBackend()


__all__ = ["NumpyBackend", "SUPPORTED_OPERATIONS", "create"]
