"""Selective PULVINI fold tests against the unmodified formal inverse."""
import pytest
import numpy as np
from chronus.pulvini.formal import PhiRecursiveOperator, ValidationError
from chronus.tensor.pulvini_selective import unfold_partial_recursive


@pytest.mark.parametrize("normalization", ["orthonormal", "legacy"])
@pytest.mark.parametrize("length,depth", [(1, 0), (2, 1), (3, 2), (17, 7), (128, 4), (1000, 12)])
def test_selective_equals_full_for_real_input(normalization, length, depth):
    source = np.arange(length, dtype=np.float64) / 17.0
    op = PhiRecursiveOperator(normalization=normalization)
    state = op.fold_recursive(source, depth=depth)
    full = op.unfold_recursive(state)
    for start, stop in ((0, 0), (0, min(5, length)),
                        (length // 2, min(length, length // 2 + 3)),
                        (length - 1, length)):
        partial = unfold_partial_recursive(state, start, stop)
        np.testing.assert_allclose(partial.values, full[start:stop], rtol=0, atol=1e-12)
        assert partial.full_original_digest_verified is False
        assert partial.touched_folded_indices <= stop - start
        assert partial.touched_kernel_entries <= (stop - start) * state.depth


@pytest.mark.parametrize("normalization", ["orthonormal", "legacy"])
def test_complex_selective_against_full(normalization):
    source = np.exp(1j * np.arange(91, dtype=np.float64))
    op = PhiRecursiveOperator(normalization=normalization)
    state = op.fold_recursive(source, depth=8)
    partial = unfold_partial_recursive(state, 11, 29)
    np.testing.assert_allclose(
        partial.values, op.unfold_recursive(state).reshape(-1)[11:29], atol=1e-12
    )


def test_no_full_unfold_called(monkeypatch):
    op = PhiRecursiveOperator(normalization="orthonormal")
    state = op.fold_recursive(np.arange(250, dtype=np.float64), depth=8)
    def fail(*args, **kwargs):
        raise AssertionError("full unfolding forbidden")
    monkeypatch.setattr(PhiRecursiveOperator, "unfold_recursive", fail)
    result = unfold_partial_recursive(state, 3, 8)
    assert result.values.size == 5


def test_invalid_range_fails():
    state = PhiRecursiveOperator().fold_recursive(np.arange(10, dtype=np.float64), 3)
    for start, stop in ((-1, 1), (9, 11), (7, 5), (0, 65537)):
        with pytest.raises(ValidationError):
            unfold_partial_recursive(state, start, stop)
