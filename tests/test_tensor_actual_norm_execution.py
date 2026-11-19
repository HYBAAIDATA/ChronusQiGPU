"""Independent local CPU contraction correctness tests (not GPU qualification)."""
import numpy as np
import pytest
from chronus.tensor.network import build_network
from chronus.tensor.enhanced_representation import (
    search_contraction_trees, plan_gpu_shards, execute_sharded_contraction,
    EnhancedTensorRepresentation,
)

pytestmark = pytest.mark.real

@pytest.mark.parametrize("n", [2,3,5])
def test_actual_norm_matches_independent_dense_contraction(n):
    net, _ = build_network(n, topology="MPS", chi_max=8)
    for i in range(n):
        node = net.node_for(i)
        block = node.tensor.blocks[(0,0,0)].copy()
        block[0,0,0] = complex(i+1, 0.25)
        block[0,1,0] = complex(0.5, i*0.1)
        node.tensor.blocks[(0,0,0)] = block
    raw = np.squeeze(net.node_for(0).tensor.to_dense(), axis=0)
    for i in range(1,n):
        raw = np.tensordot(raw, net.node_for(i).tensor.to_dense(), axes=(-1,0))
    reference = float(np.vdot(raw, raw).real)
    assert reference > 0
    for path in search_contraction_trees(net, 1 << 20):
        result = execute_sharded_contraction(plan_gpu_shards(net, ["cpu"], "replicate"), path, net)
        assert result["result_norm_squared"] == pytest.approx(reference, rel=1e-12)
        assert result["physical_gpu_claimed"] is False

def test_facade_executes_and_refuses_fictitious_gpu():
    cpu = EnhancedTensorRepresentation(dimensions=4, device="cpu")
    result = cpu.optimize_contraction({"operation":"norm"})
    assert result["status"] == "CONTRACTION_EXECUTED_CPU"
    assert result["result_norm_squared"] == pytest.approx(1.0)
    with pytest.raises(NotImplementedError):
        cpu.optimize_contraction({"operation":"unimplemented"})
    gpu = EnhancedTensorRepresentation(dimensions=4, device="cuda:0")
    with pytest.raises(NotImplementedError):
        gpu.optimize_contraction({"operation":"norm"})
