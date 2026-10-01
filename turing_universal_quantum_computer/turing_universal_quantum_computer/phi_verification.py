"""Independent-style evidence gates for the consolidated Turing phi machine.

The original July GHZ shot-correlation check is retained only as a diagnostic.
Production verification operates on the stabilizer group itself. Equivalent
stabilizer states may use different generator bases, so this module performs
GF(2) group-membership reduction including Pauli phase rather than comparing
raw tableau rows.
"""
from __future__ import annotations

import hashlib
import json

from .phi_quantum_machine import PhiQuantumCircuit, PhiQuantumMachine1000
from .stabilizer import StabilizerState


def _pauli_product(
    x1: int, z1: int, r1: int, x2: int, z2: int, r2: int
) -> tuple[int, int, int]:
    """Multiply two commuting Hermitian Pauli rows using the CHP phase rule."""
    g = StabilizerState._gsum(x1, z1, x2, z2)
    phase = (2 * int(bool(r1)) + 2 * int(bool(r2)) + g) % 4
    if phase not in (0, 2):
        raise ValueError("non-commuting/imaginary Pauli product at stabilizer boundary")
    return x1 ^ x2, z1 ^ z2, phase // 2


def _stabilizer_basis(state: StabilizerState) -> dict[int, tuple[int, int, int]]:
    """Build one echelon basis for the state's n stabilizer generators."""
    n = state.n
    basis: dict[int, tuple[int, int, int]] = {}
    for index in range(n, 2 * n):
        x = int(state._x[index])
        z = int(state._z[index])
        r = int(bool(state._r[index]))
        vector = x | (z << n)
        while vector:
            pivot = vector.bit_length() - 1
            row = basis.get(pivot)
            if row is None:
                basis[pivot] = (x, z, r)
                break
            x, z, r = _pauli_product(x, z, r, *row)
            vector = x | (z << n)
        else:
            if r:
                raise ValueError("stabilizer generators contain -I or are phase-inconsistent")
    if len(basis) != n:
        raise ValueError(f"stabilizer rank {len(basis)} != logical qubits {n}")
    return basis


def _contains_with_basis(
    n: int,
    basis: dict[int, tuple[int, int, int]],
    x: int,
    z: int,
    r: int = 0,
) -> bool:
    if x < 0 or z < 0 or x >> n or z >> n or r not in (0, 1):
        return False
    vector = x | (z << n)
    phase = int(r)
    while vector:
        pivot = vector.bit_length() - 1
        row = basis.get(pivot)
        if row is None:
            return False
        x, z, phase = _pauli_product(x, z, phase, *row)
        vector = x | (z << n)
    return phase == 0


def stabilizer_contains(state: StabilizerState, x: int, z: int, r: int = 0) -> bool:
    """Return True iff the signed Pauli belongs to the state's stabilizer group."""
    basis = _stabilizer_basis(state)
    return _contains_with_basis(state.n, basis, x, z, r)


def ghz_expected_generators(n_qubits: int) -> tuple[tuple[int, int, int], ...]:
    if n_qubits < 1:
        raise ValueError("n_qubits must be positive")
    generators = [((1 << n_qubits) - 1, 0, 0)]
    for q in range(1, n_qubits):
        generators.append((0, (1 << (q - 1)) | (1 << q), 0))
    return tuple(generators)


def verify_ghz_stabilizer_group(state: StabilizerState) -> dict[str, object]:
    expected = ghz_expected_generators(state.n)
    basis = _stabilizer_basis(state)
    membership = tuple(
        _contains_with_basis(state.n, basis, *generator) for generator in expected
    )
    witness = hashlib.sha256(
        json.dumps(expected, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "logical_qubits": state.n,
        "expected_generators": len(expected),
        "verified_generators": sum(membership),
        "all_generators_verified": all(membership),
        "witness_digest": witness,
        "verification_method": "basis-invariant signed-Pauli stabilizer membership",
    }


def run_1000_qubit_verification(shots: int = 32) -> dict[str, object]:
    """Run the production 1,000-qubit evidence gate.

    Pass criteria are stabilizer-group membership and digest-verified exact
    PULVINI checkpoint restoration. Measurement correlation is reported but is
    explicitly excluded from the pass condition because a copied classical bit
    can reproduce it.
    """
    machine = PhiQuantumMachine1000()
    result = machine.execute(PhiQuantumCircuit.ghz(1000), shots=shots, seed=42)
    stabilizer_evidence = verify_ghz_stabilizer_group(machine.register)

    checkpoint = machine.checkpoint(depth=20)
    before = machine.state_digest()
    machine.register.x(0)
    mutated = machine.state_digest()
    machine.restore(checkpoint)
    restored = machine.state_digest()
    restore_verified = mutated != before and restored == before == checkpoint.digest

    diagnostic_correlations = all(
        all(bit == 0 for bit in row) or all(bit == 1 for bit in row)
        for row in result.samples
    )
    verification_pass = bool(
        stabilizer_evidence["all_generators_verified"] and restore_verified
    )
    return {
        **machine.system_report(),
        "circuit": "GHZ-1000",
        "gates": result.gates_executed,
        "shots": shots,
        "state_digest": before,
        "stabilizer_evidence": stabilizer_evidence,
        "pulvini_checkpoint_depth": checkpoint.depth,
        "pulvini_restore_digest_verified": restore_verified,
        "measurement_correlation_diagnostic": diagnostic_correlations,
        "measurement_correlation_is_evidence": False,
        "verification_pass": verification_pass,
    }


run_1000_qubit_demonstration = run_1000_qubit_verification

__all__ = [
    "ghz_expected_generators",
    "run_1000_qubit_demonstration",
    "run_1000_qubit_verification",
    "stabilizer_contains",
    "verify_ghz_stabilizer_group",
]
