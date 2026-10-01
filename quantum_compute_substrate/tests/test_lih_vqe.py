"""Tests for LiH VQE."""
from quantum_compute_substrate.applications.lih_vqe import LiHVQE


class TestLiHVQE:
    def test_run_returns_result_within_bound(self):
        res = LiHVQE().run(max_iters=300, seed=0)
        assert res.converged, f"LiH VQE did not converge: e={
            res.energy} exact={
            res.exact_reference}"

    def test_exact_reference_is_negative(self):
        vqe = LiHVQE()
        assert vqe.exact < 0.0
