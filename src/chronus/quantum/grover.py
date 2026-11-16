"""Finite-field Grover-shaped operator iteration over algebraic state vectors.

The oracle is an exact phase flip (multiply by -1 = 256 mod 257) and the
diffusion operator D = 2|s><s| - I is an exact Householder reflection over
the field. Every amplitude evolves by integer field arithmetic, so the full
Grover trajectory is exactly computable and checkable; over a finite field
there is no Born rule, so this verifies operator trajectories rather than
sampling outcomes.
"""

from chronus.quantum.statevector import P, StateVector


def oracle_flip(state: StateVector, marked: int) -> StateVector:
    """Phase-flip the marked basis state: a_marked -> -a_marked (mod 257)."""
    if not isinstance(marked, int) or not 0 <= marked < len(state.amplitudes):
        raise ValueError("marked index out of range")
    state.amplitudes[marked] = (P - state.amplitudes[marked]) % P
    return state


def diffusion(state: StateVector) -> StateVector:
    """Inversion about the mean: a_i -> 2*mu - a_i with mu the exact field mean."""
    n = len(state.amplitudes)
    inv_n = pow(n, -1, P)  # n is a power of two, always invertible mod 257
    mean = (sum(state.amplitudes) * inv_n) % P
    state.amplitudes = [(2 * mean - a) % P for a in state.amplitudes]
    return state


def grover_iterate(state: StateVector, marked: int) -> StateVector:
    """One exact Grover iteration: diffusion after oracle."""
    return diffusion(oracle_flip(state, marked))


def grover_trajectory(
    num_qubits: int, marked: int, iterations: int
) -> tuple[StateVector, list[list[int]]]:
    """Run exact Grover iterations, returning the final state and trajectory."""
    if not isinstance(iterations, int) or isinstance(iterations, bool) or iterations < 0:
        raise ValueError("iterations must be a non-negative integer")
    state = StateVector(num_qubits)
    for qubit in range(num_qubits):
        state.apply("H", qubit)
    trajectory = [list(state.amplitudes)]
    for _ in range(iterations):
        grover_iterate(state, marked)
        trajectory.append(list(state.amplitudes))
    return state, trajectory
