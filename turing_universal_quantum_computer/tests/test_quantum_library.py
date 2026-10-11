"""Tests for the quantum_library facade — every result exact, every lane named.

The assertions here check the contract that distinguishes this surface
from a float simulation: results are exact objects (integers, Fractions,
sympy expressions), the executing lane is recorded, and requests that no
exact lane can answer are refused rather than approximated.
"""

from fractions import Fraction

import pytest
import sympy as sp

from turing_universal_quantum_computer.quantum_library import (
    ExactLaneError,
    QuantumLibrary,
    TRUTH_EXACT,
)


def test_catalog_lists_all_families_with_owners():
    catalog = QuantumLibrary.catalog()
    for family in ("entanglement", "quantum_walk", "grover", "qpe", "qaoa", "vqe", "execute"):
        assert family in catalog
        assert catalog[family]["owner"]
        assert catalog[family]["lane"]


def test_lanes_report_live_backends():
    matrix = QuantumLibrary.lanes()
    names = {row["backend"] for row in matrix}
    assert {"exact_algebraic", "stabilizer", "mps_exact"} <= names


def test_bell_pair_entropy_is_one_ebit():
    res = QuantumLibrary.bell_pair()
    assert res.truth_class == TRUTH_EXACT
    assert res.payload["entropy_ebits"] == 1


def test_ghz_entropy_exact_at_large_n():
    res = QuantumLibrary.ghz(1000, subset={0})
    assert res.payload["entropy_ebits"] == 1
    assert res.lane == "clifford_tableau"


def test_entanglement_entropy_nonclifford_uses_register_lane():
    # A T gate takes the state out of the Clifford tableau class; the
    # facade must route to the exact register lane, not silently
    # approximate.  State stays separable => entropy 0.
    res = QuantumLibrary.entanglement_entropy(2, [("h", 0), ("phase", 0, Fraction(1, 8))], {0})
    assert res.lane == "exact_register"
    assert res.payload["entropy"] == "0"


def test_cycle_walk_distribution_is_exact_and_normalized():
    res = QuantumLibrary.quantum_walk_cycle(8, 10)
    probs = [sp.sympify(p) for p in res.payload["distribution"].values()]
    assert sp.simplify(sum(probs) - 1) == 0
    var = sp.sympify(res.payload["variance"])
    assert var > 0


def test_hypercube_walk_closed_form_at_large_n():
    res = QuantumLibrary.quantum_walk_hypercube(64, sp.pi / 4)
    dist = res.payload["hamming_distribution"]
    assert sp.simplify(sum(dist.values()) - 1) == 0


def test_grover_marks_state_with_exact_high_probability():
    res = QuantumLibrary.grover(4, marked=7)
    pa = res.payload["marked_probability"]
    assert res.payload["marked"] == 7
    assert pa > sp.Rational(9, 10)


def test_qpe_recovers_dyadic_phase_exactly():
    # T-gate eigenphase 1/8 with 3 counting qubits is exactly dyadic:
    # the readout must concentrate with probability exactly 1.
    res = QuantumLibrary.qpe(Fraction(1, 8), counting_qubits=3)
    assert res.payload["estimated_phase"] == "1/8"
    assert sp.sympify(res.payload["readout_probability"]) == 1
    assert res.payload["exact_dyadic"] is True


def test_qpe_nondyadic_phase_is_exact_not_float():
    res = QuantumLibrary.qpe(Fraction(1, 7), counting_qubits=3)
    assert res.payload["exact_dyadic"] is False
    for p in res.payload["readout_distribution"].values():
        # probabilities are exact sympy expressions, never floats
        assert not isinstance(sp.sympify(p), sp.Float)


def test_qaoa_triangle_beats_random_assignment():
    # Triangle graph: optimal cut = 2, uniform random expected cut = 3/2.
    edges = [(0, 1), (1, 2), (0, 2)]
    res = QuantumLibrary.qaoa_maxcut(
        edges, [(Fraction(3, 8), Fraction(1, 8))]
    )
    assert res.truth_class == TRUTH_EXACT
    assert res.payload["optimal_cut"] == 2
    expected = sp.sympify(res.payload["expected_cut"])
    assert expected == sp.Rational(15, 8)
    assert expected > sp.Rational(3, 2)  # beats the uniform-random cut
    assert sp.sympify(res.payload["probability_by_cut"][2]) == sp.Rational(15, 16)


def test_qaoa_grid_search_is_deterministic_and_exact():
    edges = [(0, 1), (1, 2), (0, 2)]
    res = QuantumLibrary.qaoa_maxcut_grid(edges, p_layers=1, grid=4)
    assert len(res.payload["search_history"]) == 1
    entry = res.payload["search_history"][0]
    Fraction(entry["gamma"])  # parses as an exact rational
    Fraction(entry["beta"])


def test_qaoa_rejects_irrational_angles():
    with pytest.raises(ExactLaneError):
        QuantumLibrary.qaoa_maxcut([(0, 1)], [("pi/4", Fraction(1, 4))])


def test_vqe_expectation_respects_variational_bound():
    # 2-qubit TFIM: H = ZZ + X0 + X1, exact ground energy -sqrt(2) - ... computed below.
    terms = QuantumLibrary.ising_terms(2, J=1, g=1)
    res = QuantumLibrary.vqe_evaluate(2, [("yrot", 0, Fraction(1, 4)), ("yrot", 1, Fraction(1, 4))], terms)
    energy = sp.sympify(res.payload["energy"])
    assert not isinstance(energy, sp.Float)
    scan = QuantumLibrary.vqe_ising_scan(2, J=1, g=1, grid=8)
    ground = sp.sympify(scan.payload["exact_ground_energy"])
    # variational principle: every exact expectation >= true ground
    assert energy >= ground
    assert sp.sympify(scan.payload["min_energy"]) >= ground
    # the yrot product ansatz reaches at least E = -1 on the 2-qubit TFIM
    assert sp.sympify(scan.payload["min_energy"]) <= sp.Integer(-1)


def test_execute_ops_selects_exact_lane_for_clifford():
    res = QuantumLibrary.execute_ops(2, [("h", 0), ("cx", 0, 1)])
    assert res.payload["truth_class"] == "exact"
    assert res.lane in {"exact_algebraic", "stabilizer", "sparse", "closed_form"}


def test_execute_ops_refuses_unknown_gate():
    from turing_universal_quantum_computer.backends import StatevectorTooLargeError

    with pytest.raises((StatevectorTooLargeError, ValueError)):
        QuantumLibrary.execute_ops(2, [("tooffoli", 0, 1, 2)])


def test_all_results_carry_lane_and_time():
    for res in (
        QuantumLibrary.bell_pair(),
        QuantumLibrary.quantum_walk_cycle(4, 3),
        QuantumLibrary.grover(3, 5),
    ):
        assert res.lane
        assert res.wall_ms >= 0.0
        assert res.truth_class == TRUTH_EXACT
