"""Tests for surface code quantum error correction."""

import numpy as np
from quantum_compute_substrate.error_correction import SurfaceCodeQEC


class TestSurfaceCodeQEC:
    def test_initialization(self):
        qec = SurfaceCodeQEC(lattice_size=8)
        assert qec.L == 8
        assert qec.num_data_qubits == 64
        assert qec.code_distance == 8
        assert qec.max_correctable_errors == 3

    def test_no_error_no_syndrome(self):
        qec = SurfaceCodeQEC(lattice_size=8)
        state = np.ones(64, dtype=np.complex128)
        state = state / np.linalg.norm(state)
        syndrome = qec.measure_syndrome(state)
        assert not syndrome.detected
        assert syndrome.total_errors == 0

    def test_detect_bit_flip(self):
        qec = SurfaceCodeQEC(lattice_size=8)
        state = np.ones(64, dtype=np.complex128)
        state = state / np.linalg.norm(state)
        corrupted = qec.inject_bit_flip(state, [10])
        syndrome = qec.measure_syndrome(corrupted)
        assert syndrome.detected

    def test_correct_single_bit_flip(self):
        qec = SurfaceCodeQEC(lattice_size=8)
        state = np.ones(64, dtype=np.complex128)
        state = state / np.linalg.norm(state)
        corrupted = qec.inject_bit_flip(state, [10])
        corrected, syndrome, success = qec.correct_errors(corrupted)
        assert syndrome.detected
        assert success

    def test_correct_multiple_errors(self):
        """Code distance 8 can correct up to 3 errors."""
        qec = SurfaceCodeQEC(lattice_size=8)
        state = np.ones(64, dtype=np.complex128)
        state = state / np.linalg.norm(state)
        corrupted = qec.inject_bit_flip(state, [5, 20, 40])
        corrected, syndrome, success = qec.correct_errors(corrupted)
        assert success

    def test_error_correction_rate(self):
        qec = SurfaceCodeQEC(lattice_size=8)
        result = qec.test_error_correction(num_errors=1, num_trials=50)
        assert result["detection_rate"] == 1.0
        assert result["correction_rate"] == 1.0
        assert result["all_corrected"]

    def test_larger_lattice(self):
        qec = SurfaceCodeQEC(lattice_size=16)
        assert qec.max_correctable_errors == 7
        result = qec.test_error_correction(num_errors=3, num_trials=50)
        assert result["correction_rate"] > 0.9

    def test_compare_error_rates(self):
        results = SurfaceCodeQEC.compare_error_rates(
            noise_levels=[0.01, 0.05, 0.1],
            lattice_sizes=[4, 8],
        )
        assert len(results["results"]) == 6  # 3 noise levels * 2 lattice sizes
        for r in results["results"]:
            assert 0 <= r["correction_rate"] <= 1.0
