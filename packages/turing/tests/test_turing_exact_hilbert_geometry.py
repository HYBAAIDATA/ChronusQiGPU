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


def test_interference_and_exact_reflection_are_first_class_turing_primitives():
    from turing.exact.geometry.operators import (
        InterferenceEngine, amplitude_amplification_step,
        inner_product, marked_reflection, reflect_about,
    )
    space = TensorHilbert((4,))
    # Rational exactly normalized state on 4 basis vectors.
    reference = SparseState(space,{i:ExactComplex(Fraction(1,2)) for i in range(4)})
    assert reference.normalized()
    flipped = marked_reflection(reference,{2})
    assert flipped.norm2() == 1
    assert flipped.amplitudes[2] == ExactComplex(Fraction(-1,2))
    result = amplitude_amplification_step(reference,reference,{2})
    assert result.norm2() == 1
    # For N=4, M=1, one Grover iteration places exact probability 1 at target.
    assert result.born_distribution() == {2:Fraction(1)}
    assert inner_product(reference,reference) == ExactComplex(1)
    assert reflect_about(reference,reference) == reference
    engine = InterferenceEngine(reference)
    assert engine.amplify(reference,{2}).born_distribution() == {2:Fraction(1)}
    with pytest.raises(ValueError):
        marked_reflection(reference,{4})
