"""phi^n scaling study tests."""

import math
from quantum_compute_substrate.post_quantum import AGIScale, AGI_SCALE_LEVELS

PHI = (1.0 + math.sqrt(5.0)) / 2.0


class TestAGIScaleLadder:
    def test_levels_are_10_12_15_18_20(self):
        assert AGI_SCALE_LEVELS == [10, 12, 15, 18, 20]

    def test_measure_point_10(self):
        pt = AGIScale(seed=0).measure_point(10)
        assert pt.dim == 123
        assert pt.F_n == 55 and pt.F_n_minus_1 == 34
        assert pt.phi_exact_residual < 1e-6
        assert pt.norm_preservation_residual < 1e-6
        assert pt.unitarity_residual < 1e-6

    def test_measure_point_12(self):
        pt = AGIScale(seed=0).measure_point(12)
        assert pt.dim == 322
        assert pt.F_n == 144 and pt.F_n_minus_1 == 89
        assert pt.norm_preservation_residual < 1e-6

    def test_measure_point_15(self):
        pt = AGIScale(seed=0).measure_point(15)
        assert pt.dim == 1364
        assert pt.F_n == 610 and pt.F_n_minus_1 == 377
        assert pt.norm_preservation_residual < 1e-6

    def test_measure_point_18(self):
        pt = AGIScale(seed=0).measure_point(18)
        assert pt.dim == 5778
        assert pt.F_n == 2584 and pt.F_n_minus_1 == 1597

    def test_measure_point_20(self):
        pt = AGIScale(seed=0).measure_point(20)
        assert pt.dim == 15127
        assert pt.F_n == 6765 and pt.F_n_minus_1 == 4181

    def test_compression_ratio_approaches_phi(self):
        # dense / fold ~ dim / F(n-1) -> phi as n grows
        pt = AGIScale(seed=0).measure_point(20)
        # compression ratio dim/F(n-1) ~ phi^{2}? actually dim ~ phi^n, F(n-1) ~ phi^{n-1}/sqrt5
        # so ratio ~ sqrt(5) * phi ~ 3.61
        assert 2.5 < pt.compression_ratio < 5.0

    def test_information_capacity_exceeds_quantum(self):
        pt = AGIScale(seed=0).measure_point(15)
        assert pt.information_capacity_bits > math.log2(pt.dim)

    def test_full_run_covers_all_levels(self):
        pts = AGIScale(seed=0).run_full_scale()
        assert [p.n for p in pts] == AGI_SCALE_LEVELS
        assert all(p.dim > 0 for p in pts)
        assert all(p.norm_preservation_residual < 1e-6 for p in pts)
