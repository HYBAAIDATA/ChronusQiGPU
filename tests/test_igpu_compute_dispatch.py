"""Real mathematical dispatch and fail-closed optional Metal regressions.

These do not pretend that an Apple GPU exists in Linux CI. They verify
finite 32x600 arithmetic, asynchronous error propagation and TURING exact
operator routing. Actual Metal execution requires a physical macOS run.
"""
from fractions import Fraction
import platform

import numpy as np
import pytest

from chronus.compute import ComputeTask, iGPUDispatcher
from chronus.compute.quantum_evolution_igpu import iGPUQuantumEvolution
from chronus.geodesic.dual_120cell import build_dual_120_cell
from turing.exact.geometry.hilbert import (
    ExactComplex, SignedInvolution, SparseState, TensorHilbert,
)


def test_exact_19200_dual_laplacian_conservation_and_graph_response():
    dispatcher = iGPUDispatcher()
    dispatcher.start()
    try:
        rows = [[0] * 600 for _ in range(32)]
        rows[4][17] = 3
        result = dispatcher.submit_sync(
            ComputeTask("exact-h4", "exact-dual-laplacian", {"state": rows}))
        assert result["basis_dimension"] == 19200
        assert result["execution_classification"] == "MATHEMATICAL_EXECUTION_HOST"
        assert result["hardware_attested"] is False
        assert result["arithmetic"] == "EXACT_UNBOUNDED_INTEGER"
        assert result["state"][4][17] == 12
        neighbors = [j for a, b in build_dual_120_cell().edges
                     for j in ([b] if a == 17 else ([a] if b == 17 else []))]
        assert len(neighbors) == 4
        assert all(result["state"][4][j] == -3 for j in neighbors)
        assert sum(result["state"][4]) == 0
        assert sum(result["state"][3]) == 0
        stats = dispatcher.get_stats()
        assert stats["tasks_submitted"] == stats["tasks_completed"] == 1
        assert stats["metal_tasks"] == 0
    finally:
        dispatcher.stop()


def test_async_result_failure_propagation_and_duplicate_ids():
    dispatcher = iGPUDispatcher()
    dispatcher.start()
    try:
        good = ComputeTask("fail", "exact-dual-laplacian", {"state": [[1]]})
        dispatcher.submit(good)
        with pytest.raises(ValueError):
            dispatcher.result("fail", timeout=30)
        with pytest.raises(ValueError, match="duplicate"):
            dispatcher.submit(good)
        with pytest.raises(KeyError):
            dispatcher.result("missing")
        assert dispatcher.get_stats()["tasks_failed"] == 1
    finally:
        dispatcher.stop()


def test_no_silent_gpu_fallback_or_undocumented_precision():
    dispatcher = iGPUDispatcher(max_buffer_bytes=8192)
    dispatcher.start()
    try:
        with pytest.raises(ValueError, match="float32"):
            dispatcher.submit_sync(ComputeTask(
                "wrong-type", "metal-matmul",
                {"left": np.eye(2, dtype=np.float64),
                 "right": np.eye(2, dtype=np.float32)}))
        with pytest.raises(Exception, match="buffer"):
            dispatcher.submit_sync(ComputeTask(
                "too-large", "metal-matmul",
                {"left": np.ones((100,100),dtype=np.float32),
                 "right": np.ones((100,100),dtype=np.float32)}))
        if platform.system() != "Darwin":
            from chronus.tensor.metal_backend import MetalTensorUnavailable
            with pytest.raises(MetalTensorUnavailable):
                dispatcher.submit_sync(ComputeTask(
                    "absent-metal", "metal-matmul",
                    {"left": np.eye(2,dtype=np.float32),
                     "right": np.eye(2,dtype=np.float32)}))
    finally:
        dispatcher.stop()


def test_turing_exact_involution_and_interference_from_compute_facade():
    space = TensorHilbert((32,600))
    state = SparseState.basis(space, (0,0))
    operator = SignedInvolution(space, {0:(1,1),1:(0,1)})
    engine = iGPUQuantumEvolution()
    try:
        evolved = engine.evolve_exact(state,operator,1)
        assert evolved["state"].amplitudes == {1:ExactComplex(0,-1)}
        assert evolved["execution_classification"] == "MATHEMATICAL_EXECUTION_HOST"
        phased = engine.phase_exact(state,{0:ExactComplex(0,1)})
        assert phased["state"].amplitudes == {0:ExactComplex(0,1)}
        assert engine.inspect_probabilities(state) == {0:Fraction(1)}
        assert engine.performance_report()["stats"]["metal_tasks"] == 0
        assert engine.performance_report()["physical_device_attested"] is False
        assert evolved["state"].norm2() == 1
    finally:
        engine.shutdown()


def test_exact_interference_amplitude_amplification_known_oracle():
    space = TensorHilbert((4,))
    ref = SparseState(space, {i:ExactComplex(Fraction(1,2)) for i in range(4)})
    engine = iGPUQuantumEvolution()
    try:
        out = engine.amplify_exact(ref,ref,{2})
        assert out["state"].born_distribution() == {2:Fraction(1)}
        assert out["unknown_oracle_speedup_proven"] is False
    finally:
        engine.shutdown()
