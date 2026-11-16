"""Regression checks for current OpenCL tensor output and source integrity.

These CPU-only checks do not establish physical GPU execution, device identity,
latency, or deployment. The optional hardware test skips if no GPU is present.
"""
from __future__ import annotations

from importlib.resources import files

import numpy as np
import pytest

from chronus.tensor.geodesic import TopologicalIntegrityGate
from chronus.tensor.opencl_backend import OpenCLTensorBackend


def test_componentwise_higham_accepts_actual_float32_result():
    a = np.array([[1.0, 2.0, -3.0], [4.0, 5.0, 6.0]], dtype=np.float32)
    b = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]], dtype=np.float32)
    expected = a @ b
    gate = TopologicalIntegrityGate()
    verdict = gate.verify_float32_matmul(expected, a, b)
    assert verdict.passed is True
    assert verdict.shape_match is True
    assert verdict.dtype_match is True
    assert gate.checks_performed == 1
    assert gate.checks_passed == 1


def test_componentwise_higham_rejects_corrupt_output():
    a = np.arange(1, 7, dtype=np.float32).reshape(2, 3)
    b = np.arange(1, 7, dtype=np.float32).reshape(3, 2)
    wrong = a @ b
    wrong[1, 1] += 1.0
    verdict = TopologicalIntegrityGate().verify_float32_matmul(wrong, a, b)
    assert verdict.passed is False


def test_componentwise_higham_rejects_forged_dtype_and_nan():
    a = np.eye(2, dtype=np.float32)
    b = np.eye(2, dtype=np.float32)
    gate = TopologicalIntegrityGate()
    assert not gate.verify_float32_matmul(a.astype(np.float64), a, b).passed
    invalid = a.copy()
    invalid[0, 0] = np.nan
    assert not gate.verify_float32_matmul(invalid, a, b).passed
    assert not gate.verify_float32_matmul(np.eye(3, dtype=np.float32), a, b).passed


@pytest.mark.parametrize("bad", [
    np.array([1., 2.], dtype=np.float64),
    np.array([1 + 2j], dtype=np.complex64),
    np.array([float("nan")], dtype=np.float32),
    np.array([], dtype=np.float32),
])
def test_opencl_rejects_unsupported_or_invalid_tensor_data(bad):
    with pytest.raises(ValueError):
        OpenCLTensorBackend._f32(bad)


def test_opencl_kernel_lane_mapping_and_operation_coverage():
    source = files("chronus.kernels").joinpath("tensor_ops.cl").read_text("utf-8")
    matrix = source.split("__kernel void tensor_matmul(", 1)[1].split(
        "__kernel void tensor_kron2(", 1
    )[0]
    kron = source.split("__kernel void tensor_kron2(", 1)[1]
    for snippet in [matrix, kron]:
        assert "size_t col = get_global_id(0);" in snippet
        assert "size_t row = get_global_id(1);" in snippet
    for name in ["tensor_add", "tensor_hadamard", "tensor_scale",
                 "tensor_matmul", "tensor_kron2"]:
        assert f"__kernel void {name}(" in source


def test_optional_real_opencl_gpu_exercises_every_kernel():
    backend = OpenCLTensorBackend()
    if not backend.is_available():
        pytest.skip("NO_PHYSICAL_OPENCL_GPU: GPU evidence unavailable")
    a = np.array([[1., 2.], [3., 4.]], dtype=np.float32)
    b = np.array([[5., 6.], [7., 8.]], dtype=np.float32)
    m = np.array([[1., 2., 3.], [4., 5., 6.]], dtype=np.float32)
    n = np.array([[1., 2.], [3., 4.], [5., 6.]], dtype=np.float32)
    reference = [
        ("add", (a, b), None, a + b),
        ("hadamard", (a, b), None, a * b),
        ("scale", (a,), 2., a * 2),
        ("matmul", (m, n), None, m @ n),
        ("kron", (m, a), None, np.kron(m, a)),
    ]
    for operation, values, scalar, answer in reference:
        result = backend.execute(operation, *values, scalar=scalar)
        np.testing.assert_array_equal(result["output"], answer)
        assert result["output_integrity_verified"] is True
        assert result["physical_execution"] is True
    assert backend.device_record()["integrated_gpu_verified"] is False
