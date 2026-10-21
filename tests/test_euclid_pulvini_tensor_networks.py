from __future__ import annotations

import numpy as np
import pytest

from euclid.pythagoras.quantum.operators.matrix_product_operator import (
    IsingHamiltonianMPO,
    MPOPulviniTTHybrid,
)
from euclid.pythagoras.quantum.operators.pulvini_scaling import PulviniOperator
from euclid.pythagoras.quantum.operators.tensor_train import TensorTrain, TTPulviniHybrid
from euclid.pythagoras.quantum.topology.orchestrator import QuantumTopologyOrchestrator


def test_pulvini_fold_unfold_is_reversible_when_kernel_is_retained():
    rng = np.random.default_rng(7)
    operator = PulviniOperator(tolerance=1e-12)
    value = rng.normal(size=31)
    folded, kernel = operator.fold(value)
    restored = operator.unfold(folded, kernel, value.size)
    np.testing.assert_allclose(restored, value, rtol=0, atol=1e-12)
    assert operator.round_trip_error(value) < 1e-12


def test_hamiltonian_reduction_reports_measured_spectral_gap():
    # Diagonal low-energy sector: the first two eigenvalues remain in the
    # retained Phi-sized subspace, so the gap-preservation claim is testable.
    hamiltonian = np.diag([0.0, 2.0, 20.0, 30.0, 40.0])
    reduced, envelope = PulviniOperator(tolerance=1e-10).hamiltonian_reduction(hamiltonian)
    assert reduced.shape == (3, 3)
    assert envelope.is_reversible is False
    assert envelope.spectral_gap_delta < 1e-10
    assert envelope.topology_preserved is True


def test_hamiltonian_reduction_rejects_non_hermitian_input():
    with pytest.raises(ValueError, match="Hermitian"):
        PulviniOperator().hamiltonian_reduction(np.array([[0.0, 1.0], [0.0, 0.0]]))


def test_tensor_train_exact_round_trip():
    rng = np.random.default_rng(11)
    value = rng.normal(size=(3, 4, 2))
    tt = TensorTrain(value, tolerance=0)
    np.testing.assert_allclose(tt.reconstruct(), value, rtol=1e-10, atol=1e-10)
    assert tt.get_memory_bytes()["compressed"] > 0


def test_pulvini_tt_hybrid_reconstructs_original_with_complement():
    value = np.arange(12, dtype=float).reshape(3, 4)
    result = TTPulviniHybrid(max_tt_rank=64, tolerance=1e-10).process(value)
    np.testing.assert_allclose(result["reconstructed"], value, rtol=1e-10, atol=1e-10)
    assert result["reconstruction_error"] < 1e-10
    assert result["topology_preserved"] is True
    assert result["pulvini_kernel"].shape[0] == result["folded"].shape[0]


def test_ising_mpo_is_hermitian_and_applies_to_vector():
    mpo = IsingHamiltonianMPO(num_sites=2, coupling=1.0, field=0.5)
    matrix = mpo.to_full_matrix()
    assert matrix.shape == (4, 4)
    np.testing.assert_allclose(matrix, matrix.T, atol=1e-12)
    out = mpo.apply_to_vector(np.ones(4))
    assert out.shape == (4,)


def test_mpo_pulvini_hybrid_normalizes_evolution():
    # A one-site Ising MPO has dimension two; an original length-three vector
    # folds to two coordinates, exercising the actual fold -> MPO -> unfold path.
    value = np.array([1.0, 2.0, 3.0])
    result = MPOPulviniTTHybrid(tolerance=1e-10).process(
        value, mpo=IsingHamiltonianMPO(num_sites=1), num_time_steps=2
    )
    assert result["mpo_applied"] is True
    assert result["time_steps"] == 2
    assert np.isfinite(result["mpo_error"])
    assert np.isclose(np.linalg.norm(result["mpo_applied_state"]), 1.0)


def test_orchestrator_routes_only_large_workloads_to_pulvini():
    orchestrator = QuantumTopologyOrchestrator(large_dimension_threshold=10_000)
    small = orchestrator.plan((100,))
    large = orchestrator.plan((10_001,))
    assert small.mode == "direct"
    assert large.mode == "pulvini_tt_mpo"
    assert large.reason == "element_count_exceeds_threshold"
