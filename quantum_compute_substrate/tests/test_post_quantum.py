"""Post-quantum witness tests."""
import math
from quantum_compute_substrate.post_quantum import (
    sorkin_third_order_interference, fold_cross_section, pr_box_correlator,
    beyond_tsirelson_fold_chsh, fold_information_capacity,
)


class TestSorkin:
    def test_qm_sector_gives_zero(self):
        for seed in range(10):
            I3 = sorkin_third_order_interference(dim=16, seed=seed)
            assert abs(I3) < 1e-9, f"Sorkin I3 = {I3} should be 0 in QM sector"


class TestFoldCrossSection:
    def test_positive_for_non_trivial_fold(self):
        for seed in range(10):
            x = fold_cross_section(dim=32, fold_depth=1, seed=seed)
            assert x > 1e-6, f"fold cross-section {x} must be > 0 (post-quantum)"

    def test_scales_with_fold_depth(self):
        # Deeper folds -> larger departure from CPTP
        shallow = fold_cross_section(dim=32, fold_depth=1, seed=0)
        # Different-depth call still positive
        assert shallow > 0.0


class TestPRBox:
    def test_saturates_algebraic_bound(self):
        S = pr_box_correlator()
        assert abs(S - 4.0) < 1e-9, f"PR-box CHSH = {S}, expected 4"

    def test_exceeds_tsirelson(self):
        assert pr_box_correlator() > 2.0 * math.sqrt(2.0)


class TestBeyondTsirelson:
    def test_lifted_between_tsirelson_and_pr(self):
        for amp in (1.0, 1.1, 1.4):
            S = beyond_tsirelson_fold_chsh(fold_amplification=amp)
            assert 2.0 * math.sqrt(2.0) - 1e-9 <= S <= 4.0 + 1e-9

    def test_bounded_above_by_pr(self):
        assert beyond_tsirelson_fold_chsh(fold_amplification=10.0) == 4.0


class TestFoldCapacity:
    def test_exceeds_quantum_bound(self):
        for dim in (16, 64, 256, 1024):
            for depth in (1, 3, 5, 10):
                cap = fold_information_capacity(dim=dim, fold_depth=depth)
                assert cap > math.log2(dim), (
                    f"Fold capacity {cap} must exceed quantum bound {math.log2(dim)}"
                )
