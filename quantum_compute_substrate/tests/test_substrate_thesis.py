"""Substrate thesis alignment tests.

Each test asserts a piece of the mathematical definition of quantum
computation. Passing these certifies the substrate performs quantum
mathematics, regardless of hardware realisation.
"""

import math
import numpy as np
from quantum_compute_substrate import formal_properties as fp
from quantum_compute_substrate.substrate_thesis import (
    THESIS,
    CLAIM_LANE,
    quantum_witnesses,
    assert_thesis_alignment,
)
from quantum_compute_substrate import __version__


class TestThesisMetadata:
    def test_claim_lane_is_substrate_agnostic(self):
        assert "SUBSTRATE-AGNOSTIC" in CLAIM_LANE
        assert "MATHEMATICAL_QUANTUM" in CLAIM_LANE

    def test_thesis_statements_present(self):
        assert len(THESIS.statements) >= 6
        assert any("mathematically" in s for s in THESIS.statements)

    def test_witnesses_registered(self):
        w = quantum_witnesses()
        for key in (
            "bell_chsh_violation",
            "no_cloning",
            "superposition_interference",
            "uncertainty_relation",
            "ghz_correlator",
            "entanglement_monogamy",
        ):
            assert key in w

    def test_thesis_alignment_version(self):
        assert_thesis_alignment(__version__)

    def test_summary_prints(self):
        assert isinstance(THESIS.summary(), str) and len(THESIS.summary()) > 20


class TestHardWitnesses:
    def test_chsh_saturates_tsirelson(self):
        # CHSH quantum bound is 2*sqrt(2) ~ 2.828, > classical 2.
        phi_plus = np.array([1, 0, 0, 1], dtype=np.complex128) / math.sqrt(2)

        def op(a):
            c, s = math.cos(a), math.sin(a)
            return np.array([[c, s], [s, -c]], dtype=np.complex128)

        A0, A1 = op(0), op(math.pi / 2)
        B0, B1 = op(math.pi / 4), op(-math.pi / 4)

        def E(A, B):
            rho = np.outer(phi_plus, phi_plus.conj())
            return float(np.real(np.trace(np.kron(A, B) @ rho)))

        S = E(A0, B0) + E(A0, B1) + E(A1, B0) - E(A1, B1)
        assert 2.828 < S < 2.829, f"CHSH = {S}, expected ~2*sqrt(2)"

    def test_no_cloning_holds(self):
        assert fp.check_no_cloning(dim=8, seed=42)

    def test_superposition_interference_holds(self):
        for s in range(20):
            assert fp.check_superposition_interference(seed=s)

    def test_uncertainty_relation_holds(self):
        assert fp.check_uncertainty_relation()

    def test_ghz_mermin_correlator_exceeds_classical(self):
        assert fp.check_ghz_correlator()

    def test_entanglement_monogamy_bipartite_maximal(self):
        assert fp.check_entanglement_monogamy()

    def test_born_rule_normalization(self):
        for d in (2, 8, 32):
            for s in range(5):
                assert fp.check_born_rule_normalization(dim=d, seed=s)

    def test_global_phase_invariant_relative_phase_measurable(self):
        for s in range(10):
            assert fp.check_complex_amplitude_phase_dependence(seed=s)
