"""Differential verification of exact stabilizer measurement.

The tableau and the dense reference use the same little-endian qubit indexing:
qubit q is bit q of a computational-basis integer. The reference simulator is
independent NumPy state-vector algebra; it does not call the tableau's gate,
measurement, phase or row-reduction implementation.

Production rule: no mathematical xfail is permitted here. Random Clifford
circuits are checked before and after measurement, both measurement branches
are exercised when physically possible, stabilizer signs are retained, and
post-measurement continuation is compared again with the dense reference.
"""

from __future__ import annotations

import math
import random
import unittest

import numpy as np

from turing_universal_quantum_computer.stabilizer import StabilizerState

_H = np.array([[1, 1], [1, -1]], dtype=complex) / math.sqrt(2)
_S = np.array([[1, 0], [0, 1j]], dtype=complex)
_X = np.array([[0, 1], [1, 0]], dtype=complex)
_Y = np.array([[0, -1j], [1j, 0]], dtype=complex)
_Z = np.array([[1, 0], [0, -1]], dtype=complex)
_GATES = {
    "h": _H,
    "s": _S,
    "sdg": _S.conj().T,
    "x": _X,
    "y": _Y,
    "z": _Z,
}
_PAULIS = {"X": _X, "Y": _Y, "Z": _Z}


def _apply_single(
    psi: np.ndarray,
    n: int,
    qubit: int,
    matrix: np.ndarray,
) -> np.ndarray:
    """Apply one 2x2 gate with qubit q mapped to basis bit q."""
    out = np.zeros_like(psi)
    bit = 1 << qubit
    for index, amplitude in enumerate(psi):
        source = (index >> qubit) & 1
        base = index & ~bit
        out[base] += matrix[0, source] * amplitude
        out[base | bit] += matrix[1, source] * amplitude
    return out


def _apply_cnot(
    psi: np.ndarray,
    n: int,
    control: int,
    target: int,
) -> np.ndarray:
    """Apply CNOT using the same basis-bit convention as the tableau."""
    del n
    out = np.zeros_like(psi)
    target_bit = 1 << target
    for index, amplitude in enumerate(psi):
        destination = index ^ target_bit if (index >> control) & 1 else index
        out[destination] += amplitude
    return out


def _apply_pauli(psi: np.ndarray, n: int, label: str) -> np.ndarray:
    out = psi
    for qubit, symbol in enumerate(label):
        if symbol != "I":
            out = _apply_single(out, n, qubit, _PAULIS[symbol])
    return out


def _expectation(psi: np.ndarray, n: int, label: str) -> complex:
    return complex(np.vdot(psi, _apply_pauli(psi, n, label)))


def _project(
    psi: np.ndarray,
    n: int,
    qubit: int,
    outcome: int,
) -> np.ndarray | None:
    del n
    projected = psi.copy()
    for index in range(len(projected)):
        if ((index >> qubit) & 1) != outcome:
            projected[index] = 0
    norm = np.linalg.norm(projected)
    if norm < 1e-12:
        return None
    return projected / norm


def _dense_probabilities(psi: np.ndarray, qubit: int) -> tuple[float, float]:
    p0 = float(
        sum(
            abs(amplitude) ** 2
            for index, amplitude in enumerate(psi)
            if ((index >> qubit) & 1) == 0
        )
    )
    p1 = float(
        sum(
            abs(amplitude) ** 2
            for index, amplitude in enumerate(psi)
            if ((index >> qubit) & 1) == 1
        )
    )
    return p0, p1


def _random_circuit(seed: int, n: int = 3, gates: int = 12):
    rng = random.Random(seed)
    state = StabilizerState(n)
    psi = np.zeros(2**n, dtype=complex)
    psi[0] = 1.0
    for _ in range(gates):
        name = rng.choice(["h", "s", "sdg", "x", "y", "z", "cnot"])
        if name == "cnot":
            control, target = rng.sample(range(n), 2)
            state.cnot(control, target)
            psi = _apply_cnot(psi, n, control, target)
        else:
            qubit = rng.randrange(n)
            getattr(state, name)(qubit)
            psi = _apply_single(psi, n, qubit, _GATES[name])
    return state, psi, rng.randrange(n), rng


def _rank_from_unsigned_rows(rows: list[str], n: int) -> int:
    basis: dict[int, int] = {}
    for row in rows:
        x = sum(1 << q for q, ch in enumerate(row) if ch in "XY")
        z = sum(1 << q for q, ch in enumerate(row) if ch in "YZ")
        value = x | (z << n)
        while value:
            pivot = value.bit_length() - 1
            previous = basis.get(pivot)
            if previous is None:
                basis[pivot] = value
                break
            value ^= previous
    return len(basis)


def _group_matches_state(state: StabilizerState, psi: np.ndarray) -> tuple[bool, str]:
    """Every signed stabilizer must have +1 expectation and full rank."""
    n = state.n
    unsigned: list[str] = []
    for signed in state.stabilizer_strings():
        sign = -1 if signed.startswith("-") else 1
        row = signed[1:]
        unsigned.append(row)
        value = sign * _expectation(psi, n, row)
        if abs(value - 1) > 1e-8:
            return (
                False,
                f"{signed} has signed expectation "
                f"{value.real:+.6f}{value.imag:+.6f}i",
            )
    rank = _rank_from_unsigned_rows(unsigned, n)
    if rank != n:
        return False, f"stabilizers span {rank} of {n} independent generators"
    return True, "ok"


def _assert_state_matches_dense(state: StabilizerState, psi: np.ndarray) -> None:
    state.validate_invariants()
    ok, why = _group_matches_state(state, psi)
    assert ok, why


class KnownGoodMeasurementTests(unittest.TestCase):
    def _check(self, state, psi, qubit, expected_outcome):
        reference = _project(psi, state.n, qubit, expected_outcome)
        self.assertIsNotNone(reference)
        outcome = state.measure(qubit, outcome=expected_outcome)["outcome"]
        self.assertEqual(outcome, expected_outcome)
        state.validate_invariants()
        ok, why = _group_matches_state(state, reference)
        self.assertTrue(ok, why)

    def test_measuring_a_superposition_collapses_to_zero(self):
        state = StabilizerState(1)
        state.h(0)
        self._check(
            state,
            np.array([1, 1], dtype=complex) / math.sqrt(2),
            0,
            0,
        )

    def test_measuring_one_half_of_a_bell_pair(self):
        state = StabilizerState(2)
        state.h(0)
        state.cnot(0, 1)
        self._check(
            state,
            np.array([1, 0, 0, 1], dtype=complex) / math.sqrt(2),
            0,
            0,
        )

    def test_measuring_a_product_state(self):
        state = StabilizerState(2)
        state.h(0)
        state.h(1)
        self._check(state, np.ones(4, dtype=complex) / 2, 1, 1)

    def test_measuring_the_middle_of_a_ghz_state(self):
        state = StabilizerState(3)
        state.h(0)
        state.cnot(0, 1)
        state.cnot(1, 2)
        psi = np.zeros(8, dtype=complex)
        psi[0] = psi[7] = 1 / math.sqrt(2)
        self._check(state, psi, 1, 0)

    def test_measuring_a_deterministic_one_reports_one(self):
        state = StabilizerState(1)
        state.x(0)
        self.assertEqual(state.measure(0)["outcome"], 1)
        state.validate_invariants()

    def test_measuring_a_deterministic_zero_reports_zero(self):
        state = StabilizerState(1)
        self.assertEqual(state.measure(0)["outcome"], 0)
        state.validate_invariants()

    def test_forcing_a_deterministic_qubit_to_the_wrong_value_still_refuses(self):
        state = StabilizerState(1)
        state.x(0)
        with self.assertRaises(ValueError):
            state.measure(0, outcome=0)


def test_random_clifford_measurement_matches_dense_statevector():
    """1200 random circuits: probabilities, collapse, signs and invariants."""
    for seed in range(1200):
        state, psi, qubit, _ = _random_circuit(seed, n=3, gates=14)
        _assert_state_matches_dense(state, psi)

        dense_p0, dense_p1 = _dense_probabilities(psi, qubit)
        table_p0, table_p1 = state.measurement_probabilities(qubit)
        assert abs(float(table_p0) - dense_p0) < 1e-8, seed
        assert abs(float(table_p1) - dense_p1) < 1e-8, seed

        if dense_p0 > 1 - 1e-9:
            expected = 0
        elif dense_p1 > 1 - 1e-9:
            expected = 1
        else:
            expected = 0
        reference = _project(psi, state.n, qubit, expected)
        assert reference is not None
        record = state.measure(qubit)
        assert record["outcome"] == expected, seed
        _assert_state_matches_dense(state, reference)


def test_both_random_measurement_branches_match_dense_statevector():
    """Force each non-zero branch independently on the same generated state."""
    checked_random = 0
    for seed in range(500):
        _, psi, qubit, _ = _random_circuit(seed, n=4, gates=18)
        p0, p1 = _dense_probabilities(psi, qubit)
        if p0 < 1e-9 or p1 < 1e-9:
            continue
        checked_random += 1
        for outcome in (0, 1):
            state, regenerated, regenerated_qubit, _ = _random_circuit(
                seed, n=4, gates=18
            )
            assert regenerated_qubit == qubit
            assert np.allclose(regenerated, psi)
            reference = _project(psi, state.n, qubit, outcome)
            assert reference is not None
            record = state.measure(qubit, outcome=outcome)
            assert record["outcome"] == outcome
            _assert_state_matches_dense(state, reference)
    assert checked_random > 100


def test_post_measurement_clifford_continuation_remains_exact():
    """Collapse, continue evolving, and compare the resulting state again."""
    for seed in range(400):
        state, psi, qubit, rng = _random_circuit(seed, n=4, gates=20)
        p0, p1 = _dense_probabilities(psi, qubit)
        if p0 > 1 - 1e-9:
            outcome = 0
        elif p1 > 1 - 1e-9:
            outcome = 1
        else:
            outcome = rng.randrange(2)

        reference = _project(psi, state.n, qubit, outcome)
        assert reference is not None
        state.measure(qubit, outcome=outcome)
        _assert_state_matches_dense(state, reference)

        psi = reference
        for _ in range(16):
            name = rng.choice(["h", "s", "sdg", "x", "y", "z", "cnot"])
            if name == "cnot":
                control, target = rng.sample(range(state.n), 2)
                state.cnot(control, target)
                psi = _apply_cnot(psi, state.n, control, target)
            else:
                target = rng.randrange(state.n)
                getattr(state, name)(target)
                psi = _apply_single(psi, state.n, target, _GATES[name])
        _assert_state_matches_dense(state, psi)


def test_seeded_random_draw_is_reproducible_and_truthfully_labelled():
    a = StabilizerState(2).h(0).cnot(0, 1)
    b = StabilizerState(2).h(0).cnot(0, 1)
    first = a.measure(0, seed=73)
    second = b.measure(0, seed=73)
    assert first["outcome"] == second["outcome"]
    assert first["seeded_classical_draw"] is True
    assert second["seeded_classical_draw"] is True


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
