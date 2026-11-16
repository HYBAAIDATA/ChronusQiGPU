"""July HERMES FoldState contract recovery over the maintained tensor core."""
from __future__ import annotations

import numpy as np
import pytest

from chronus.tensor.folded_compute import FoldedTensorExecutor

pytestmark = pytest.mark.simulated


@pytest.fixture
def executor():
    return FoldedTensorExecutor(depth=3)


@pytest.mark.parametrize("operation,count", [
    ("add", 2), ("hadamard", 2), ("fma", 3),
    ("scale", 1), ("matmul", 2), ("reduce_sum", 1),
])
def test_archived_hermes_operations_remain_executable(executor, operation, count):
    data = np.array([[.5, 1.5], [2.25, -3.0]], dtype=np.float64)
    operands = [executor.fold(data) for _ in range(count)]
    result = executor.execute(operation, *operands, scalar=3 if operation == "scale" else None)
    assert result.backend == "numpy-reference"
    assert result.numerical_output_verified is True
    m = result.public_metrics()
    assert m["total_retained_bytes"] == m["active_folded_bytes"] + m["kernel_bytes"]
    target = {
        "add": data+data, "hadamard": data*data, "fma": data*data+data,
        "scale": data*3, "matmul": data@data, "reduce_sum": data.sum(),
    }[operation]
    np.testing.assert_allclose(executor.materialise(result.operand), target,
                               rtol=1e-12, atol=1e-12)


def test_window_update_does_not_modify_source(executor):
    value = np.arange(14, dtype=np.float64).reshape(2, 7)
    operand = executor.fold(value)
    result = executor.update_window(operand, np.array([21.,31.,41.]), start=3, stop=6)
    expected = value.copy().reshape(-1)
    expected[3:6] = [21,31,41]
    np.testing.assert_allclose(executor.materialise(result.operand).reshape(-1),
                               expected, rtol=1e-12, atol=1e-12)
    np.testing.assert_allclose(executor.materialise(operand), value, rtol=1e-12, atol=1e-12)
    assert result.whole_state_materialised is True


def test_kernel_corruption_fails_closed(executor):
    operand = executor.fold(np.array([1.,2.,3.,4.,5.]))
    operand.state.kernels[0][0] += 12
    with pytest.raises(ValueError):
        executor.materialise(operand)


@pytest.mark.parametrize("count", [0, 1, 3, 4])
def test_bad_operand_count_rejected(executor, count):
    operands = [executor.fold(np.ones((2,2))) for _ in range(count)]
    with pytest.raises(ValueError, match="wrong folded operand count"):
        executor.execute("add", *operands)


def test_no_false_gpu_fused_or_storage_qualification(executor):
    operand = executor.fold(np.array([10.,20.,30.,40.]))
    m = executor.execute("hadamard", operand, operand).public_metrics()
    assert m["physical_accelerator_measured"] is False
    assert m["net_storage_savings_measured"] is False
    assert m["fused_hardware_instruction"] is False
