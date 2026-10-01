"""Tests for scientific application kernels."""

import numpy as np
from quantum_compute_substrate.applications import (
    LHCEventClassifier,
    H2VQE,
    AdvectionKernel,
    QuantumSequenceAligner,
)


class TestParticlePhysics:
    def test_classifier_trains_and_predicts(self):
        clf = LHCEventClassifier(num_features=3)
        result = clf.demo(n_events=16)
        assert 0.0 <= result["accuracy"] <= 1.0
        assert result["n_test"] > 0

    def test_classifier_predict_requires_fit(self):
        clf = LHCEventClassifier(num_features=3)
        try:
            clf.predict(np.zeros((1, 3)))
            raised = False
        except RuntimeError:
            raised = True
        assert raised, "predict() before fit() should raise RuntimeError"


class TestQuantumChemistry:
    def test_h2_vqe_converges(self):
        vqe = H2VQE()
        result = vqe.solve(max_iterations=200, learning_rate=0.05)
        # Should reach within a few tenths of a Hartree of exact value
        assert result["error_ha"] < 0.5

    def test_h2_hamiltonian_is_hermitian(self):
        vqe = H2VQE()
        H = vqe.hamiltonian
        assert np.allclose(H, H.conj().T)


class TestClimate:
    def test_advection_conserves_l2_norm(self):
        ak = AdvectionKernel(nx=64)
        x = np.linspace(0, 2 * np.pi, 64, endpoint=False)
        u0 = np.sin(x)
        u1 = ak.step(u0, dt=0.1)
        assert abs(np.linalg.norm(u1) - np.linalg.norm(u0)) < 1e-9

    def test_advection_demo_low_error(self):
        ak = AdvectionKernel(nx=64)
        result = ak.demo()
        assert result["l2_relative_error"] < 0.2


class TestGenomics:
    def test_smith_waterman_score_non_negative(self):
        aligner = QuantumSequenceAligner()
        result = aligner.align("ACACACTA", "AGCACACA")
        assert result["score"] > 0

    def test_identical_sequences_align_well(self):
        aligner = QuantumSequenceAligner()
        result = aligner.align("AAAA", "AAAA")
        assert result["score"] == 8  # 4 matches * 2
