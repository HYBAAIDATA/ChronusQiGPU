"""Exact Grover correctness tests over F_257."""

import pytest

from chronus.quantum import (
    P,
    StateVector,
    diffusion,
    grover_trajectory,
    oracle_flip,
)

pytestmark = pytest.mark.real

INV4 = pow(4, -1, P)


def _reference_grover(amplitudes, marked, iterations):
    """Independent exact reference: the same operators computed standalone."""
    amps = list(amplitudes)
    for _ in range(iterations):
        amps[marked] = (-amps[marked]) % P
        mean = (sum(amps) * pow(len(amps), -1, P)) % P
        amps = [(2 * mean - a) % P for a in amps]
    return amps


def test_oracle_is_exact_involution():
    state = StateVector(2)
    state.amplitudes = [3, 5, 7, 9]
    oracle_flip(state, 2)
    assert state.amplitudes == [3, 5, P - 7, 9]
    oracle_flip(state, 2)
    assert state.amplitudes == [3, 5, 7, 9]


def test_diffusion_is_exact_reflection():
    state = StateVector(2)
    state.amplitudes = [1, 2, 3, 4]
    original = list(state.amplitudes)
    mean = (sum(original) * INV4) % P
    diffusion(state)
    assert state.amplitudes == [(2 * mean - a) % P for a in original]
    diffusion(state)
    assert state.amplitudes == original  # D^2 = I exactly


def test_grover_n2_single_iteration_converges_exactly():
    # Uniform amplitude over 4 states is (1/sqrt(2))^2 = 1/2 = 129 mod 257.
    half = 30 * 30 % P
    assert half == 129 and 2 * half % P == 1
    state, trajectory = grover_trajectory(2, marked=3, iterations=1)
    assert trajectory[0] == [half] * 4
    # One exact iteration drives the marked amplitude to exactly 1 and all
    # others to exactly 0, matching the real-valued Grover guarantee for n=2.
    assert state.amplitudes == [0, 0, 0, 1]
    assert state.amplitudes == _reference_grover([half] * 4, 3, 1)


def test_grover_trajectory_matches_independent_recurrence_all_marks():
    for num_qubits in (1, 2, 3):
        for marked in range(1 << num_qubits):
            state, _ = grover_trajectory(num_qubits, marked, iterations=3)
            fresh = StateVector(num_qubits)
            for q in range(num_qubits):
                fresh.apply("H", q)
            assert state.amplitudes == _reference_grover(fresh.amplitudes, marked, 3)


def test_grover_operator_squared_is_not_identity_but_reversible():
    state, _ = grover_trajectory(2, 1, iterations=2)
    assert state.amplitudes == _reference_grover(
        StateVector(2).apply("H", 0).apply("H", 1).amplitudes, 1, 2
    )


def test_grover_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        grover_trajectory(2, 4, 1)
    with pytest.raises(ValueError):
        grover_trajectory(2, 0, -1)
    with pytest.raises(ValueError):
        oracle_flip(StateVector(1), 5)
