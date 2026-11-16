"""Selectively reconstruct retained-kernel numerical fold without whole-array reads."""
from __future__ import annotations

import numpy as np
import pytest

from chronus.pulvini.partial import VerifiedFoldIndex
from chronus.tensor.folded_compute import FoldedTensorExecutor

pytestmark = pytest.mark.simulated


@pytest.mark.parametrize("size,depth", [
    (1,0), (2,1), (3,1), (11,3), (113,5), (10648,9), (10648,20),
])
def test_selected_inverse_matches_full_reconstruction(size, depth):
    original = np.arange(size, dtype=float)/7.
    executor = FoldedTensorExecutor(depth=depth)
    operand = executor.fold(original)
    index = VerifiedFoldIndex.compile(operand)
    whole = executor.materialise(operand)
    for start, stop in [
        (0, 1), (size//2, min(size,size//2+7)),
        (max(0,size-13),size), (0,size),
    ]:
        np.testing.assert_allclose(index.read(start,stop), whole[start:stop],
                                   atol=1e-12, rtol=1e-12)
    assert index.evidence()["per_read_full_unfold"] is False


def test_compiled_state_immutable_against_source_mutation():
    executor = FoldedTensorExecutor(depth=4)
    original = np.arange(144, dtype=float).reshape(12,12)
    operand = executor.fold(original)
    index = VerifiedFoldIndex.compile(operand)
    operand.state.kernels[0][0] += 100
    assert index.read(0,1)[0] == pytest.approx(original.reshape(-1)[0],abs=1e-12)
    np.testing.assert_allclose(index.read_rows(4,6),original[4:6],
                               atol=1e-12,rtol=1e-12)
    with pytest.raises(ValueError):
        index._state.kernels[0][0] = 45


@pytest.mark.parametrize("window", [(-1,2), (0,145), (3,2), (3.0,4)])
def test_invalid_windows_fail_closed(window):
    executor = FoldedTensorExecutor(depth=3)
    index = VerifiedFoldIndex.compile(executor.fold(np.arange(120,dtype=float)))
    with pytest.raises(ValueError):
        index.read(*window)


def test_complex_selective_reconstruction():
    executor = FoldedTensorExecutor(depth=4)
    original = (np.arange(99)+1j*np.linspace(0,1,99)).astype(np.complex128)
    index = VerifiedFoldIndex.compile(executor.fold(original))
    np.testing.assert_allclose(index.read(50,62),original[50:62],
                               rtol=1e-12,atol=1e-12)


def test_corrupt_final_fold_size_cannot_misroute_partial_reads():
    from dataclasses import replace
    from chronus.tensor.folded_compute import VerifiedFoldedOperand
    executor = FoldedTensorExecutor(depth=1)
    original = executor.fold(np.arange(5, dtype=float))
    assert original.state.sizes == (5, 3)
    corrupted = VerifiedFoldedOperand(
        replace(original.state, sizes=(5, 2)), original.evidence
    )
    with pytest.raises(ValueError, match="chronology"):
        VerifiedFoldIndex.compile(corrupted)


def test_compiled_inverse_requires_canonical_full_precision_dtype():
    from dataclasses import replace
    from chronus.tensor.folded_compute import VerifiedFoldedOperand
    executor = FoldedTensorExecutor(depth=1)
    operand = executor.fold(np.arange(13, dtype=float))
    state = replace(operand.state,
                    folded=operand.state.folded.astype(np.float32),
                    kernels=tuple(x.astype(np.float32) for x in operand.state.kernels))
    with pytest.raises(ValueError, match="canonical"):
        VerifiedFoldIndex.compile(VerifiedFoldedOperand(state, operand.evidence))
