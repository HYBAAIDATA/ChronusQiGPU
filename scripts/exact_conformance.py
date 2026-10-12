"""Executable exact-register/tableau conformance for declared Clifford vectors.

LUCAS WIRING: assurance evidence, not operational or all-family certification.
All joint Born distributions are compared in local X/Y/Z bases. Branches are
conditioned explicitly on every outcome: no seed, sampling, float or tolerance.
This is scoped implementation conformance, not third-party institutional review.
"""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
import hashlib
from itertools import product
from pathlib import Path

# Fixed vectors cover phase, interference, correlations and entangling chains.
VECTORS = (
    ("basis", 1, (("x", 0),)),
    ("plus", 1, (("h", 0),)),
    ("phase", 1, (("h", 0), ("s", 0))),
    ("interference", 1, (("h", 0), ("s", 0), ("h", 0))),
    ("bell", 2, (("h", 0), ("cnot", 0, 1))),
    ("bell_phase", 2, (("h", 0), ("cnot", 0, 1), ("s", 1))),
    ("ghz", 3, (("h", 0), ("cnot", 0, 1), ("cnot", 0, 2))),
    ("chain", 4, (
        ("h", 0), ("h", 1), ("h", 2), ("h", 3),
        ("cnot", 0, 1), ("s", 1), ("cnot", 1, 2), ("cnot", 2, 3),
    )),
)


def _tableau_distribution(state):
    """Enumerate exact conditional branches, preserving their correlations."""
    pending = [(0, Fraction(1), state)]
    for q in range(state.n):
        following = []
        for index, weight, branch in pending:
            probabilities = branch.measurement_probabilities(q)
            if any(type(p) is not Fraction or p < 0 for p in probabilities):
                raise ArithmeticError("invalid exact tableau probability")
            if sum(probabilities) != 1:
                raise ArithmeticError("tableau distribution is not normalized")
            for bit, probability in enumerate(probabilities):
                if probability:
                    child = deepcopy(branch)
                    child.measure(q, outcome=bit)
                    child.validate_invariants()
                    following.append((index | (bit << q), weight * probability, child))
        pending = following
    return {index: weight for index, weight, _ in pending}


def _apply(register, tableau, operations):
    for operation in operations:
        gate, *qubits = operation
        getattr(register, f"apply_{gate}")(*qubits)
        getattr(tableau, gate)(*qubits)


def evaluate_conformance():
    """Run real independent arithmetic implementations; missing lanes raise."""
    from turing_universal_quantum_computer import hilbert, stabilizer

    checks = 0
    mismatches = []
    for name, width, operations in VECTORS:
        register = hilbert.QuantumRegister(width)
        tableau = stabilizer.StabilizerState.basis(width)
        _apply(register, tableau, operations)
        register.assert_normalized()
        tableau.validate_invariants()
        for axes in product("xyz", repeat=width):
            r, t = deepcopy(register), deepcopy(tableau)
            rotations = []
            for q, axis in enumerate(axes):
                if axis == "y":
                    rotations.extend([("s", q)] * 3)  # S-dagger before H
                if axis != "z":
                    rotations.append(("h", q))
            _apply(r, t, rotations)
            r.assert_normalized()
            t.validate_invariants()
            actual = _tableau_distribution(t)
            expected = r.distribution()
            checks += 1
            if sum(actual.values()) != 1 or any(
                expected.get(index, hilbert.QSqrt2()).to_sympy() != actual.get(index, 0)
                for index in range(1 << width)
            ):
                mismatches.append({"vector": name, "basis": "".join(axes)})
    return {
        "schema_version": 1,
        "scope": "finite_clifford_register_tableau_conformance_not_all_family_certification",
        "implementations": {
            "exact_register": hashlib.sha256(Path(hilbert.__file__).read_bytes()).hexdigest(),
            "clifford_tableau": hashlib.sha256(Path(stabilizer.__file__).read_bytes()).hexdigest(),
        },
        "vectors": len(VECTORS),
        "checks": checks,
        "mismatches": mismatches,
        "passed": len(VECTORS) == 8 and checks == 138 and not mismatches,
    }
