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
