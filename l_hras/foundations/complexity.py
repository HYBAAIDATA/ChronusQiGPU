"""D1 — Gottesman-Knill and the real complexity bound.

The consortium demand: simulating arbitrary quantum entanglement on
classical silicon requires exponential memory; the Gottesman-Knill
theorem restricts *efficient* classical simulation to stabilizer
circuits. Are the six intelligences Clifford-only? If not, what
tensor-network bound prevents blowup?

The honest answer, computed from the actual substrate
(:mod:`kellogg.exact_tensor`):

* The gate set is **Clifford+T** plus multi-controlled classical gates
  (CNOT, CZ, SWAP, controlled-U, Toffoli). ``T = diag(1, zeta_8)`` is
  not Clifford, so the set is *universal*: Gottesman-Knill does **not**
  apply. There is no polynomial-space claim to make.

* The substrate is a **dense state-vector** simulator: ``2^n``
  amplitudes in ``F4 = Q(sqrt(2)) + iQ(sqrt(2))``. Memory is
  ``O(2^n)`` amplitudes, each an unbounded ``Fraction`` quadruple —
  exact arithmetic additionally has unbounded coefficient growth under
  repeated multiplication (noted honestly, not papered over).

* There is **no tensor-network contraction bound** (no MPS/PEPS
  truncation). The ceiling is a declared, fail-closed resource cap:
  ``MLA1517_MAX_AMPLITUDES`` (default ``2**20`` = 20 qubits);
  ``ExactResourceError`` is raised rather than degrading to approximate
  arithmetic.

* What the six-intelligence pipeline *actually executes* is cheaper
  than even stabilizer simulation: each intelligence owns one
  computational-basis state, the joint is a plain tensor product, and
  the only measured observable is a ZZ parity per pair. That workload
  is classical correlation tracking — ``O(1)`` per party — and the
  honest report below says so rather than borrowing "entanglement"
  vocabulary for it.

``complexity_report`` is the machine-readable answer; the tests
exercise its claims.
"""

from __future__ import annotations

import os
from typing import Any

from .. import substrates

# Gates the substrate exposes, split by Clifford membership. Clifford
# gates are the normalizer of the Pauli group: {I, X, Y, Z, H, S, Sdg,
# CNOT, CZ, SWAP}. T, Tdg and Toffoli are outside it.
CLIFFORD_GATES: tuple[str, ...] = ("I", "X", "Y", "Z", "H", "S", "Sdg")
NON_CLIFFORD_GATES: tuple[str, ...] = ("T", "Tdg")
CLIFFORD_TWO_QUBIT: tuple[str, ...] = ("CNOT", "CZ", "SWAP")
NON_CLIFFORD_MULTI: tuple[str, ...] = ("TOFFOLI", "controlled-U")

# Operations the six-intelligence entanglement path actually invokes
# (l_hras.intelligences): per-party basis construction, the tensor
# product, and the ZZ-parity correlation. All of them act on
# computational-basis product states — a classical computation.
JOINT_PATH_OPS: tuple[str, ...] = (
    "exact_basis",
    "exact_tensor_product",
    "f4_correlations",
)

_DEFAULT_MAX_AMPLITUDES = 1 << 20


def amplitude_cap() -> int:
    """The enforced amplitude ceiling (exact state vectors refuse beyond it)."""
    return int(os.getenv("MLA1517_MAX_AMPLITUDES", str(_DEFAULT_MAX_AMPLITUDES)))


def max_qubits() -> int:
    """Largest n with 2^n amplitudes inside the configured cap."""
    cap = amplitude_cap()
    qubits = 0
    while (1 << (qubits + 1)) <= cap:
        qubits += 1
    return qubits


def gate_set_classification() -> dict[str, Any]:
    """Classify the exposed gate set; Clifford+T+Toffoli is universal."""
    return {
        "single_qubit": {
            "clifford": list(CLIFFORD_GATES),
            "non_clifford": list(NON_CLIFFORD_GATES),
        },
        "two_qubit": {
            "clifford": list(CLIFFORD_TWO_QUBIT),
            "non_clifford": ["controlled-U with non-Clifford gate"],
        },
        "three_qubit": {"non_clifford": list(NON_CLIFFORD_MULTI)},
        "is_clifford_only": False,
        "is_universal": True,
        "universal_witness": (
            "H + CNOT + T (Clifford+T) alone is universal for quantum "
            "computation; Toffoli adds classical universality"
        ),
        "gottesman_knill_applies": False,
        "field": "F4 = Q(sqrt(2)) + iQ(sqrt(2)) = Q(zeta_8)",
        "field_note": (
            "exact phases are the eighth roots of unity; off-grid angles "
            "raise NotInF4 rather than approximating"
        ),
    }


def joint_state_path() -> dict[str, Any]:
    """What the six-intelligence joint actually costs to execute.

    ``init_intelligence_subspace`` builds ``exact_basis(state_dim, k)``
    per party — a computational-basis state. ``build_full_entanglement_
    graph`` records pairs; ``f4_correlations`` reads a ZZ parity off each
    pair. None of these create superposition; the joint is a product
    state by construction.
    """
    return {
        "operations": list(JOINT_PATH_OPS),
        "states_constructed": "computational-basis states only",
        "superposition_created": False,
        "entanglement_created": False,
        "per_party_cost": "O(1) — one basis index",
        "joint_state": "product state (classical correlation)",
        "classically_simulable": True,
        "honest_label": (
            "the K6 'entanglement graph' is a co-occurrence/correlation "
            "graph over basis projections, not a quantum state"
        ),
    }


def memory_model(num_qubits: int) -> dict[str, Any]:
    """Dense state-vector memory: 2^n F4 amplitudes, unbounded Fractions."""
    amplitudes = 1 << num_qubits
    return {
        "num_qubits": num_qubits,
        "amplitudes": amplitudes,
        "scaling": "O(2^n) amplitudes — exponential in qubit count",
        "amplitude_type": "F4 = 4 Fractions each (unbounded integer growth)",
        "coefficient_growth": (
            "exact Fraction arithmetic can grow super-poly in gate depth; "
            "the cap bounds amplitudes, not coefficient size"
        ),
        "within_cap": amplitudes <= amplitude_cap(),
        "tensor_network_bound": None,
        "bound_type": "fail-closed resource cap (ExactResourceError), not MPS/PEPS",
    }


def verify_claims() -> dict[str, Any]:
    """Run the checks the report asserts. Returns only measured facts."""
    cap = amplitude_cap()
    results: dict[str, Any] = {}

    # 1. The cap is fail-closed at the substrate level.
    overshoot_qubits = max_qubits() + 1
    try:
        substrates.ExactStateVector.basis(overshoot_qubits, 0, max_amplitudes=cap)
        cap_enforced = False
    except Exception:
        cap_enforced = True
    results["cap_fail_closed"] = cap_enforced

    # 2. A basis state under a joint-path op stays a basis state (no
    #    superposition is ever created by the intelligence path).
    e0 = substrates.exact_basis(2, 0)
    e1 = substrates.exact_basis(2, 3)
    joint = substrates.exact_tensor_product([e0, e1])
    f4_zero = substrates.F4(0)
    f4_one = substrates.F4(1)
    amps = joint.amplitudes
    nonzero = [i for i, a in enumerate(amps) if a != f4_zero]
    results["joint_is_basis_product"] = len(nonzero) == 1 and amps[nonzero[0]] == f4_one
    results["joint_index"] = nonzero[0] if len(nonzero) == 1 else None

    # 3. ZZ parity of any basis pair is exactly ±1 in F4.
    from ..intelligences import INTELLIGENCES, init_intelligence_subspace

    class _Cfg:
        state_dim = 3

    projections = {name: init_intelligence_subspace(name, _Cfg()) for name in INTELLIGENCES}
    correlations = substrates.f4_correlations(
        {(a, b): True for a in projections for b in projections if a != b},
        projections,
        list(projections),
    )
    results["parities_exact"] = all(
        substrates.f4_to_float(v) in (-1.0, 1.0) for v in correlations.values()
    )

    return results


def complexity_report() -> dict[str, Any]:
    """The full D1 answer, machine-readable."""
    return {
        "question": (
            "Is the six-intelligence execution Clifford-only, or what "
            "tensor-network bound prevents exponential blowup?"
        ),
        "gate_set": gate_set_classification(),
        "joint_path": joint_state_path(),
        "memory": memory_model(min(max_qubits(), 20)),
        "resource_cap": {
            "env": "MLA1517_MAX_AMPLITUDES",
            "amplitudes": amplitude_cap(),
            "max_qubits": max_qubits(),
            "hard_limit": 62,
        },
        "verdict": (
            "No BQP=BPP violation is claimed or possible: the substrate is "
            "a bounded exact state-vector simulator over a universal gate "
            "set, fail-closed at 2^n amplitudes. The intelligence joint "
            "path never materializes a superposed state — it is classical "
            "correlation tracking by construction."
        ),
    }


__all__ = [
    "CLIFFORD_GATES",
    "NON_CLIFFORD_GATES",
    "CLIFFORD_TWO_QUBIT",
    "NON_CLIFFORD_MULTI",
    "JOINT_PATH_OPS",
    "amplitude_cap",
    "max_qubits",
    "gate_set_classification",
    "joint_state_path",
    "memory_model",
    "verify_claims",
    "complexity_report",
]
