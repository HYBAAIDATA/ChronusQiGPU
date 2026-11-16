"""Exact finite Hilbert basis, probabilities and involutory evolution tests."""
from fractions import Fraction

import pytest

from turing.exact.geometry.hilbert import (
    ExactComplex, I, SparseState, TensorHilbert,
    SignedInvolution, phase_injection,
)


def test_lazy_combined_tensor_basis_19200():
    h = TensorHilbert((32, 600))
    assert h.dimension == 19200
    assert h.index((31,599)) == 19199
    assert h.coordinates(19199) == (31,599)
    state = SparseState.basis(h, (10,120))
    assert len(state.amplitudes) == 1
    assert state.born_distribution() == {h.index((10,120)): Fraction(1)}
    assert state.expectation_diagonal({h.index((10,120)): Fraction(7,3)}) == Fraction(7,3)


def test_exact_tunneling_involution_and_four_phase_return():
    space = TensorHilbert((2,))
    state = SparseState.basis(space, (0,))
    tunneling = SignedInvolution(space, {0:(1,1),1:(0,1)})
    after = tunneling.quarter_turn(state)
    assert after.amplitudes == {1: -I}
    assert after.norm2() == Fraction(1)
    assert tunneling.quarter_turn(state, 2).amplitudes == {0: ExactComplex(-1)}
    assert tunneling.quarter_turn(state, 4) == state
    assert tunneling.transition_probability(state, 1) == Fraction(1)
    assert tunneling.transition_probability(state, 0) == Fraction(0)


def test_exact_phase_injection_and_hermitian_validation():
    space = TensorHilbert((2,))
    start = SparseState.basis(space, (0,))
    assert phase_injection(start, {0:I}).amplitudes == {0:I}
    with pytest.raises(ValueError):
        phase_injection(start, {0: ExactComplex(2)})
    with pytest.raises(ValueError):
        SignedInvolution(space, {0:(1,1)})
    with pytest.raises(ValueError):
        TensorHilbert((32,0))
