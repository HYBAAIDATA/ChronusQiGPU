"""Migrated Geodesic/Tensor capability regression tests."""

from __future__ import annotations

import numpy as np
import pytest

from chronus.tensor.folded_inference import FoldedInferencePilot
from chronus.tensor.folded_state import ExactFoldState
from chronus.tensor.geodesic import (
    EnergyModel,
    GeodesicScheduler,
    HybridGPU,
    KernelLaunchConfig,
    MetricTensor,
    PhiGPU,
    PhiMemoryHierarchy,
    ProfiledHybridRouter,
    PhiTensorCore,
    TopologicalIntegrityGate,
)
from chronus.tensor.opencl_backend import OpenCLTensorBackend
from chronus.tensor.cuda_backend import CUDATensorBackend, CUDATensorUnavailable
from chronus.tensor.metal_backend import MetalTensorBackend, MetalTensorUnavailable


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
        assert record["known_answer_self_test"] == "PASS"
    else:
        assert backend.is_available() is False


def test_energy_model_uses_only_supplied_measurements():
    comparison = EnergyModel.compare(
        baseline_compute_joules=10.0,
        baseline_movement_joules=30.0,
        candidate_compute_joules=8.0,
        candidate_movement_joules=12.0,
    )
    assert comparison.baseline_joules == 40.0
    assert comparison.candidate_joules == 20.0
    assert comparison.reduction_fraction == pytest.approx(0.5)


def test_profiled_router_uses_only_verified_observations():
    router = ProfiledHybridRouter()
    router.record(operation="matmul", backend="opencl", size_class=1024, elapsed_ns=90, verified=False)
    router.record(operation="matmul", backend="numpy-reference", size_class=1024, elapsed_ns=120, verified=True)
    router.record(operation="matmul", backend="qualified-gpu", size_class=1024, elapsed_ns=80, verified=True)
    selected = router.select("matmul", 1024)
    assert selected["route"] == "qualified-gpu"
    assert selected["profiled"] is True
    assert router.select("matmul", 2048)["route"] == "numpy-reference"


def test_cuda_tensor_backend_is_real_or_fails_closed():
    backend = CUDATensorBackend()
    if backend.is_available():
        a = np.arange(6, dtype=np.float32).reshape(2, 3)
        b = np.arange(6, dtype=np.float32).reshape(2, 3)
        result = backend.execute("add", a, b)
        np.testing.assert_allclose(result["output"], a + b)
        assert result["physical_execution"] is True
        assert result["device"]["measured"] is False
        assert result["device"]["known_answer_self_test"] == "PASS"
    else:
        with pytest.raises(CUDATensorUnavailable):
            backend.execute("add", np.ones(2, dtype=np.float32), np.ones(2, dtype=np.float32))


def test_metal_tensor_backend_is_real_or_fails_closed():
    backend = MetalTensorBackend()
    if backend.is_available():
        a = np.arange(6, dtype=np.float32).reshape(2, 3)
        b = np.arange(6, dtype=np.float32).reshape(3, 2)
        result = backend.execute("matmul", a, b)
        np.testing.assert_allclose(result["output"], a @ b, rtol=1e-5, atol=1e-5)
        assert result["physical_execution"] is True
        assert result["device"]["measured"] is False
    else:
        with pytest.raises(MetalTensorUnavailable):
            backend.execute("add", np.ones(2, dtype=np.float32), np.ones(2, dtype=np.float32))


def test_live_mining_scheduler_dispatches_through_existing_geodesic_organs(monkeypatch):
    from chronus.execution.mining_scheduler import TuringMiningScheduler
    scheduler = TuringMiningScheduler(bytes(range(32)))
    # Full decode cannot satisfy this integration.
    monkeypatch.setattr(ExactFoldState, "unfold", lambda self: (_ for _ in ()).throw(AssertionError("full unfold")))
    for _ in range(3):
        order = scheduler.order(32)
        assert sorted(order) == list(range(32))
        evidence = scheduler.last_evidence["geodesic"]
        assert evidence["coverage"] == "exact_permutation"
        assert evidence["representation_bytes"] == evidence["source_bytes"]
        assert evidence["hashrate_multiplier"] is None
    def fail(*args, **kwargs):
        raise RuntimeError("scheduler failed")
    monkeypatch.setattr(scheduler.geodesic, "submit", fail)
    with pytest.raises(RuntimeError, match="scheduler failed"):
        scheduler.order(32)


def test_memory_tier_capacity_enforced_without_corrupting_existing_state():
    memory = PhiMemoryHierarchy(capacity_bytes={"sram": 8, "hbm": 16})
    value = np.arange(4, dtype=np.uint16)
    memory.store("first", value, "sram")
    with pytest.raises(MemoryError):
        memory.store("second", value, "sram")
    np.testing.assert_array_equal(memory.load("first", "sram"), value)
    memory.store("second", value, "hbm")
    with pytest.raises(MemoryError):
        memory.promote("second", "hbm", "sram")
    assert memory.telemetry()["resident_bytes"]["sram"] == 8
    assert memory.telemetry()["scope"] == "software_residency_not_physical_cache"


def test_folded_arrays_reject_process_local_object_pointers():
    with pytest.raises(ValueError):
        ExactFoldState.from_array(np.array([object()], dtype=object))
    with pytest.raises(ValueError):
        ExactFoldState.from_array(np.zeros(2, dtype=[("x", np.int32)]))


def test_archived_tensor_runtime_finite_numeric_guards_are_wired():
    core = PhiTensorCore()
    with pytest.raises(ValueError, match="finite numeric policy"):
        core.execute("add", np.array([float("nan")]), np.array([1.0]))
    with pytest.raises(ValueError, match="finite numeric policy"):
        core.execute("hadamard", np.array(["x"]), np.array(["y"]))
    with pytest.raises(ValueError, match="element budget"):
        core.execute("kron", np.ones(1001), np.ones(1000))
    with pytest.raises(ValueError, match="element budget"):
        core.execute("matmul", np.ones((1001, 2)), np.ones((2, 1000)))
    with pytest.raises(ValueError, match="scale must be finite"):
        core.execute("scale", np.array([1.0]), scalar=float("inf"))
    with pytest.raises(ValueError, match="output exceeds finite numeric policy"):
        core.execute("scale", np.array([1e308]), scalar=1e308)


def test_archived_tensor_guard_keeps_complex_reference_execution():
    core = PhiTensorCore()
    a = np.array([[1 + 1j, 2 - 2j]], dtype=np.complex128)
    b = np.array([[3 - 4j], [5 + 2j]], dtype=np.complex128)
    out = core.execute("matmul", a, b)
    np.testing.assert_array_equal(out["output"], a @ b)
    assert out["backend"] == "numpy-reference"
