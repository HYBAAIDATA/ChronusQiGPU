"""Exact tests for the AL HARAS core engines (no web framework needed).

Each test checks a computed property against an independent derivation, an
adversarial input, or a mutation that a wrong implementation would not survive.
"""

import hashlib
import os
import sys
from fractions import Fraction

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pytest

from chronus.security.al_haras import braids, expander, fingerprint, golden, reed_solomon
from chronus.security.al_haras.cyclotomic import ONE, PHI, PHI_INVERSE, ZERO, CyclotomicZ5, mat2_mul
from chronus.security.al_haras.engine import (
    ALHarasSecurityFabric,
    CellularSheafCohomology,
    CyclotomicAnyonBraidEngine,
    DSW4DInstantonMonopoleHealer,
    HeckeModularChecksum,
    RamanujanExpanderSpectralGapGuard,
)
from chronus.security.al_haras.exact import decimal_string, householder, is_orthogonal, sqrt_decimal_string, to_fraction
from chronus.security.al_haras.receipts import ReceiptSigner, signed_receipt
from chronus.security.al_haras.sheaf import GraphSheaf, SheafError, analyse_states
from chronus.security.al_haras.sovereign import SovereignGovernanceEngine
from chronus.security.al_haras.topological_os import ALHarasTopologicalKernel, run_self_tests

pytestmark = pytest.mark.real


# --------------------------------------------------------------------------- exact helpers
class TestExactHelpers:
    def test_float_inputs_are_read_as_the_decimal_literal(self):
        assert to_fraction(0.1) == Fraction(1, 10)
        assert to_fraction("2/3") == Fraction(2, 3)
        with pytest.raises(ValueError):
            to_fraction(float("nan"))
        with pytest.raises(TypeError):
            to_fraction(True)

    def test_decimal_rendering_is_integer_exact(self):
        assert decimal_string(Fraction(2, 3), 4) == "0.6667"
        assert sqrt_decimal_string(Fraction(2), 8) == "1.41421356"

    def test_householder_is_exactly_orthogonal(self):
        h = householder([Fraction(1), Fraction(2), Fraction(2)])
        assert is_orthogonal(h)
        assert not is_orthogonal([[Fraction(1), Fraction(1)], [Fraction(0), Fraction(1)]])


# --------------------------------------------------------------------------- sheaf
class TestSheafConsistency:
    def test_identical_states_form_a_global_section(self):
        res = CellularSheafCohomology.compute_cohomology([[1, 2, 3]] * 4)
        assert res["h0_consensus"] is True
        assert res["coboundary_max_edge_norm"] == "0.00000000"
        assert res["status"] == "CONSISTENT"

    def test_orthogonal_unit_states_have_coboundary_norm_sqrt_two(self):
        # The 1.41421356 figure in older notes is this computed value for this input.
        res = CellularSheafCohomology.compute_cohomology([[1, 0], [0, 1]])
        assert res["h0_consensus"] is False
        assert res["coboundary_max_edge_norm_sq"] == "2"
        assert res["coboundary_max_edge_norm"] == "1.41421356"

    def test_rogue_node_is_located_and_isolated(self):
        states = {"Planner": [1, 0, 0, 1], "Coder": [99, -88, 77, 66], "Executor": [1, 0, 0, 1], "Tool": [1, 0, 0, 1]}
        edges = [("Planner", "Coder"), ("Coder", "Executor"), ("Executor", "Tool")]
        res = CellularSheafCohomology.compute_cohomology(latent_vectors=states, edges=edges)
        assert res["isolating_nodes"] == ["Coder"]
        assert res["status"] == "INCONSISTENT_STATES_ISOLATED"
        # The repair is the nearest global section: here the mean of the four states.
        expected = [str(Fraction(99 + 3, 4)), str(Fraction(-88, 4)), str(Fraction(77, 4)), str(Fraction(66 + 3, 4))]
        assert res["nearest_global_section"]["Coder"] == expected

    def test_tolerance_is_explicit_and_exact(self):
        states = {"a": [1.0, 2.0], "b": [1.0001, 2.0]}
        assert analyse_states(states, edges=[("a", "b")], tolerance="0.0001")["consistent"] is True
        assert analyse_states(states, edges=[("a", "b")], tolerance="0.00009")["consistent"] is False

    def test_cohomology_dimensions_follow_euler_characteristic(self):
        triangle = GraphSheaf(["a", "b", "c"], [("a", "b"), ("b", "c"), ("c", "a")], 2)
        dims = triangle.cohomology_dimensions()
        assert dims == {"h0": 2, "h1": 2, "euler_characteristic": 0}
        tree = GraphSheaf(["a", "b", "c"], [("a", "b"), ("b", "c")], 3)
        assert tree.cohomology_dimensions()["h1"] == 0

    def test_holonomy_reduces_global_sections(self):
        # A reflection around a 2-cycle fixes a hyperplane: dim H^0 = d - 1.
        h = householder([Fraction(1), Fraction(2), Fraction(2)])
        sheaf = GraphSheaf(["a", "b"], [("a", "b"), ("b", "a")], 3, {(0, "a"): h})
        assert sheaf.cohomology_dimensions()["h0"] == 2

    def test_edge_cochain_class_detects_cycle_contradictions(self):
        triangle = GraphSheaf(["a", "b", "c"], [("a", "b"), ("b", "c"), ("c", "a")], 1)
        assert triangle.is_coboundary([[1], [2], [-3]])["is_coboundary"] is True
        inconsistent = triangle.is_coboundary([[1], [1], [1]])
        assert inconsistent["is_coboundary"] is False
        assert inconsistent["fundamental_cycle_defects"][0]["cycle_defect_norm_sq"] == 9

    def test_non_orthogonal_restriction_maps_are_rejected(self):
        with pytest.raises(SheafError):
            GraphSheaf(["a", "b"], [("a", "b")], 2, {(0, "a"): [[1, 1], [0, 1]]})

    def test_no_states_is_reported_as_not_evaluated(self):
        res = CellularSheafCohomology.compute_cohomology([])
        assert res["evaluated"] is False
        assert res["status"] == "NO_STATE_SUPPLIED"


# --------------------------------------------------------------------------- Reed-Solomon
class TestReedSolomonHealing:
    def test_clean_trace_needs_no_repair(self):
        res = DSW4DInstantonMonopoleHealer.inspect_and_heal(b"execution trace")
        assert res["status"] == "NO_CORRUPTION_DETECTED"
        assert res["healed"] is False

    @pytest.mark.parametrize("faults", [1, 3, 8])
    def test_drill_repairs_injected_faults_and_verifies_hash(self, faults):
        trace = bytes(range(32))
        res = DSW4DInstantonMonopoleHealer.inspect_and_heal(trace, is_perturbed=True, fault_count=faults)
        assert res["healed"] is True
        assert sorted(res["corrected_positions"]) == sorted(res["injected_fault_positions"])
        assert res["repaired_trace_sha256"] == hashlib.sha256(trace).hexdigest()
        assert res["checkpoint_restore_used"] is False

    def test_more_errors_than_capacity_are_reported_uncorrectable(self):
        trace = bytes(range(32))
        env = reed_solomon.protect(trace)
        corrupted = reed_solomon.inject_faults(trace, list(range(9)))  # t = 8 for RS(48,32)
        res = reed_solomon.heal(corrupted, env)
        assert res["integrity_verified"] is False

    def test_parity_corruption_is_also_corrected(self):
        trace = b"parity symbols can be hit too"
        env = reed_solomon.protect(trace)
        parity = [list(block) for block in env["parity"]]
        parity[0][0] = (parity[0][0] + 1) % 257
        res = reed_solomon.heal(trace, env, received_parity=parity)
        assert res["integrity_verified"] is True

    def test_encoding_is_a_polynomial_code(self):
        # Mutation guard: parity must equal the interpolating polynomial at x = k+1..n.
        data = [7] * 32
        assert reed_solomon.encode_block(data, 48, 32) == [7] * 16


# --------------------------------------------------------------------------- expander
class TestPaleyExpander:
    def test_paley_257_is_certified_exactly(self):
        res = RamanujanExpanderSpectralGapGuard.verify_mass_gap()
        assert res["satisfies_bound"] is True
        assert res["degree"] == 128
        assert res["srg_parameters"] == [257, 128, 63, 64]
        assert res["lambda_2_decimal"] == decimal_string((Fraction(160312195, 10**7) - 1) / 2, 6)

    def test_non_paley_order_is_rejected(self):
        with pytest.raises(expander.ExpanderError):
            expander.certify_paley(19)  # 19 = 3 mod 4

    def test_mixing_bound_is_monotone_in_epsilon(self):
        assert expander.mixing_steps(257, Fraction(1, 2**8)) <= expander.mixing_steps(257, Fraction(1, 2**32))

    def test_thirty_percent_vertex_loss_keeps_p257_connected(self):
        for strategy in ("hashed", "ball"):
            res = expander.removal_resilience(257, Fraction(3, 10), strategy=strategy)
            assert res["removed"] == 77 and res["remaining_connected"] is True


# --------------------------------------------------------------------------- braids
class TestBraidRelations:
    def test_relations_hold_exactly(self):
        assert all(braids.verify_relations().values())
        assert CyclotomicAnyonBraidEngine.compile_braid()["status"] == "VERIFIED_COHERENT"

    def test_wrong_r_matrix_breaks_the_artin_relation(self):
        bad_r = [[ONE, ZERO], [ZERO, CyclotomicZ5.zeta_power(1)]]
        f = braids.F_MATRIX
        s1, s2 = bad_r, mat2_mul(mat2_mul(f, bad_r), f)
        assert mat2_mul(mat2_mul(s1, s2), s1) != mat2_mul(mat2_mul(s2, s1), s2)

    def test_golden_ratio_inside_z_zeta5(self):
        assert PHI * PHI == PHI + ONE and PHI * PHI_INVERSE == ONE

    def test_unknown_generators_are_rejected(self):
        with pytest.raises(ValueError):
            braids.compile_braid_word(["sigma_9"])


# --------------------------------------------------------------------------- fingerprint, Lucas
class TestFingerprintAndLucas:
    def test_point_count_matches_independent_legendre_sum(self):
        res = HeckeModularChecksum.verify_payload_eigenform(b"payload")
        assert res["independent_trace_check"] is True
        assert res["frobenius_trace_ap"] ** 2 <= 4 * 257
        assert res["status"] == "HASSE_BOUND_VERIFIED"

    def test_small_curve_count_by_hand(self):
        # y^2 = x^3 + x over F_5 has 4 affine points plus infinity.
        assert fingerprint.count_points(1, 0, 5) == 4

    def test_lucas_and_binet_are_exact(self):
        assert [golden.lucas(n) for n in range(8)] == [2, 1, 3, 4, 7, 11, 18, 29]
        assert golden.binet_lucas_identity(479)
        profile = golden.storage_profile(479)
        assert profile["lucas_digits"] == len(str(golden.lucas(479)))
        assert profile["value_bytes"] == (golden.lucas(479).bit_length() + 7) // 8

    def test_zeckendorf_is_unique_and_non_adjacent(self):
        for n in (1, 2, 3, 100, 1000, 10**9 + 7):
            res = golden.verify_zeckendorf(n)
            assert res["sum_matches"] and res["non_adjacent"]


# --------------------------------------------------------------------------- receipts & decisions
class TestReceiptsAndDecisions:
    def test_receipt_signature_verifies_and_detects_tampering(self):
        rec = signed_receipt({"decision": "ADMIT", "n": 1})
        assert ReceiptSigner.verify(rec["body"], rec["signature"]) is True
        assert ReceiptSigner.verify({"decision": "REJECT", "n": 1}, rec["signature"]) is False

    def test_ingress_admits_consistent_and_rejects_inconsistent_states(self):
        ok = ALHarasSecurityFabric.evaluate_ingress(b"payload", [[1, 2], [1, 2], [1, 2]])
        bad = ALHarasSecurityFabric.evaluate_ingress(b"payload", [[1, 2], [1, 2], [9, 2]])
        assert ok["admitted"] is True and bad["admitted"] is False
        assert bad["sheaf_cohomology"]["isolating_nodes"] == ["n2"]
        assert ReceiptSigner.verify(bad["receipt"]["body"], bad["receipt"]["signature"])

    def test_passphrase_is_not_a_credential(self):
        a = ALHarasSecurityFabric.evaluate_ingress(b"x", [[1], [1]], passphrase="anything")
        b = ALHarasSecurityFabric.evaluate_ingress(b"x", [[1], [1]], passphrase="SPEAK FRIEND AND ENTER")
        assert a["admitted"] == b["admitted"] is True

    def test_governance_register_claims_no_certification(self):
        reg = SovereignGovernanceEngine.audit_sovereign_compliance("t")
        assert reg["certifications_held"] == []
        assert reg["principles_independently_assessed"] == 0
        assert len(reg["ncsc_14_principles"]) == 14
        assert all(p["assessment"] == "NOT_ASSESSED" for p in reg["ncsc_14_principles"].values())

    def test_kernel_self_test_is_computed(self):
        tests = run_self_tests()
        assert set(tests) >= {"braid_relations_exact", "reed_solomon_repair_verified", "paley_257_ramanujan_certified"}
        boot = ALHarasTopologicalKernel("t").boot_kernel()
        assert boot["boot_status"] == ("SELF_TEST_PASSED" if all(tests.values()) else "SELF_TEST_FAILED")
