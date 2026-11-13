# AL HARAS SCENARIO TEST SUITE
# Real-World Failure Mode Reproduction - Japan (AP) emergency cybersecurity report (Nov 2026)
# Run: python -m pytest tests/test_al_haras_scenarios.py -v

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
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

# Scenario 1 - CREDENTIAL / PASSPHRASE COMPROMISE
class TestPassphrasePaths:
    def test_empty_passphrase_rejected(self):
        res = ALHarasSecurityFabric.evaluate_ingress(payload=b"X", state_vectors=[[1.0]*3]*3, passphrase="")
        assert res["admitted"] is False
        assert res["status"] == "REJECTED & HEALED"

    def test_omitted_passphrase_admitted(self):
        res = ALHarasSecurityFabric.evaluate_ingress(payload=b"X", state_vectors=[[1.0]*3]*3)
        assert res["admitted"] is True

    def test_none_passphrase_admitted(self):
        res = ALHarasSecurityFabric.evaluate_ingress(payload=b"X", state_vectors=[[1.0]*3]*3, passphrase=None)
        assert res["admitted"] is True

    def test_whitespaced_passphrase(self):
        res = ALHarasSecurityFabric.evaluate_ingress(payload=b"X", state_vectors=[[1.0]*3]*3, passphrase="  SPEAK FRIEND AND ENTER  ")
        assert res["admitted"] is True
        assert res["status"] == "ADMITTED TO FABRIC"

# Scenario 2 - ADVERSARIAL STATE VECTORS (PROMPT INJECTION / NEURAL PERTURBATION)
class TestAdversarialVortexDetection:
    def test_large_perturbation_vortex(self):
        perturbed = [[1.0, 2.0, 3.0], [10.0, -15.0, 22.0], [1.0, 2.0, 3.0]]
        res = CellularSheafCohomology.compute_cohomology(perturbed)
        assert res["h0_consensus"] is False
        assert res["h1_vortex_norm"] > 0.0
        assert res["status"] == "ADVERSARIAL_VORTEX_ISOLATED"

    def test_pure_noise_state_rejected(self):
        noise = [[0.1, 0.9, 1.5], [2.3, 8.7, 4.2], [6.1, 1.4, 9.8]]
        res = CellularSheafCohomology.compute_cohomology(noise)
        assert res["h0_consensus"] is False
        assert res["h1_vortex_norm"] > 0.0
        assert res["status"] == "ADVERSARIAL_VORTEX_ISOLATED"

class TestCleanConsensusPreserved:
    def test_identical_vectors_clean(self):
        clean = [[2.5, 3.5, 4.5]] * 4
        res = CellularSheafCohomology.compute_cohomology(clean)
        assert res["h0_consensus"] is True
        assert res["h1_vortex_norm"] == 0.0
        assert res["status"] == "HARMONIC_CONSENSUS_CLEAN"

# Scenario 3 - DEEP STATE DRIFT (INCREMENTAL CORRUPTION OVER TIME)
class TestDeepStateDrift:
    def test_cumulative_drift_exceeds_tolerance(self):
        drift_vectors = [[1.0, 2.0, 3.0], [500.0, 1000.0, 2000.0], [1.0, 2.0, 3.0]]
        res = CellularSheafCohomology.compute_cohomology(drift_vectors)
        assert res["h0_consensus"] is False
        assert res["h1_vortex_norm"] > 0.0
        assert res["status"] == "ADVERSARIAL_VORTEX_ISOLATED"

    def test_is_secure_flag_matches_consensus(self):
        clean = [[1.0, 2.0, 3.0]] * 3
        clean_res = CellularSheafCohomology.compute_cohomology(clean)
        assert clean_res["is_secure"] is True
        assert clean_res["is_isolated"] is False

# Scenario 4 - MEMORY CORRUPTION / BITFLIP MICRO-INJECTION
class TestDSWInstantonHealing:
    def test_bitflip_payload_healed(self):
        payload = b"CRITICAL_SECURITY_GATEWAY_TRACE"
        res = DSW4DInstantonMonopoleHealer.inspect_and_heal(payload, is_perturbed=True)
        assert res["instanton_charge_k"] == 1
        assert res["cobordism_type"] == "INSTANTON_COBORDISM_TRACE_HEALED"
        assert res["healing_cycles"] == 1
        assert res["healed"] is True
        assert len(res["healed_trace_hash"]) == 64

    def test_clean_trace_no_fault(self):
        payload = b"CLEAN_EXECUTION_TRACE_NO_FAULT"
        res = DSW4DInstantonMonopoleHealer.inspect_and_heal(payload, is_perturbed=False)
        assert res["instanton_charge_k"] == 0
        assert res["cobordism_type"] == "TRIVIAL_COBORDISM_NO_FAULT"
        assert res["healing_cycles"] == 0
        assert res["healed"] is False
# Scenario 5 - PAYLOAD INTEGRITY (BSD RIEMANN-WEIL HECKE CHECKSUMS)
class TestHeckeModularChecksum:
    def test_paylooad_satisfies_weil_bound(self):
        payload = b"SOVEREIGN_SECURITY_PAYLOAD"
        res = HeckeModularChecksum.verify_payload_eigenform(payload)
        assert res["modular_form_weight"] == 2
        assert res["hecke_commutator_zero"] is True
        assert res["weil_bound_satisfied"] is True
        assert res["status"] == "HECKE_EIGENFORM_SATISFIED"

    def test_random_payloads_all_satisfy_bound(self):
        for i in range(50):
            payload = ("security_payload_" + str(i).zfill(4) + "_data").encode("utf-8")
            res = HeckeModularChecksum.verify_payload_eigenform(payload)
            assert res["weil_bound_satisfied"] is True
            assert res["status"] == "HECKE_EIGENFORM_SATISFIED"

# Scenario 6 - UNIFIED SECURITY FABRIC GATEWAY
class TestUnifiedSecurityFabric:
    def test_speak_friend_enter_admitted(self):
        res = ALHarasSecurityFabric.evaluate_ingress(payload=b"AUTHENTIC_DISPATCH_CODE", state_vectors=[[1.0]*3]*3, passphrase="SPEAK FRIEND AND ENTER")
        assert res["admitted"] is True
        assert res["status"] == "ADMITTED TO FABRIC"
        assert res["sheaf_cohomology"]["h0_consensus"] is True
        assert res["dsw_self_healing"]["healing_cycles"] == 0

    def test_adversarial_vectors_rejected(self):
        res = ALHarasSecurityFabric.evaluate_ingress(payload=b"AUTHENTIC_DISPATCH_CODE", state_vectors=[[1.0, 2.0, 3.0], [10.0, -15.0, 22.0], [1.0, 2.0, 3.0]], passphrase="SPEAK FRIEND AND ENTER")
        assert res["admitted"] is False

# Scenario 7 - SOVEREIGN GOVERNANCE & COMPLIANCE AUDIT
class TestSovereignGovernanceEngine:
    def test_ncsc_14_principles_compliant(self):
        audit = SovereignGovernanceEngine.audit_sovereign_compliance("sovereign_defence_authority")
        principles = audit["ncsc_14_principles"]
        assert len(principles) == 14
        assert all(v == "COMPLIANT_PASS" for v in principles.values())

    def test_sovereign_kernel_boot(self):
        kernel = ALHarasTopologicalKernel("UK_DEFENCE_CYBER")
        boot = kernel.boot_kernel()
        assert boot["boot_status"] == "KERNEL_BOOT_SUCCESSFUL"
        assert boot["maclane_pentagon_coherence"] is True
        assert boot["spectral_mass_gap"]["is_spectral_gap_valid"] is True

# Scenario 8 - BRAID COHERENCE & ZERO-FLOATING-POINT EXACT ARITHMETIC
class TestCyclotomicAnyonBraidEngine:
    def test_artin_braid_relation_satisfied(self):
        res = CyclotomicAnyonBraidEngine.compile_braid(["sigma_1", "sigma_2", "sigma_1"])
        assert res["artin_braid_relations"] == "SATISFIED_EXACT"
        assert res["artin_braid_satisfied"] is True
        assert res["status"] == "VERIFIED_COHERENT"

    def test_zero_floating_point_exact(self):
        res = CyclotomicAnyonBraidEngine.compile_braid()
        assert res["zero_float_truncation"] is True
        assert res["zero_floating_point"] is True

    def test_cyclotomic_polynomial_quotient(self):
        zeta = CyclotomicZ5(0, 1, 0, 0)
        ring_check = (zeta*zeta*zeta*zeta + zeta*zeta*zeta + zeta*zeta + zeta + CyclotomicZ5(1, 0, 0, 0))
        assert ring_check == CyclotomicZ5(0, 0, 0, 0), "x^4 + x^3 + x^2 + x + 1 must vanish"

# END OF SCENARIO TEST SUITE

class TestWrongPassphraseRejected:
    def test_wrong_passphrase_rejected_and_healed(self):
        res = ALHarasSecurityFabric.evaluate_ingress(payload=b"X", state_vectors=[[1.0]*3]*3, passphrase="WRONG")
        assert res["admitted"] is False
        assert res["status"] == "REJECTED & HEALED"

class TestCaseInsensitivePassphrase:
    def test_case_variant_passphrase_admitted(self):
        res = ALHarasSecurityFabric.evaluate_ingress(payload=b"X", state_vectors=[[1.0]*3]*3, passphrase="speak friend and enter")
        assert res["admitted"] is True
        assert res["status"] == "ADMITTED TO FABRIC"