"""Owner-controlled, fail-closed checks for the PULVINI V3 research seam."""
import dataclasses
import numpy as np
import pytest
from chronus.pulvini import PhiRecursiveOperator, ValidationError, fold_verified, unfold_verified


@pytest.mark.parametrize("depth", range(0, 9))
def test_reconstruction_and_retained_bytes(depth):
    original = np.random.default_rng(20260723).normal(size=10648)
    state, evidence = fold_verified(original, depth=depth)
    np.testing.assert_allclose(unfold_verified(state, receipt=evidence), original, rtol=0, atol=1e-12)
    assert evidence.reconstructed_within_tolerance
    assert evidence.relative_reconstruction_error <= 1e-12
    assert evidence.original_bytes == original.nbytes
    assert evidence.retained_bytes == evidence.folded_bytes + evidence.kernel_bytes
    assert evidence.retained_state_ratio == evidence.original_bytes / evidence.retained_bytes
    assert evidence.working_set_ratio == evidence.original_bytes / evidence.folded_bytes
    assert evidence.depth == depth
    if depth:
        assert evidence.retained_state_ratio < 1, "retained kernels must be counted"


@pytest.mark.parametrize("normalization", ["legacy", "orthonormal"])
def test_both_archive_normalizations_are_reversible(normalization):
    x = np.linspace(-10, 10, 256, dtype=np.float64)
    state, evidence = fold_verified(x, normalization=normalization, depth=4)
    assert evidence.normalization == normalization
    assert np.linalg.norm(unfold_verified(state, receipt=evidence)-x) / np.linalg.norm(x) <= 1e-12


def test_isometry_is_property_of_complete_orthonormal_state_not_folded_channel():
    rng = np.random.default_rng(23)
    x = rng.normal(size=64)
    op = PhiRecursiveOperator(normalization="orthonormal")
    state = op.fold_recursive(x, depth=4)
    complete_norm = np.linalg.norm(state.folded)**2 + sum(np.linalg.norm(k)**2 for k in state.kernels)
    np.testing.assert_allclose(complete_norm, np.linalg.norm(x)**2, atol=1e-12)
    assert np.linalg.norm(state.folded) < np.linalg.norm(x)


def test_adversarial_kernel_corruption_is_not_silent():
    x = np.linspace(0.2, 2.0, 100)
    state, evidence = fold_verified(x, depth=3)
    altered = state.kernels[0].copy()
    altered[0] += 0.125
    bad = dataclasses.replace(state, kernels=(altered,) + state.kernels[1:])
    with pytest.raises(ValidationError, match="digest mismatch"):
        unfold_verified(bad, receipt=evidence)


def test_no_tensor_or_mining_authority_mutation():
    state, evidence = fold_verified(np.array([[1.,2.],[3.,4.]]), depth=2)
    assert state.original_shape == (2,2)
    assert unfold_verified(state, receipt=evidence).shape == (2,2)
    assert not hasattr(evidence, "hashrate")
    assert not hasattr(evidence, "nonce")


@pytest.mark.parametrize("invalid", [np.array([]), np.array([np.nan]), np.array([np.inf])])
def test_untrusted_input_fails_closed(invalid):
    with pytest.raises(ValidationError):
        fold_verified(invalid)


@pytest.mark.parametrize("bad_depth", [-1, True, 33, 2.2])
def test_depth_limit_rejects_invalid(bad_depth):
    with pytest.raises(ValidationError):
        fold_verified(np.arange(20.), depth=bad_depth)

def test_missing_or_mismatched_receipt_fails_closed():
    x = np.arange(25.0)
    state, receipt = fold_verified(x, depth=3)
    with pytest.raises(TypeError):
        unfold_verified(state)
    wrong = dataclasses.replace(receipt, depth=2)
    with pytest.raises(ValidationError, match="metadata"):
        unfold_verified(state, receipt=wrong)
