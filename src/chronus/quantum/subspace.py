"""Rank-2 symbolic search: no dense statevector, ever.

The uniform state, the marked indicator, and the phase iterate span a
2-dimensional invariant subspace, so the entire trajectory is parameterized
by the exact pair (a_marked, a_unmarked) — two field elements. This module
executes one-shot phase-matched search directly on that pair, and resolves
the marked set symbolically: membership is decided by oracle evaluation,
never by materializing 2**n amplitudes.

This pairs the primitives by their native roles: F_257 phase matching does
the search; the Zeckendorf/PV coordinate layer names states without storing
them.
"""

from dataclasses import dataclass

from chronus.quantum.metallic_search import one_shot_phases_multi
from chronus.quantum.statevector import INV_SQRT2, P


@dataclass(frozen=True)
class SubspaceState:
    """Exact state of the 2D invariant subspace; no 2**n array is allocated."""

    num_qubits: int
    marked_count: int
    marked_amplitude: int
    unmarked_amplitude: int

    def to_dict(self) -> dict:
        return {
            "num_qubits": self.num_qubits,
            "states": 1 << self.num_qubits,
            "marked_count": self.marked_count,
            "marked_amplitude": self.marked_amplitude,
            "unmarked_amplitude": self.unmarked_amplitude,
            "representation": "rank-2-symbolic",
        }


def uniform_subspace(num_qubits: int, marked_count: int) -> SubspaceState:
    """The prepared uniform state as a rank-2 pair."""
    if not isinstance(marked_count, int) or not 1 <= marked_count < (1 << num_qubits):
        raise ValueError("marked_count must be in [1, 2**num_qubits)")
    u = pow(INV_SQRT2, num_qubits, P)
    return SubspaceState(num_qubits, marked_count, u, u)


def subspace_iterate(state: SubspaceState, alpha: int, beta: int) -> SubspaceState:
    """One exact phase iterate on the pair (a_marked, a_unmarked).

    Derived from the dense operator exactly: the mean over N states is
    (r*a_marked + (N-r)*a_unmarked)/N, the oracle multiplies marked
    amplitudes by alpha, and diffusion maps a -> (1+beta)*mean - beta*a.
    """
    n = 1 << state.num_qubits
    r = state.marked_count
    marked = (alpha * state.marked_amplitude) % P
    mean = ((r * marked + (n - r) * state.unmarked_amplitude)
            * pow(n, -1, P)) % P
    return SubspaceState(
        state.num_qubits,
        r,
        ((1 + beta) * mean - beta * marked) % P,
        ((1 + beta) * mean - beta * state.unmarked_amplitude) % P,
    )


def exact_subspace_search(num_qubits: int, marked_count: int) -> SubspaceState:
    """One-shot phase-matched search in O(1) state: returns the converged pair.

    The converged state has marked amplitude +/-1 and unmarked amplitude 0;
    the marked SET membership of any basis index is then decided by the
    caller's oracle, one query per candidate, with no state table at all.
    """
    state = uniform_subspace(num_qubits, marked_count)
    alpha, beta = one_shot_phases_multi(num_qubits, marked_count)[0]
    result = subspace_iterate(state, alpha, beta)
    if result.unmarked_amplitude != 0 or result.marked_amplitude not in (1, P - 1):
        raise ArithmeticError("subspace search failed to converge")
    return result
