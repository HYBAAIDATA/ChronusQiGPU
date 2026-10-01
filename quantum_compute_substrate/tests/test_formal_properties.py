"""Tests for runtime formal-property checks."""

from quantum_compute_substrate.formal_properties import (
    check_norm_preservation,
    check_phi_fibonacci_identity,
    check_grover_diffusion_reflection,
    check_fold_unfold_reconstruction,
    run_all_properties,
)


class TestFormalProperties:
    def test_phi_fibonacci_identity(self):
        assert check_phi_fibonacci_identity(n_max=30)

    def test_grover_diffusion_reflection(self):
        assert check_grover_diffusion_reflection(dim=32)

    def test_fold_unfold_reconstruction(self):
        assert check_fold_unfold_reconstruction(dim=128)

    def test_run_all_properties(self):
        results = run_all_properties()
        assert all(results.values())

    def test_norm_preservation_callable(self):
        # Identity operator preserves norm trivially
        ok, err = check_norm_preservation(lambda x: x, dim=32, trials=5)
        assert ok
