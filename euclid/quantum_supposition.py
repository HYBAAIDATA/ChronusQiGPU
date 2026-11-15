"""Exact quantum-mathematical supposition register for EUCLID research swarms.

Each *declared* hypothesis is a distinct orthonormal basis label. The
experiment prepares a uniform superposition with exact Hadamards, applies
an explicitly supplied phase oracle D, and applies Hadamards again:
    |psi> = H^(tensor n) D H^(tensor n) |0...0>
This is a finite-dimensional mathematical transformation, not a heuristic
confidence score, theorem verifier, quantum hardware call, or claim of speedup.
Oracle memberships are caller assertions and acquire no epistemic authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from turing_universal_quantum_computer.exact_state_vector import (
    ExactStateVector, H,
)

MAX_QUBITS = 8


@dataclass(frozen=True)
class Supposition:
    name: str
    proposition: str

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name or len(self.name) > 128:
            raise ValueError("bounded hypothesis name required")
        if not isinstance(self.proposition, str) or not self.proposition or len(self.proposition) > 2048:
            raise ValueError("bounded proposition required")


def _rational(value) -> str:
    if value.b == 0:
        return str(value.a)
    return f"({value.a})+({value.b})*sqrt(2)"


def exact_supposition_interference(
    suppositions: tuple[Supposition, ...],
    phase_flipped: frozenset[str],
) -> dict[str, object]:
    """Return mathematically exact amplitudes/probabilities for a phase oracle.

    The oracle predicate must come from separately validated task logic.
    A phase flip is neither a fact nor a posterior probability.
    """
    if not isinstance(suppositions, tuple) or not suppositions:
        raise ValueError("nonempty tuple of suppositions required")
    n = (len(suppositions) - 1).bit_length()
    if len(suppositions) != 1 << n or n < 1 or n > MAX_QUBITS:
        raise ValueError("exact register requires 2^n hypotheses, 1 <= n <= 8")
    if any(not isinstance(item, Supposition) for item in suppositions):
        raise TypeError("suppositions must be typed")
    names = [item.name for item in suppositions]
    if len(set(names)) != len(names):
        raise ValueError("hypothesis basis labels must be unique")
    if not isinstance(phase_flipped, frozenset) or not phase_flipped <= set(names):
        raise ValueError("phase oracle requires known hypothesis labels")

    state = ExactStateVector.basis(n)
    for bit in range(n):
        state = state.apply_single(bit, H)
    # D is exactly diagonal/unitary with eigenvalues +/- 1.
    amplitudes = tuple(-amp if name in phase_flipped else amp
                       for name, amp in zip(names, state.amplitudes))
    state = ExactStateVector(n, amplitudes)
    for bit in range(n):
        state = state.apply_single(bit, H)
    if not state.normalized_exact():
        raise ArithmeticError("nonunitary supposition transformation")

    probabilities = state.probabilities_exact()
    from turing_universal_quantum_computer.exact_state_vector import ONE
    if sum(probabilities, probabilities[0] - probabilities[0]) != ONE:
        raise ArithmeticError("Born probability normalization failed")
    manifest = {
        "basis": [
            {"index": index, "name": item.name, "proposition": item.proposition}
            for index, item in enumerate(suppositions)
        ],
        "phase_flipped": sorted(phase_flipped),
        "operator": "H^tensor(n) D_phase H^tensor(n)",
        "arithmetic": "exact Q(sqrt(2)) + iQ(sqrt(2))",
    }
    digest = hashlib.sha256(json.dumps(
        manifest, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    return {
        "schema": "euclid.quantum-supposition/v1",
        "manifest_sha256": digest,
        "hypotheses": [
            {"name": item.name, "basis_index": index,
             "born_probability_exact": _rational(probabilities[index])}
            for index, item in enumerate(suppositions)
        ],
        "normalization_exact": True,
        "oracle_evidence": "UNVERIFIED_CALLER_ASSERTION",
        "mathematical_model": "EXACT_UNITARY_HILBERT_EVOLUTION",
        "external_validation": "NOT_PERFORMED",
        "authority_granted": False,
        "hardware_execution": False,
        "quantum_advantage_claim": False,
    }
