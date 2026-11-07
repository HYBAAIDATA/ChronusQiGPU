"""Exact finite-field quantum evolution tests — no floating point anywhere."""

import pytest

from chronus.quantum import I_UNIT, INV_SQRT2, OMEGA_8, P, SQRT2, StateVector


def test_field_constants_are_exact():
    assert SQRT2 * SQRT2 % P == 2
    assert INV_SQRT2 * SQRT2 % P == 1
    assert I_UNIT * I_UNIT % P == P - 1
    assert pow(OMEGA_8, 4, P) == P - 1 and pow(OMEGA_8, 8, P) == 1


def test_hadamard_is_exactly_involutive():
    state = StateVector(1).apply("H", 0)
    assert state.amplitudes == [INV_SQRT2, INV_SQRT2]
    state.apply("H", 0)
    assert state.amplitudes == [1, 0]  # H*H = I exactly in F_257


def test_bell_state_has_exact_amplitudes():
    state = StateVector(2).apply("H", 0).cnot(0, 1)
    assert state.amplitudes == [INV_SQRT2, 0, 0, INV_SQRT2]


def test_gate_algebra_identities():
    # S^2 = Z, T^2 = S, T^4 = Z, X^2 = I — exact over the field.
    s2 = StateVector(1).apply("S", 0).apply("S", 0)
    z = StateVector(1).apply("Z", 0)
    assert s2.equivalent(z)
    t2 = StateVector(1).apply("T", 0).apply("T", 0)
    s = StateVector(1).apply("S", 0)
    assert t2.equivalent(s)
    x2 = StateVector(1).apply("X", 0).apply("X", 0)
    assert x2.equivalent(StateVector(1))


def test_circuit_equivalence_detection():
    left = StateVector(2).apply("H", 0).cnot(0, 1)
    right = StateVector(2).apply("H", 0).cnot(0, 1)
    different = StateVector(2).apply("H", 0).cnot(0, 1).apply("Z", 1)
    assert left.equivalent(right)
    assert not left.equivalent(different)


def test_invalid_inputs_rejected():
    with pytest.raises(ValueError):
        StateVector(0)
    with pytest.raises(ValueError):
        StateVector(13)
    with pytest.raises(ValueError):
        StateVector(1, [1, 2, 3])
    with pytest.raises(ValueError):
        StateVector(1).apply("NOPE", 0)
    with pytest.raises(ValueError):
        StateVector(2).cnot(0, 0)
    with pytest.raises(TypeError):
        StateVector(1, [1.5, 0])
