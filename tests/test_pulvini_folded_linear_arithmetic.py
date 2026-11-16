"""Direct full-state linear arithmetic; test complete kernels and source falsifiers."""
from __future__ import annotations

import numpy as np
import pytest

from chronus.tensor.folded_compute import FoldedTensorExecutor

pytestmark = pytest.mark.simulated


@pytest.mark.parametrize("depth", [0,1,2,4,8])
def test_addition_occurs_in_complete_fold_coordinates(depth):
    executor=FoldedTensorExecutor(depth=depth)
    left=np.arange(177,dtype=float)/13
    right=np.sin(np.arange(177,dtype=float))
    outcome=executor.execute_folded_linear(executor.fold(left),executor.fold(right))
    np.testing.assert_allclose(executor.materialise(outcome.operand),
                               left+right,rtol=1e-12,atol=1e-12)
    assert outcome.backend=="numpy-reference-folded-channels"
    assert outcome.operand.evidence.retained_bytes==(
        outcome.operand.evidence.folded_bytes+outcome.operand.evidence.kernel_bytes)
    assert outcome.physical_accelerator_measured is False


def test_scaled_complex_linear_combination_without_discarding_imaginary_data():
    executor=FoldedTensorExecutor(depth=3)
    x=np.linspace(0,1,55)+1j*np.linspace(1,2,55)
    y=np.linspace(4,5,55)-1j*np.linspace(3,2,55)
    result=executor.execute_folded_linear(executor.fold(x),executor.fold(y),
                                           alpha=2+3j,beta=-0.4+0.5j)
    np.testing.assert_allclose(executor.materialise(result.operand),
                               (2+3j)*x+(-0.4+0.5j)*y,
                               rtol=1e-12,atol=1e-12)
    assert result.operand.source_digest_authentication.endswith("NOT_SIGNED")


def test_invalid_original_geometry_fails_closed():
    executor=FoldedTensorExecutor(depth=2)
    with pytest.raises(ValueError,match="geometry"):
        executor.execute_folded_linear(executor.fold(np.ones(11)),
                                       executor.fold(np.ones(12)))


def test_mutated_source_kernel_does_not_enter_arithmetic():
    executor=FoldedTensorExecutor(depth=3)
    left=executor.fold(np.arange(32,dtype=float))
    right=executor.fold(np.ones(32,dtype=float))
    left.state.kernels[0][0] += 13
    with pytest.raises(ValueError,match="digest"):
        executor.execute_folded_linear(left,right)


@pytest.mark.parametrize("scalar",[float("inf"),float("nan"),"2",True])
def test_invalid_coefficients_rejected(scalar):
    executor=FoldedTensorExecutor(depth=2)
    left=executor.fold(np.ones(8,dtype=float))
    with pytest.raises(ValueError,match="scalar"):
        executor.execute_folded_linear(left,left,alpha=scalar)


def test_corrupted_final_size_fails_before_folded_arithmetic():
    from dataclasses import replace
    from chronus.tensor.folded_compute import VerifiedFoldedOperand

    executor=FoldedTensorExecutor(depth=1)
    left=executor.fold(np.arange(5,dtype=float))
    assert left.state.sizes == (5,3)
    broken=VerifiedFoldedOperand(replace(left.state,sizes=(5,2)),left.evidence)
    with pytest.raises(ValueError,match="chronology"):
        executor.execute_folded_linear(broken,broken)


def test_large_integer_scalar_cannot_round_before_composition():
    executor=FoldedTensorExecutor(depth=2)
    operand=executor.fold(np.arange(12,dtype=float))
    with pytest.raises(ValueError,match="exactly representable"):
        executor.execute_folded_linear(operand,operand,alpha=np.int64(2**53+1))


def test_extreme_scalar_beyond_float64_cannot_be_silently_cast():
    executor = FoldedTensorExecutor(depth=3)
    operand = executor.fold(np.ones(16, dtype=float))
    with pytest.raises(ValueError, match="scalar|canonical|representable"):
        executor.execute_folded_linear(operand, operand, alpha=float("inf"))
