"""Tests for Exact Finite-Field Entanglement and Superposition Engine over F_257."""

import pytest  # noqa: F401
from chronus.quantum.entanglement import (
    BellStateKind,
    algebraic_concurrence_determinant,
    create_bell_state,
    create_ghz_state,
    create_superposition_state,
    entanglement_entropy_proxy,
    is_entangled_bipartite,
    superposition_memory_lookup,
)
from chronus.quantum.statevector import StateVector

pytestmark = pytest.mark.real


def test_uniform_superposition_state_preparation():
    state = create_superposition_state(3)
    assert state.num_qubits == 3
    # Over F_257, H |0> = INV_SQRT2 * (|0> + |1>) where INV_SQRT2 = 30
    # For 3 qubits, amplitude is 30^3 mod 257 = 27000 mod 257 = 15
    expected_amp = pow(30, 3, 257)
    assert all(a == expected_amp for a in state.amplitudes)


def test_bell_state_maximally_entangled_algebraic_witness():
    # Test all 4 canonical Bell states
    for kind in (
        BellStateKind.PHI_PLUS,
        BellStateKind.PHI_MINUS,
        BellStateKind.PSI_PLUS,
        BellStateKind.PSI_MINUS,
    ):
        bell = create_bell_state(kind)
        assert bell.num_qubits == 2
        det = algebraic_concurrence_determinant(bell)
        # Det must be non-zero for entangled states (30*30 mod 257 = 129 != 0)
        assert det != 0
        assert is_entangled_bipartite(bell) is True

        proxy = entanglement_entropy_proxy(bell)
        assert proxy["is_entangled"] is True
        assert proxy["concurrence_determinant"] == det


def test_separable_product_state_zero_concurrence():
    # Pure unentangled product state: |00>, |01>, |10>, |11>
    for amp_idx in range(4):
        amps = [0, 0, 0, 0]
        amps[amp_idx] = 1
        separable = StateVector(2, amps)
        assert algebraic_concurrence_determinant(separable) == 0
        assert is_entangled_bipartite(separable) is False


def test_ghz_tripartite_entanglement_structure():
    ghz = create_ghz_state(3)
    assert ghz.num_qubits == 3
    amps = ghz.amplitudes
    # In GHZ state (|000> + |111>) / sqrt(2):
    # index 0 (|000>) is 30, index 7 (|111>) is 30, all other 6 amplitudes are 0
    assert amps[0] == 30
    assert amps[7] == 30
    assert all(amps[i] == 0 for i in range(1, 7))


def test_superposition_memory_lookup_acceleration():
    pages = [
        b"PAGE_ZERO_EMPTY",
        b"PAGE_ONE_TARGET_VAL",
        b"PAGE_TWO_DATA_X",
        b"PAGE_THREE_DATA_Y",
    ]
    target_byte = ord("T")  # In PAGE_ONE_TARGET_VAL

    lookup_result = superposition_memory_lookup(pages, target_byte)
    assert lookup_result["found"] is True
    assert 1 in lookup_result["matching_indices"]
    assert lookup_result["superposition_amplified"] is True
    assert lookup_result["iterations"] == 1
