# AL HARAS SCENARIO TEST SUITE
# Real-World Failure Mode Reproduction - Japan (AP) emergency cybersecurity report (Nov 2026)
# Run: python -m pytest tests/test_al_haras_scenarios.py -v

import os
import sys

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)
from chronus.security.al_haras import (
    ALHarasSecurityFabric,
    CellularSheafCohomology,
    CyclotomicAnyonBraidEngine,
    CyclotomicZ5,
    DSW4DInstantonMonopoleHealer,
    HeckeModularChecksum,
    SovereignGovernanceEngine,
    ALHarasTopologicalKernel,
)


# Scenario 1 - the legacy passphrase argument is compatibility-only
class TestPassphrasePaths:
    def test_empty_passphrase_is_not_used_as_a_credential(self):
        res = ALHarasSecurityFabric.evaluate_ingress(
            payload=b"X", state_vectors=[[1.0] * 3] * 3, passphrase=""
        )
        assert res["admitted"] is True
        assert res["status"] == "ADMITTED"
        assert (
            "authentication (enforced by the API layer)" in res["checks_not_performed"]
        )

    def test_omitted_passphrase_admitted(self):
        res = ALHarasSecurityFabric.evaluate_ingress(
            payload=b"X", state_vectors=[[1.0] * 3] * 3
        )
        assert res["admitted"] is True

    def test_none_passphrase_admitted(self):
        res = ALHarasSecurityFabric.evaluate_ingress(
            payload=b"X", state_vectors=[[1.0] * 3] * 3, passphrase=None
        )
        assert res["admitted"] is True

    def test_whitespaced_passphrase(self):
        res = ALHarasSecurityFabric.evaluate_ingress(
            payload=b"X",
            state_vectors=[[1.0] * 3] * 3,
            passphrase="  SPEAK FRIEND AND ENTER  ",
        )
        assert res["admitted"] is True
        assert res["status"] == "ADMITTED"


# Scenario 2 - ADVERSARIAL STATE VECTORS (PROMPT INJECTION / NEURAL PERTURBATION)
class TestAdversarialVortexDetection:
    def test_large_perturbation_vortex(self):
        perturbed = [[1.0, 2.0, 3.0], [10.0, -15.0, 22.0], [1.0, 2.0, 3.0]]
        res = CellularSheafCohomology.compute_cohomology(perturbed)
        assert res["h0_consensus"] is False
        assert res["coboundary_max_edge_norm_sq"] != "0"
        assert res["status"] == "INCONSISTENT_STATES_ISOLATED"

    def test_pure_noise_state_rejected(self):
        noise = [[0.1, 0.9, 1.5], [2.3, 8.7, 4.2], [6.1, 1.4, 9.8]]
        res = CellularSheafCohomology.compute_cohomology(noise)
        assert res["h0_consensus"] is False
        assert res["coboundary_max_edge_norm_sq"] != "0"
        assert res["status"] == "INCONSISTENT_STATES"


class TestCleanConsensusPreserved:
    def test_identical_vectors_clean(self):
        clean = [[2.5, 3.5, 4.5]] * 4
        res = CellularSheafCohomology.compute_cohomology(clean)
        assert res["h0_consensus"] is True
        assert res["coboundary_max_edge_norm_sq"] == "0"
        assert res["status"] == "CONSISTENT"


# Scenario 3 - DEEP STATE DRIFT (INCREMENTAL CORRUPTION OVER TIME)
class TestDeepStateDrift:
    def test_cumulative_drift_exceeds_tolerance(self):
        drift_vectors = [[1.0, 2.0, 3.0], [500.0, 1000.0, 2000.0], [1.0, 2.0, 3.0]]
        res = CellularSheafCohomology.compute_cohomology(drift_vectors)
        assert res["h0_consensus"] is False
        assert res["coboundary_max_edge_norm_sq"] != "0"
        assert res["status"] == "INCONSISTENT_STATES_ISOLATED"

    def test_is_secure_flag_matches_consensus(self):
        clean = [[1.0, 2.0, 3.0]] * 3
        clean_res = CellularSheafCohomology.compute_cohomology(clean)
        assert clean_res["h0_consensus"] is True
        assert clean_res["is_isolated"] is False


# Scenario 4 - MEMORY CORRUPTION / BITFLIP MICRO-INJECTION
class TestDSWInstantonHealing:
    def test_bitflip_payload_healed(self):
        payload = b"CRITICAL_SECURITY_GATEWAY_TRACE"
        res = DSW4DInstantonMonopoleHealer.inspect_and_heal(payload, is_perturbed=True)
        assert res["mode"] == "fault_injection_drill"
        assert res["symbol_errors_corrected"] == 1
        assert res["status"] == "TRACE_REPAIRED_AND_VERIFIED"
        assert res["healed"] is True
        assert len(res["repaired_trace_sha256"]) == 64

    def test_clean_trace_no_fault(self):
        payload = b"CLEAN_EXECUTION_TRACE_NO_FAULT"
        res = DSW4DInstantonMonopoleHealer.inspect_and_heal(payload, is_perturbed=False)
        assert res["mode"] == "verify"
        assert res["symbol_errors_corrected"] == 0
        assert res["status"] == "NO_CORRUPTION_DETECTED"
        assert res["healed"] is False


# Scenario 5 - payload-derived elliptic-curve fingerprint
class TestHeckeModularChecksum:
    def test_payload_point_count_satisfies_hasse_bound(self):
        payload = b"SOVEREIGN_SECURITY_PAYLOAD"
        res = HeckeModularChecksum.verify_payload_eigenform(payload)
        assert res["independent_trace_check"] is True
        assert res["weil_bound_satisfied"] is True
        assert res["status"] == "HASSE_BOUND_VERIFIED"

    def test_random_payloads_all_satisfy_bound(self):
        for i in range(50):
            payload = ("security_payload_" + str(i).zfill(4) + "_data").encode("utf-8")
            res = HeckeModularChecksum.verify_payload_eigenform(payload)
            assert res["independent_trace_check"] is True
            assert res["weil_bound_satisfied"] is True
            assert res["status"] == "HASSE_BOUND_VERIFIED"


# Scenario 6 - UNIFIED SECURITY FABRIC GATEWAY
class TestUnifiedSecurityFabric:
    def test_speak_friend_enter_admitted(self):
        res = ALHarasSecurityFabric.evaluate_ingress(
            payload=b"AUTHENTIC_DISPATCH_CODE",
            state_vectors=[[1.0] * 3] * 3,
            passphrase="SPEAK FRIEND AND ENTER",
        )
        assert res["admitted"] is True
        assert res["status"] == "ADMITTED"
        assert res["sheaf_cohomology"]["h0_consensus"] is True
        assert res["trace_protection"]["scheme"] == "reed-solomon-gf257-systematic"

    def test_adversarial_vectors_rejected(self):
        res = ALHarasSecurityFabric.evaluate_ingress(
            payload=b"AUTHENTIC_DISPATCH_CODE",
            state_vectors=[[1.0, 2.0, 3.0], [10.0, -15.0, 22.0], [1.0, 2.0, 3.0]],
            passphrase="SPEAK FRIEND AND ENTER",
        )
        assert res["admitted"] is False


# Scenario 7 - governance register (evidence pointers, not certification)
class TestSovereignGovernanceEngine:
    def test_ncsc_14_principles_are_not_claimed_as_assessed(self):
        audit = SovereignGovernanceEngine.audit_sovereign_compliance(
            "sovereign_defence_authority"
        )
        principles = audit["ncsc_14_principles"]
        assert len(principles) == 14
        assert all(v["assessment"] == "NOT_ASSESSED" for v in principles.values())
        assert audit["principles_independently_assessed"] == 0
        assert audit["certifications_held"] == []

    def test_sovereign_kernel_boot(self):
        kernel = ALHarasTopologicalKernel("UK_DEFENCE_CYBER")
        boot = kernel.boot_kernel()
        assert boot["boot_status"] == "SELF_TEST_PASSED"
        assert set(boot["self_tests"]) >= {
            "braid_relations_exact",
            "reed_solomon_repair_verified",
            "paley_257_ramanujan_certified",
        }
        assert all(boot["self_tests"].values())


# Scenario 8 - BRAID COHERENCE & ZERO-FLOATING-POINT EXACT ARITHMETIC
class TestCyclotomicAnyonBraidEngine:
    def test_artin_braid_relation_satisfied(self):
        res = CyclotomicAnyonBraidEngine.compile_braid(
            ["sigma_1", "sigma_2", "sigma_1"]
        )
        assert res["relations_verified"]["artin_relation"] is True
        assert res["artin_braid_satisfied"] is True
        assert res["exact_arithmetic"] is True
        assert res["status"] == "VERIFIED_COHERENT"

    def test_zero_floating_point_exact(self):
        res = CyclotomicAnyonBraidEngine.compile_braid()
        assert res["exact_arithmetic"] is True
        assert all(res["relations_verified"].values())

    def test_cyclotomic_polynomial_quotient(self):
        zeta = CyclotomicZ5(0, 1, 0, 0)
        ring_check = (
            zeta * zeta * zeta * zeta
            + zeta * zeta * zeta
            + zeta * zeta
            + zeta
            + CyclotomicZ5(1, 0, 0, 0)
        )
        assert ring_check == CyclotomicZ5(0, 0, 0, 0), (
            "x^4 + x^3 + x^2 + x + 1 must vanish"
        )


# END OF SCENARIO TEST SUITE


class TestWrongPassphraseIgnored:
    def test_wrong_passphrase_does_not_override_state_decision(self):
        res = ALHarasSecurityFabric.evaluate_ingress(
            payload=b"X", state_vectors=[[1.0] * 3] * 3, passphrase="WRONG"
        )
        assert res["admitted"] is True
        assert res["status"] == "ADMITTED"


class TestCaseInsensitivePassphrase:
    def test_case_variant_passphrase_admitted(self):
        res = ALHarasSecurityFabric.evaluate_ingress(
            payload=b"X",
            state_vectors=[[1.0] * 3] * 3,
            passphrase="speak friend and enter",
        )
        assert res["admitted"] is True
        assert res["status"] == "ADMITTED"
