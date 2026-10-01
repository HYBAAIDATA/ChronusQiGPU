from __future__ import annotations

import numpy as np
import pytest

import aethel.phi_fold as phi_fold_module
from aethel import (
    KernelBoundary,
    MemoryTier,
    PhiMemoryHierarchy,
    TopologicalIntegrityGate,
    fold_result,
    phi_fold,
    phi_unfold,
    unfold_partial,
    unfold_partial_with_stats,
)
from chronus.gpu_reference import get_gpu_spec, list_available_gpus
from chronus.phi_gpu import (
    ComputeUnitType,
    GeodesicScheduler,
    HybridGPU,
    KernelLaunchConfig,
    KernelTask,
    PhiGPU,
)
from kellogg.phi_tensor_core import MetricTensor, PhiTensorCore, PrecisionMode
from tensor.backends.chronus_backend import ChronusBackend
from turing_universal_quantum_computer.property_invariants import InvariantTestSuite
from turing_universal_quantum_computer.quantum_algorithms import GroverSearch
from turing_universal_quantum_computer.trotter_simulation import TrotterHamiltonianSimulator


def test_selective_unfold_does_not_call_full_unfold(monkeypatch):
    original = np.arange(257, dtype=np.float64)
    state = phi_fold(original, depth=6)
    boundary = KernelBoundary(73, 19)

    def forbidden(_state):
        raise AssertionError("full phi_unfold must not be called by selective read")

    monkeypatch.setattr(phi_fold_module, "phi_unfold", forbidden)
    values, stats = unfold_partial_with_stats(state, boundary)
    assert np.array_equal(values, original[73:92])
    assert stats.source_values_read == 19
    assert stats.requested_values == 19
    assert stats.source_values_read < state.original_size


def test_selective_unfold_crosses_resident_segments_exactly():
    original = np.arange(144, dtype=np.float64)
    state = phi_fold(original, depth=5)
    # Choose a range that crosses at least one retained/complement boundary.
    start = max(0, state.retained_size - 3)
    boundary = KernelBoundary(start, 11)
    values, stats = unfold_partial_with_stats(state, boundary)
    assert np.array_equal(values, original[start:start + 11])
    assert stats.source_segments_touched >= 2


def test_fold_result_round_trip_updates_only_requested_slice():
    original = np.linspace(-2.0, 2.0, 128)
    state = phi_fold(original, depth=4)
    boundary = KernelBoundary(31, 7)
    replacement = np.arange(7, dtype=np.float64) + 100.0
    updated = fold_result(replacement, boundary, state)
    expected = original.copy()
    expected[31:38] = replacement
    assert np.array_equal(phi_unfold(updated), expected)
    assert updated.depth == state.depth


def test_memory_hierarchy_preserves_july_api_and_truth_boundary():
    memory = PhiMemoryHierarchy(hbm_max_depth=5)
    source = np.arange(128, dtype=np.float64)
    resident = memory.store("x", source, MemoryTier.HBM)
    assert memory.load("x", MemoryTier.HBM) is resident.state
    ratio = memory.get_working_set_ratio("x", MemoryTier.HBM)
    assert ratio > 1.0
    modeled = memory.get_effective_bandwidth("x", MemoryTier.HBM, 3.35)
    assert modeled == pytest.approx(3.35 * ratio)

    memory.promote("x", MemoryTier.SRAM)
    assert memory._residents["x"].tier == MemoryTier.SRAM
    assert np.array_equal(memory.read("x"), source)
    memory.demote("x", MemoryTier.HBM)
    assert memory._residents["x"].tier == MemoryTier.HBM
    assert np.array_equal(memory.read("x"), source)

    report = memory.get_memory_report()
    assert report["effective_bandwidth_is_hardware_measurement"] is False
    assert report["promotions"] >= 1
    assert report["demotions"] >= 1


def test_integrity_gate_roundtrip_and_metrics():
    gate = TopologicalIntegrityGate(tolerance=1e-12)
    result = gate.verify_roundtrip(np.linspace(0.0, 1.0, 64), depth=4)
    assert result["passed"] is True
    assert result["reconstruction_error"] <= 1e-12
    metrics = gate.get_metrics()
    assert metrics["checks_performed"] == 1
    assert metrics["checks_passed"] == 1
    assert metrics["checks_failed"] == 0


def test_kellogg_binary_elementwise_reduce_and_metrics():
    left = phi_fold(np.arange(16, dtype=np.float64), depth=2)
    right = phi_fold(np.ones(16, dtype=np.float64) * 2.0, depth=2)
    core = PhiTensorCore(result_depth=2, core_id=7, precision=PrecisionMode.FP32)

    added = core.elementwise(left, right, op=lambda a, b: a + b)
    assert np.array_equal(phi_unfold(added), np.arange(16, dtype=np.float64) + 2.0)
    total = core.reduce_sum(left)
    assert total == pytest.approx(float(np.arange(16).sum()))
    # Scalar reduction must settle at depth 0 rather than asking phi_fold to
    # fold a one-element result.
    assert core.last_metrics is not None
    assert core.last_metrics.result_depth == 0
    metrics = core.get_aggregate_metrics()
    assert metrics["total_operations"] == 2
    assert metrics["operations_by_type"]["elementwise"] == 1
    assert metrics["operations_by_type"]["reduce_sum"] == 1
    assert metrics["total_flops"] > 0


def test_metric_tensor_exposes_riemannian_surface():
    metric = MetricTensor.phi_scaled(3)
    assert metric.g_ij.shape == (3, 3)
    assert metric.distance([1, 1, 1], [2, 1, 1]) > 0
    step = metric.geodesic_step([1, 1, 1], [1, 0, 0], 0.25)
    assert step.shape == (3,)
    walk = metric.walk_manifold([1, 1, 1], 4, [1, 0, 0], 0.1)
    assert len(walk) == 4


def test_chronus_phi_gpu_launch_reads_only_boundary(monkeypatch):
    gpu = PhiGPU(cores=4)
    source = np.arange(128, dtype=np.float64)
    gpu.store("weights", source, MemoryTier.HBM)
    boundary = KernelBoundary(40, 16)

    # If launch_kernel regresses to a full Aethel read this fails immediately.
    def forbidden(_name):
        raise AssertionError("PhiGPU launch must not call full memory.read")

    monkeypatch.setattr(gpu.memory, "read", forbidden)
    result = gpu.launch_kernel(
        KernelLaunchConfig(
            name="weights",
            work_items=16,
            boundary=boundary,
            kernel=lambda x: x * 3.0,
        )
    )
    assert np.array_equal(result, source[40:56] * 3.0)
    assert gpu.launch_log[-1].boundary == (40, 16)
    assert gpu.launch_log[-1].integrity_passed is True


def test_geodesic_scheduler_preserves_modern_and_july_surfaces():
    scheduler = GeodesicScheduler(num_cores=2)
    scheduler.submit(KernelTask("far", 100.0), reference=1.0)
    scheduler.submit(KernelTask("near", 2.0), reference=1.0)
    batch = scheduler.schedule_batch(1)
    assert [task.name for task in batch] == ["near"]
    scheduler.mark_completed(batch[0], result="ok")
    assert batch[0].completed is True
    remaining = scheduler.schedule()
    assert [task.name for task in remaining] == ["far"]
    metrics = scheduler.get_metrics()
    assert metrics["completed_tasks"] == 1
    assert metrics["scheduling_decisions"] == 2


def test_hybrid_gpu_exposes_both_compute_unit_types():
    hybrid = HybridGPU(phi_gpu=PhiGPU(cores=3), traditional_units=2)
    kinds = [unit.unit_type for unit in hybrid.compute_units]
    assert kinds.count(ComputeUnitType.PHI_NATIVE) == 3
    assert kinds.count(ComputeUnitType.TRADITIONAL) == 2
    assert hybrid.route_workload("structured", np.arange(16, dtype=np.float64)) == "phi_native"
    assert hybrid.route_workload("irregular", {"x": 1}) == "traditional"


def test_july_gpu_reference_is_dated_reference_not_telemetry():
    assert "rubin_r100" in list_available_gpus()
    spec = get_gpu_spec("r100")
    assert spec.name == "NVIDIA Rubin R100"
    record = spec.as_dict()
    assert record["reference_date"] == "2026-07-24"
    assert record["measured_by_chronus"] is False


def test_current_chronus_physical_backend_declares_tensor_ops_fail_closed():
    backend = ChronusBackend()
    for operation in ("matmul", "add", "scale", "kron", "hadamard"):
        assert backend.supports(operation)
    assert not backend.supports("unknown-operation")


def test_completed_qsim_trotterization_retains_full_hilbert_dimension():
    h = np.array(
        [[1.0, 0.1, 0.0, 0.0], [0.1, 2.0, 0.2, 0.0],
         [0.0, 0.2, 3.0, 0.3], [0.0, 0.0, 0.3, 4.0]],
        dtype=complex,
    )
    qsim = TrotterHamiltonianSimulator(num_qubits=2, hamiltonian=h)
    propagator = qsim.improved_trotterization(0.05, trotter_order=2)
    assert propagator.shape == (4, 4)
    initial = np.array([1, 0, 0, 0], dtype=complex)
    result = qsim.adaptive_time_stepping(initial, target_time=0.2)
    assert result["total_time"] == pytest.approx(0.2)
    assert np.linalg.norm(result["final_state"]) == pytest.approx(1.0, abs=1e-8)


def test_completed_grover_and_cptp_fixes_remain_live():
    grover = GroverSearch(4)
    result = grover.run([1, 3])
    assert result["peak_success_probability"] > 0.0

    suite = InvariantTestSuite(tolerance=1e-10)
    suite.test_cptp(n_dim=4)
    assert len(suite.results) == 5
    assert all(record.passed for record in suite.results)
