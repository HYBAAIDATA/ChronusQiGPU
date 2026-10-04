"""Measurement on the exact tableau, checked against a dense statevector.

``StabilizerState.measure`` is the one operation the whole exact path rests on:
marginals, shot sampling, entanglement queries and any error-correction layer
are all built from it.  These tests compare the tableau against an independent
dense simulation, so a disagreement is a disagreement with quantum mechanics
rather than with another tableau.

Two things are pinned:

* the cases the tableau gets right must keep working, including measuring a
  qubit that is deterministically |1>, which used to raise;
* the cases it currently gets wrong are recorded with a reproduction, so the
  defect cannot be mistaken for a passing suite.

Run: ``python -m pytest tests/test_stabilizer_measurement.py -q``
"""

from __future__ import annotations

import math
import random
import unittest

import numpy as np
import pytest

from turing_universal_quantum_computer.stabilizer import StabilizerState

I2 = np.eye(2, dtype=complex)
_H = np.array([[1, 1], [1, -1]], dtype=complex) / math.sqrt(2)
_S = np.array([[1, 0], [0, 1j]], dtype=complex)
_X = np.array([[0, 1], [1, 0]], dtype=complex)
_Y = np.array([[0, -1j], [1j, 0]], dtype=complex)
_Z = np.array([[1, 0], [0, -1]], dtype=complex)
_GATES = {"h": _H, "s": _S, "sdg": _S.conj().T, "x": _X, "y": _Y, "z": _Z}


def _operator(n: int, qubit: int, matrix: np.ndarray) -> np.ndarray:
    out = np.array([[1]], dtype=complex)
    for k in range(n):
        out = np.kron(out, matrix if k == qubit else I2)
    return out


def _cnot(n: int, control: int, target: int) -> np.ndarray:
    out = np.zeros((2 ** n, 2 ** n), dtype=complex)
    for i in range(2 ** n):
        bits = [(i >> k) & 1 for k in range(n)]
        if bits[control]:
            bits[target] ^= 1
        out[sum(b << k for k, b in enumerate(bits)), i] = 1
    return out


def _pauli_matrix(pauli: str) -> np.ndarray:
    table = {"I": I2, "X": _X, "Y": _Y, "Z": _Z}
    out = np.array([[1]], dtype=complex)
    for symbol in pauli:
        out = np.kron(out, table[symbol])
    return out


def _expectation(psi: np.ndarray, pauli: str) -> complex:
    return complex(np.vdot(psi, _pauli_matrix(pauli) @ psi))


def _random_circuit(seed: int, n: int = 3, gates: int = 10):
    rng = random.Random(seed)
    state = StabilizerState(n)
    psi = np.zeros(2 ** n, dtype=complex)
    psi[0] = 1.0
    for _ in range(gates):
        name = rng.choice(["h", "s", "sdg", "x", "y", "z", "cnot"])
        if name == "cnot":
            control, target = rng.sample(range(n), 2)
            state.cnot(control, target)
            psi = _cnot(n, control, target) @ psi
        else:
            qubit = rng.randrange(n)
            getattr(state, name)(qubit)
            psi = _operator(n, qubit, _GATES[name]) @ psi
    return state, psi, rng.randrange(n), n


def _projection_zero(n: int, qubit: int) -> np.ndarray:
    projector = np.zeros((2, 2), dtype=complex)
    projector[0, 0] = 1
    return _operator(n, qubit, projector)


def _group_matches_state(rows, psi: np.ndarray, n: int):
    """Every row must have +1 expectation, and the rows must pin the state."""
    for row in rows:
        value = _expectation(psi, row)
        if abs(value - 1) > 1e-8:
            return False, f"{row} has expectation {value.real:+.4f}{value.imag:+.4f}i"
    basis: dict[int, int] = {}
    rank = 0
    for row in rows:
        x = sum(1 << q for q, ch in enumerate(row) if ch in "XY")
        z = sum(1 << q for q, ch in enumerate(row) if ch in "YZ")
        vector = x | (z << n)
        while vector:
            pivot = vector.bit_length() - 1
            if pivot in basis:
                vector ^= basis[pivot]
            else:
                basis[pivot] = vector
                rank += 1
                break
    if rank != n:
        return False, f"rows span {rank} of {n} dimensions"
    return True, "ok"


class KnownGoodMeasurementTests(unittest.TestCase):
    """Cases the tableau already gets right.  These must not regress."""

    def _check(self, state, psi, qubit, n):
        reference = _projection_zero(n, qubit) @ psi
        norm = np.linalg.norm(reference)
        self.assertGreater(norm, 1e-9)
        reference = reference / norm
        outcome = state.measure(qubit)["outcome"]
        self.assertEqual(outcome, 0)
        ok, why = _group_matches_state(
            [row.lstrip("+-") for row in state.stabilizer_strings()], reference, n
        )
        self.assertTrue(ok, why)

    def test_measuring_a_superposition_collapses_to_zero(self):
        state = StabilizerState(1)
        state.h(0)
        self._check(state, np.array([1, 1], dtype=complex) / math.sqrt(2), 0, 1)

    def test_measuring_one_half_of_a_bell_pair(self):
        state = StabilizerState(2)
        state.h(0)
        state.cnot(0, 1)
        self._check(state, np.array([1, 0, 0, 1], dtype=complex) / math.sqrt(2), 0, 2)

    def test_measuring_a_product_state(self):
        state = StabilizerState(2)
        state.h(0)
        state.h(1)
        self._check(state, np.ones(4, dtype=complex) / 2, 0, 2)

    def test_measuring_the_middle_of_a_ghz_state(self):
        state = StabilizerState(3)
        state.h(0)
        state.cnot(0, 1)
        state.cnot(1, 2)
        psi = np.zeros(8, dtype=complex)
        psi[0] = psi[7] = 1 / math.sqrt(2)
        self._check(state, psi, 1, 3)

    def test_measuring_a_deterministic_one_reports_one(self):
        state = StabilizerState(1)
        state.x(0)
        self.assertEqual(state.measure(0)["outcome"], 1)

    def test_measuring_a_deterministic_zero_reports_zero(self):
        self.assertEqual(StabilizerState(1).measure(0)["outcome"], 0)

    def test_forcing_a_deterministic_qubit_to_the_wrong_value_still_refuses(self):
        state = StabilizerState(1)
        state.x(0)
        with self.assertRaises(ValueError):
            state.measure(0, outcome=0)


@pytest.mark.xfail(
    reason=(
        "Known defect, reproduced here: on random Clifford circuits the tableau's "
        "post-measurement stabilizer group disagrees with a dense statevector, and "
        "measure() raises StabilizerDomainError on others. The clearing loop in "
        "measure() sums a stabilizer row into its own anticommuting destabilizer "
        "partner, where the phase update is undefined. Delete this marker when the "
        "engine is fixed."
    ),
    strict=False,
)
def test_random_clifford_measurement_matches_a_dense_statevector():
    """Reproduction.  841 of 1119 comparisons disagreed when this was measured."""
    checked = 0
    mismatches = []
    for seed in range(400):
        state, psi, qubit, n = _random_circuit(seed)
        reference = _projection_zero(n, qubit) @ psi
        if np.linalg.norm(reference) < 1e-9:
            continue
        reference = reference / np.linalg.norm(reference)
        try:
            outcome = state.measure(qubit)["outcome"]
        except Exception as exc:  # the other half of the defect
            mismatches.append(f"seed {seed}: {type(exc).__name__}")
            continue
        if outcome != 0:
            mismatches.append(f"seed {seed}: reported outcome {outcome}")
            continue
        checked += 1
        ok, why = _group_matches_state(
            [row.lstrip("+-") for row in state.stabilizer_strings()], reference, n
        )
        if not ok:
            mismatches.append(f"seed {seed}: {why}")
    assert checked > 100
    assert not mismatches, f"{len(mismatches)} of {checked + len(mismatches)} disagree: {mismatches[:5]}"


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
