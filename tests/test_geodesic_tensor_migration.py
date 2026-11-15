"""Migrated Geodesic/Tensor capability regression tests."""

from __future__ import annotations

import numpy as np
import pytest

from chronus.tensor.folded_inference import FoldedInferencePilot
from chronus.tensor.folded_state import ExactFoldState
from chronus.tensor.geodesic import (
    GeodesicScheduler,
    HybridGPU,
    KernelLaunchConfig,
    MetricTensor,
    PhiGPU,
    PhiMemoryHierarchy,
    PhiTensorCore,
    TopologicalIntegrityGate,
)
from chronus.tensor.opencl_backend import OpenCLTensorBackend


def test_selective_unfold_never_calls_full_unfold(monkeypatch):
    source = np.arange(48, dtype=np.float32).reshape(8, 6)
    state = ExactFoldState.from_array(source)
    monkeypatch.setattr(ExactFoldState, "unfold", lambda self: (_ for _ in ()).throw(AssertionError("full unfold called")))
    actual = state.unfold_rows(2, 5)
    np.testing.assert_array_equal(actual, source[2:5])


def test_core_rectangular_matmul_and_complex_dtype():
    core = PhiTensorCore()
    a = np.array([[1 + 2j, 2 - 1j, 3 + 0j], [4 + 1j, 5 + 0j, 6 - 2j]])
    b = np.array([[1 - 1j, 2], [3, 4 + 1j], [5, 6]])
    result = core.execute("matmul", a, b)["output"]
    np.testing.assert_allclose(result, a @ b)


def test_memory_hierarchy_preserves_dtype_and_partial_rows():
    memory = PhiMemoryHierarchy()
    value = (np.arange(24).reshape(4, 6) + 1j).astype(np.complex64)
    state = memory.store("weights", value, "hbm")
    assert state.dtype == value.dtype.str
    np.testing.assert_array_equal(memory.load_rows("weights", 1, 3), value[1:3])
    memory.promote("weights", "hbm", "l2")
    np.testing.assert_array_equal(memory.load("weights", "l2"), value)


def test_integrity_gate_checks_operation_output_not_only_representation():
    gate = TopologicalIntegrityGate(tolerance=1e-12)
    expected = np.array([1.0, 2.0])
    assert gate.verify(expected.copy(), expected).passed is True
    assert gate.verify(np.array([1.0, 2.1]), expected).passed is False


def test_scheduler_selected_task_controls_execution_order():
    scheduler = GeodesicScheduler()
    scheduler.submit("far", distance=10.0)
    scheduler.submit("near", distance=1.0)
    assert scheduler.pop() == "near"
    assert scheduler.pop() == "far"


def test_metric_tensor_walk_and_distance():
    metric = MetricTensor.euclidean(2)
    a, b = np.array([0.0, 0.0]), np.array([3.0, 4.0])
    assert metric.distance(a, b) == pytest.approx(5.0)
    walk = metric.walk_manifold(a, b, 4)
    np.testing.assert_allclose(walk[2], np.array([1.5, 2.0]))


def test_phigpu_launch_uses_declared_operations():
    gpu = PhiGPU(num_cores=2)
    a, b = np.ones((2, 2)), np.full((2, 2), 2.0)
    results = gpu.launch_kernel([
        (KernelLaunchConfig("add", distance=2.0), (a, b), {}),
        (KernelLaunchConfig("hadamard", distance=1.0), (a, b), {}),
    ])
    assert results[0]["operation"] == "hadamard"
    np.testing.assert_allclose(results[0]["output"], a * b)
    assert gpu.get_system_report()["physical_accelerator_measured"] is False


def test_hybrid_gpu_fails_closed_when_accelerator_required_and_absent():
    router = HybridGPU(accelerator=None)
    assert router.route_workload("matmul")["route"] == "numpy-reference"
    with pytest.raises(RuntimeError):
        router.route_workload("matmul", require_accelerator=True)


def test_folded_inference_materialises_only_selected_rows():
    weights = np.arange(30, dtype=np.float32).reshape(5, 6)
    pilot = FoldedInferencePilot(weights)
    vector = np.ones(6, dtype=np.float32)
    result = pilot.execute_rows(1, 3, vector)
    np.testing.assert_allclose(result["output"], weights[1:3] @ vector)
    assert result["bytes_materialised"] == weights[1:3].nbytes
    assert result["bytes_materialised"] < result["total_weight_bytes"]
    assert result["physical_compression_ratio"] is None


def test_opencl_tensor_backend_never_claims_cpu_fallback():
    backend = OpenCLTensorBackend()
    if backend.is_available():
        record = backend.device_record()
        assert record["execution_mode"] == "PHYSICAL_ACCELERATOR"
        assert record["measured"] is False
    else:
        assert backend.is_available() is False
