"""TURING-owned interference, oracle reflection and discrete tunneling.

All states and phase operations are exact Gaussian rationals. This module
executes finite-dimensional algebraic operators; it makes no claim of
physical quantum hardware, universal Hamiltonian exponentiation, faster
unknown-target discovery, or a measured quantum advantage.

A marked set supplied by the caller is a known oracle truth table, NOT a
solution to an unknown search. An unknown oracle must be evaluated and
its query cost accounted for externally.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Collection, Mapping

from turing.exact.geometry.hilbert import (
    ZERO, ExactComplex, SparseState,
    SignedInvolution, phase_injection,
)


def inner_product(reference: SparseState, state: SparseState) -> ExactComplex:
    """Exact conjugate-linear-first finite inner product."""
    if reference.space != state.space:
        raise ValueError("Hilbert factor mismatch")
    result = ZERO
    for k,z in reference.amplitudes.items():
        other = state.amplitudes.get(k,ZERO)
        result = result + z.conj() * other
    return result


def reflect_about(reference: SparseState, state: SparseState) -> SparseState:
    """Unitary reflection 2|r><r| - I, requiring normalized reference."""
    if reference.space != state.space:
        raise ValueError("Hilbert factor mismatch")
    if not reference.normalized():
        raise ValueError("reflection reference must be exactly normalized")
    amplitude = inner_product(reference,state) * 2
    out: dict[int,ExactComplex] = {}
    for k in reference.amplitudes.keys() | state.amplitudes.keys():
        z = amplitude * reference.amplitudes.get(k,ZERO) - state.amplitudes.get(k,ZERO)
        if z != ZERO:
            out[k] = z
    result = SparseState(state.space,out)
    if result.norm2() != state.norm2():
        raise ArithmeticError("reflection failed exact norm conservation")
    return result


def marked_reflection(state: SparseState, marked: Collection[int]) -> SparseState:
    """Diagonal phase oracle for an ALREADY KNOWN marked subset."""
    keys = set(marked)
    if any(type(k) is not int or not 0 <= k < state.space.dimension for k in keys):
        raise ValueError("marked basis index outside range")
    return phase_injection(state,{k:ExactComplex(-1) for k in keys})


def amplitude_amplification_step(reference: SparseState,
                                 state: SparseState,
                                 marked: Collection[int]) -> SparseState:
    """Exact Grover-like oracle + reflection when all inputs are supplied."""
    return reflect_about(reference,marked_reflection(state,marked))


@dataclass
class InterferenceEngine:
    """Reusable TURING state-operator scheduler; no invented observations."""
    state: SparseState

    def __post_init__(self):
        if not self.state.normalized():
            raise ValueError("engine requires unit-normalized exact state")

    def create_superposition(self, reference: SparseState) -> SparseState:
        """Replace state with an explicit, exactly normalized supplied state."""
        if reference.space != self.state.space or not reference.normalized():
            raise ValueError("superposition has mismatched space or norm")
        self.state = reference
        return self.state

    def apply_phase_gate(self, phases: Mapping[int, ExactComplex]) -> SparseState:
        self.state = phase_injection(self.state, phases)
        return self.state

    def tunnel(self, operator: SignedInvolution,
               quarter_turns: int = 1) -> SparseState:
        """Finite exactly computable evolutions exp(-i*pi*k*H/2), H^2=I."""
        self.state = operator.quarter_turn(self.state,quarter_turns)
        if not self.state.normalized():
            raise ArithmeticError("tunneling operator violated exact norm")
        return self.state

    def amplify(self, reference: SparseState,
                marked: Collection[int]) -> SparseState:
        self.state = amplitude_amplification_step(reference,self.state,marked)
        if not self.state.normalized():
            raise ArithmeticError("amplification step violated exact norm")
        return self.state

    def inspect_probabilities(self) -> dict[int,Fraction]:
        return self.state.born_distribution()
