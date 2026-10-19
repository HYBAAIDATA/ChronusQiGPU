"""Dispatch-contract validation: declared output shapes proven before allocation."""
import numpy as np
import pytest

from chronus import native_tensor
from chronus.tensor_compute import (
    ChronusTensorRuntime,
    ChronusTensorValidationError,
    validate_dispatch,
)

_U32_MAX = (1 << 32) - 1


@pytest.mark.parametrize(
    "operation,input_shapes,output_shape",
    [
        ("add", [(4,), (4,)], (4,)),
        ("add", [(2, 3), (2, 3)], (2, 3)),
        ("hadamard", [(2, 3), (2, 3)], (2, 3)),
        ("scale", [(2, 3), (1,)], (2, 3)),
        ("scale", [(2, 3), ()], (2, 3)),
        ("matmul", [(2, 3), (3, 2)], (2, 2)),
        ("kron", [(3,), (4,)], (12,)),
        ("kron", [(2, 3), (4, 5)], (8, 15)),
        ("kron", [(_U32_MAX,), (1,)], (_U32_MAX,)),
    ],
)
def test_valid_dispatch_is_accepted(operation, input_shapes, output_shape):
    validate_dispatch(operation, input_shapes, output_shape)


@pytest.mark.parametrize(
    "operation,input_shapes,output_shape",
    [
        ("add", [(4,), (4,)], (3,)),
        ("add", [(4,), (4,)], (4, 1)),
        ("add", [(4,), (3,)], (4,)),
        ("hadamard", [(2, 3), (2, 3)], (6,)),
        ("scale", [(2, 3), (1,)], (6,)),
        ("scale", [(2, 3), (2,)], (2, 3)),
        ("matmul", [(2, 3), (3, 2)], (2, 3)),
        ("matmul", [(2, 3), (4, 2)], (2, 2)),
        ("matmul", [(4,), (4,)], (4,)),
        ("kron", [(3,), (4,)], (11,)),
        ("kron", [(2, 3), (4, 5)], (8, 16)),
        ("kron", [(2, 2, 2), (2, 2, 2)], (4, 4, 4)),
        ("kron", [(3,), (3, 3)], (9,)),
    ],
)
def test_mismatched_dispatch_is_rejected(operation, input_shapes, output_shape):
    with pytest.raises(ChronusTensorValidationError):
        validate_dispatch(operation, input_shapes, output_shape)


def test_unsupported_operation_is_rejected():
    with pytest.raises(ChronusTensorValidationError):
        validate_dispatch("sqrt", [(4,)], (4,))


@pytest.mark.parametrize(
    "operation,input_shapes,output_shape",
    [
        ("add", [(0,), (0,)], (0,)),
        ("add", [(-1,), (-1,)], (1,)),
        ("add", [(2.5,), (2.5,)], (2.5,)),
        ("add", [(_U32_MAX + 1,), (_U32_MAX + 1,)], (_U32_MAX + 1,)),
        ("matmul", [(65536, 65536), (65536, 1)], (65536, 1)),
    ],
)
def test_unsafe_dimensions_are_rejected(operation, input_shapes, output_shape):
    with pytest.raises(ChronusTensorValidationError):
        validate_dispatch(operation, input_shapes, output_shape)


def test_validation_precedes_allocation(monkeypatch):
    runtime = ChronusTensorRuntime.__new__(ChronusTensorRuntime)

    def _forbid(self, *args, **kwargs):
        raise AssertionError("allocation reached before dispatch validation")

    monkeypatch.setattr(ChronusTensorRuntime, "_buffers", _forbid)
    ones = np.ones(4, dtype=np.float32)
    with pytest.raises(ChronusTensorValidationError):
        runtime.execute_with_evidence("add", [ones, ones], [(4,), (4,)], (3,))


class _OversizedOperand:
    size = _U32_MAX + 1
    shape = (_U32_MAX + 1,)


def test_native_backends_reject_oversized_operands():
    with pytest.raises(native_tensor.ChronusNativeTensorValidationError):
        native_tensor._validate_common(
            "add", [_OversizedOperand(), _OversizedOperand()], (_U32_MAX + 1,)
        )


def test_native_backends_reject_output_mismatch():
    a = np.ones(4, dtype=np.float32)
    with pytest.raises(native_tensor.ChronusNativeTensorValidationError):
        native_tensor._validate_common("add", [a, a], (3,))


def test_native_backends_reject_empty_output():
    a = np.ones(4, dtype=np.float32)
    with pytest.raises(native_tensor.ChronusNativeTensorValidationError):
        native_tensor._validate_common("add", [a, a], ())
