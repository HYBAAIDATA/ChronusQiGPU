"""Tests for scaling_study module."""
from quantum_compute_substrate.scaling_study import ScalingStudy


class TestScalingStudy:
    def test_phi_index_check_small_residuals(self):
        s = ScalingStudy()
        residuals = s.phi_index_check(k_max=30)
        max_res = max(r for _, r in residuals)
        assert max_res < 1e-6, f"Max phi-index residual {max_res} too large"

    def test_diffusion_scaling_produces_positive_exponents(self):
        s = ScalingStudy()
        res = s.diffusion_scaling(dims=[8, 16, 32, 64, 128, 256, 512])
        assert res.exponent_time > 0.0
        assert 0.0 <= res.r2_time <= 1.01
        assert len(res.dims) == len(res.times_s) == len(res.errors)

    def test_diffusion_scaling_error_bounded(self):
        s = ScalingStudy()
        res = s.diffusion_scaling(dims=[16, 32, 64, 128])
        assert max(res.errors) < 1e-6
