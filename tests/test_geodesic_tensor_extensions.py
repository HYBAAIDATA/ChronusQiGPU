from fractions import Fraction
import pytest
from python_backend.core_modules.geodesic_tensor_engine import ComputeUnitType, EnergyModel, HybridGPU, KernelBoundary, KernelLaunchConfig, MetricTensor, PhiGPU, fold_exact, unfold_partial


def test_true_partial_unfold_matches_reference_without_full_unfold(monkeypatch):
    values=tuple(Fraction(i,i+3) for i in range(1,65)); state=fold_exact(values,depth=8); expected=state.unfold()[11:29]
    def forbidden(_self): raise AssertionError("full unfold must not be called by unfold_partial")
    monkeypatch.setattr(type(state),"unfold",forbidden)
    assert unfold_partial(state,KernelBoundary(11,29))==expected


def test_partial_unfold_reports_bounded_source_reads():
    state=fold_exact(range(1024),depth=12); values,stats=state.unfold_partial_with_stats(KernelBoundary(100,116))
    assert values==tuple(Fraction(v) for v in range(100,116)); assert stats.requested_values==16
    assert stats.source_values_read<state.original_length; assert stats.reconstructed_fraction==pytest.approx(16/1024)


def test_virtual_gpu_fma_uses_partial_path():
    gpu=PhiGPU(num_cores=4,fold_depth=6); gpu.store("a",range(64)); gpu.store("b",[2]*64); gpu.store("c",[1]*64)
    report=gpu.launch_fma("a","b","c",KernelLaunchConfig(grid_dim=(4,1),fold_depth=6))
    assert report["result"].unfold()==tuple(Fraction(2*i+1) for i in range(64)); assert report["blocks"]==4
    assert report["hardware_accelerated"] is False; assert report["partial_source_values_read"]<4*64*3


def test_metric_factories_energy_and_hybrid_boundaries():
    flat=MetricTensor.euclidean(2); phi=MetricTensor.phi_scaled(2); hyper=MetricTensor.hyperbolic(2)
    assert flat.distance((0,0),(3,4))==pytest.approx(5.0); assert phi.distance((0,0),(3,4))<5.0; assert hyper.distance((0,0),(3,4))<5.0
    energy=EnergyModel().compare(flops=1000,bytes_moved=4096,slice_size=64,fold_depth=3,folded_bytes=1024)
    assert energy["truth_class"]=="declared_model" and energy["measured"] is False
    router=HybridGPU(structured_threshold=8); assert router.route_workload(range(16),True) is ComputeUnitType.PHI_NATIVE
    result=router.execute(range(16),is_structured=True,phi_executor=lambda:"phi",traditional_executor=lambda:"trad")
    assert result["result"]=="phi" and result["simulated"] is False
