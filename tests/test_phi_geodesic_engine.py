"""Tests for the ported Geodesic Tensor Engine components.

Plane map (per repo discipline):
  aethel.phi_fold / aethel.phi_memory   -- storage: numeric fold + tiers + gate
  kellogg.phi_tensor_core               -- tensor: folded ALU + metric tensor
  chronus.phi_gpu                       -- GPU: scheduler, PhiGPU, Hybrid, energy
"""

import numpy as np
import pytest

from aethel.phi_fold import (
    PHI,
    KernelBoundary,
    PhiFoldError,
    phi_fold,
    phi_unfold,
    reconstruction_error,
    unfold_partial,
    working_set_ratio,
)
from aethel.phi_memory import (
    MemoryHierarchyError,
    MemoryTier,
    PhiMemoryHierarchy,
    TopologicalIntegrityGate,
)
from chronus.phi_gpu import (
    EnergyModel,
    GeodesicScheduler,
    HybridGPU,
    KernelLaunchConfig,
    KernelTask,
    PhiGPU,
    PhiGPUError,
    phi_log_distance,
)
from kellogg.phi_tensor_core import MetricTensor, PhiTensorCore, TensorCoreError

# -- aethel.phi_fold -----------------------------------------------------------


def test_fold_unfold_roundtrip_is_exact():
    x = np.arange(1024, dtype=np.float64) * 0.5
    state = phi_fold(x, depth=4)
    np.testing.assert_array_equal(phi_unfold(state), x)
    assert reconstruction_error(x, state) == 0.0


def test_fold_depth3_working_set_ratio_near_phi3():
    x = np.arange(2048, dtype=np.float64)
    state = phi_fold(x, depth=3)
    ratio = working_set_ratio(state)
    # retained fraction ~phi^-3 -> ratio ~phi^3 = 4.236
    assert abs(ratio - PHI**3) / PHI**3 < 0.05


def test_fold_preserves_shape():
    x = np.arange(64, dtype=np.float64).reshape(8, 8)
    state = phi_fold(x, depth=2)
    assert state.original_shape == (8, 8)
    np.testing.assert_array_equal(phi_unfold(state), x)


def test_unfold_partial_returns_boundary_slice():
    x = np.arange(512, dtype=np.float64)
    state = phi_fold(x, depth=3)
    boundary = KernelBoundary(offset=10, length=25)
    np.testing.assert_array_equal(unfold_partial(state, boundary), x[10:35])


def test_fold_rejects_empty_and_bad_boundary():
    with pytest.raises(PhiFoldError):
        phi_fold(np.array([]), depth=1)
    state = phi_fold(np.arange(64.0), depth=1)
    with pytest.raises(PhiFoldError):
        unfold_partial(state, KernelBoundary(0, 10_000))


# -- aethel.phi_memory ----------------------------------------------------------


def test_memory_tiers_promote_demote_roundtrip():
    mem = PhiMemoryHierarchy()
    x = np.arange(256, dtype=np.float64)
    mem.store("block", x, MemoryTier.HBM)
    assert mem._residents["block"].state.depth == mem.hbm_max_depth
    np.testing.assert_array_equal(mem.read("block"), x)
    for expected_tier in (MemoryTier.L2, MemoryTier.SRAM, MemoryTier.REGISTER):
        resident = mem.promote("block")
        assert resident.tier == expected_tier
        np.testing.assert_array_equal(mem.read("block"), x)
    demoted = mem.demote("block")
    assert demoted.tier == MemoryTier.SRAM
    np.testing.assert_array_equal(mem.read("block"), x)


def test_memory_report_is_measured():
    mem = PhiMemoryHierarchy()
    mem.store("a", np.arange(128.0), MemoryTier.SRAM)
    report = mem.tier_report()
    assert report["SRAM"]["residents"] == 1
    assert report["SRAM"]["measured_ratio"] > 1.0
    with pytest.raises(MemoryHierarchyError):
        mem.read("missing")


def test_integrity_gate_pass_and_chronology_reject():
    gate = TopologicalIntegrityGate(tolerance=1e-9)
    x = np.arange(128.0)
    state = phi_fold(x, depth=2)
    v1 = gate.verify_fold("x", x, state)
    assert v1.passed
    verdict = gate.verify(
        op="replay",
        sequence=v1.sequence,  # replayed sequence -> chronology failure
        expected=np.zeros(4),
        actual=np.zeros(4),
        input_norm=1.0,
        output_norm=1.0,
    )
    assert not verdict.passed
    assert not verdict.chronology_ok
    assert gate.pass_rate < 1.0


# -- kellogg.phi_tensor_core -----------------------------------------------------


def _folded(x, depth=1):
    return phi_fold(np.asarray(x, dtype=np.float64), depth=depth)


def test_phi_tensor_core_fma_matches_numpy():
    core = PhiTensorCore()
    a = _folded(np.arange(64.0))
    b = _folded(np.arange(64.0) * 2.0)
    c = _folded(np.ones(64))
    result = core.fma(a, b, c)
    expected = np.arange(64.0) * np.arange(64.0) * 2.0 + 1.0
    np.testing.assert_allclose(phi_unfold(result), expected)
    assert core.op_log[-1].op == "fma"


def test_phi_tensor_core_fma_boundary():
    core = PhiTensorCore()
    a = _folded(np.arange(64.0))
    boundary = KernelBoundary(0, 8)
    result = core.fma(a, a, a, boundary)
    expected = np.arange(8.0) ** 2 + np.arange(8.0)
    np.testing.assert_allclose(phi_unfold(result), expected)


def test_phi_tensor_core_matmul():
    core = PhiTensorCore()
    a = _folded(np.eye(4))
    b = _folded(np.arange(16.0).reshape(4, 4))
    result = core.matmul(a, b)
    np.testing.assert_allclose(phi_unfold(result).reshape(4, 4), np.arange(16.0).reshape(4, 4))


def test_phi_tensor_core_reduce_and_shape_guard():
    core = PhiTensorCore()
    a = _folded(np.arange(10.0))
    assert core.reduce(a) == 45.0
    with pytest.raises(TensorCoreError):
        core.elementwise(a, lambda x: x[:3])  # shape must be preserved


def test_metric_tensor_factories_and_distance():
    euclid = MetricTensor.euclidean(3)
    assert euclid.distance([0, 0, 0], [3, 4, 0]) == pytest.approx(5.0)
    phi_metric = MetricTensor.phi_scaled(2)
    assert phi_metric.distance([0, 0], [1, 0]) == pytest.approx(1.0)
    hyper = MetricTensor.hyperbolic(2)
    # Poincare half-plane: distance at larger x_n is shorter
    assert hyper.distance([0, 1], [1, 1]) > hyper.distance([0, 4], [1, 4])
    stepped = euclid.geodesic_step([0, 0, 0], [1, 0, 0], 2.0)
    np.testing.assert_allclose(stepped, [2.0, 0, 0])
    walk = euclid.walk_manifold([0.0, 0.0, 0.0], 4, [0, 1, 0], 0.5)
    assert len(walk) == 4
    np.testing.assert_allclose(walk[-1], [0.0, 1.5, 0.0])


# -- chronus.phi_gpu -------------------------------------------------------------


def test_phi_log_distance_monotonic():
    assert phi_log_distance(0, 0) == 0.0
    assert phi_log_distance(1, 1) == 0.0
    assert phi_log_distance(1, PHI**4) == pytest.approx(4.0)
    assert phi_log_distance(3, 1) == phi_log_distance(1, 3)


def test_geodesic_scheduler_orders_by_proximity():
    mem = PhiMemoryHierarchy()
    mem.store("r", np.arange(64.0), MemoryTier.REGISTER)
    sched = GeodesicScheduler(mem)
    sched.submit(KernelTask("far", position=PHI**8, resident="r"), reference=0.0)
    sched.submit(KernelTask("near", position=2.0, resident="r"), reference=0.0)
    sched.submit(KernelTask("mid", position=PHI**4), reference=0.0)
    order = [t.name for t in sched.schedule()]
    assert order == ["near", "mid", "far"]


def test_phi_gpu_launch_kernel_matches_host():
    gpu = PhiGPU()
    x = np.arange(128.0)
    gpu.store("data", x)
    result = gpu.launch_kernel(
        KernelLaunchConfig(name="data", work_items=128, kernel=lambda s: s * 2.0)
    )
    np.testing.assert_allclose(result, x * 2.0)
    report = gpu.get_system_report()
    assert report["truth_class"] == "internal"
    assert report["integrity_pass_rate"] == 1.0
    assert gpu.launch_log[-1].cores_used == gpu.cores


def test_phi_gpu_rejects_unknown_resident():
    gpu = PhiGPU()
    with pytest.raises(PhiGPUError):
        gpu.launch_kernel(KernelLaunchConfig(name="ghost", work_items=4, kernel=lambda s: s))


def test_hybrid_gpu_routes_and_executes():
    hybrid = HybridGPU()
    assert hybrid.route_workload("vec", np.arange(64.0)) == "phi_native"
    assert hybrid.route_workload("small", np.array([1.0])) == "traditional"
    assert hybrid.route_workload("blob", {"not": "numeric"}) == "traditional"
    out = hybrid.execute("vec2", np.arange(64.0), lambda s: s + 1.0)
    np.testing.assert_allclose(out, np.arange(64.0) + 1.0)
    report = hybrid.get_hybrid_report()
    assert report["routes"]["phi_native"] >= 1
    assert report["routes"]["traditional"] >= 2


def test_energy_model_compare():
    model = EnergyModel()
    cmp = model.compare(elements=1000.0, working_set_ratio=4.236)
    assert cmp.savings_j > 0
    assert 0.0 < cmp.reduction_pct < 100.0
    assert cmp.movement_share_traditional == 0.80
    assert cmp.compute_share_phi == 0.95
    with pytest.raises(PhiGPUError):
        model.compare(elements=0.0)
