"""Tests for AL HARAS Sovereign Topological Quantum Immunity Swarm & OS."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pytest
from fastapi.testclient import TestClient

from chronus.security.al_haras import (
    ALHarasSecurityFabric,
    ALHarasSovereignProductSDK,
    CellularSheafCohomology,
    CyclotomicAnyonBraidEngine,
    CyclotomicZ5,
    DSW4DInstantonMonopoleHealer,
    ExactQ5,
    GaloisField257Phi,
    HeckeModularChecksum,
    RamanujanExpanderSpectralGapGuard,
    SovereignGovernanceEngine,
    ALHarasTopologicalKernel,
    ALHarasSovereignOSProduct,
)
from chronus.service.app import create_app


@pytest.fixture
def api_client():
    app = create_app()
    return TestClient(app)


class TestCellularSheafCohomology:
    def test_clean_harmonic_consensus_h0(self):
        clean_vectors = [[1.0, 2.0, 3.0], [1.0, 2.0, 3.0], [1.0, 2.0, 3.0]]
        res = CellularSheafCohomology.compute_cohomology(clean_vectors)
        assert res["h0_consensus"] is True
        assert res["h1_vortex_norm"] == 0.0
        assert res["status"] == "HARMONIC_CONSENSUS_CLEAN"
        assert res["is_isolated"] is False

    def test_adversarial_vortex_isolated_h1(self):
        perturbed_vectors = [
            [1.0, 2.0, 3.0],
            [10.0, -15.0, 22.0],
            [1.0, 2.0, 3.0],
        ]
        res = CellularSheafCohomology.compute_cohomology(perturbed_vectors)
        assert res["h0_consensus"] is False
        assert res["h1_vortex_norm"] > 0.0
        assert res["status"] == "ADVERSARIAL_VORTEX_ISOLATED"
        assert res["is_isolated"] is True


class TestDSW4DInstantonMonopoleHealer:
    def test_trivial_cobordism_clean(self):
        payload = b"CLEAN_SPACETIME_TRACE_PAYLOAD"
        res = DSW4DInstantonMonopoleHealer.inspect_and_heal(payload, is_perturbed=False)
        assert res["instanton_charge_k"] == 0
        assert res["cobordism_type"] == "TRIVIAL_COBORDISM_NO_FAULT"
        assert res["healing_cycles"] == 0
        assert res["healed"] is False

    def test_instanton_monopole_1cycle_healing(self):
        payload = b"BITFLIP_OR_MEMORY_PERTURBATION"
        res = DSW4DInstantonMonopoleHealer.inspect_and_heal(payload, is_perturbed=True)
        assert res["instanton_charge_k"] == 1
        assert res["cobordism_type"] == "INSTANTON_COBORDISM_TRACE_HEALED"
        assert res["healing_cycles"] == 1
        assert res["healed"] is True
        assert len(res["trace_hash"]) == 64


class TestRamanujanExpanderSpectralGap:
    def test_alon_boppana_mass_gap_bound(self):
        res = RamanujanExpanderSpectralGapGuard.verify_mass_gap()
        assert res["prime_p"] == 257
        assert res["degree_k"] == 258
        assert res["lambda_2"] <= res["alon_boppana_bound_2sqrt_p"]
        assert res["satisfies_bound"] is True
        assert res["spectral_mass_gap_delta"] == 229.14
        assert res["status"] == "SPECTRAL_MASS_GAP_SATISFIED"


class TestCyclotomicAnyonBraids:
    def test_exact_cyclotomic_z5_polynomial_quotient(self):
        identity = CyclotomicZ5(1, 0, 0, 0)
        zeta = CyclotomicZ5(0, 1, 0, 0)
        # x^4 + x^3 + x^2 + x + 1 = 0
        poly_zero = (
            zeta * zeta * zeta * zeta
            + zeta * zeta * zeta
            + zeta * zeta
            + zeta
            + identity
        )
        assert poly_zero == CyclotomicZ5(0, 0, 0, 0)

    def test_anyon_braid_compiler_coherence(self):
        res = CyclotomicAnyonBraidEngine.compile_braid()
        assert res["maclane_pentagon_coherence"] == "VERIFIED_COHERENT"
        assert res["artin_braid_relations"] == "SATISFIED_EXACT"
        assert res["zero_float_truncation"] is True


class TestHeckeModularChecksum:
    def test_weil_bound_satisfied(self):
        res = HeckeModularChecksum.verify_payload_eigenform(b"SOVEREIGN_PAYLOAD")
        assert res["modular_form_weight"] == 2
        assert res["hecke_commutator_zero"] is True
        assert res["weil_bound_satisfied"] is True
        assert res["status"] == "HECKE_EIGENFORM_SATISFIED"


class TestALHarasSecurityFabric:
    def test_speak_friend_and_enter_clean(self):
        res = ALHarasSecurityFabric.evaluate_ingress(
            payload=b"AUTHENTIC_EXECUTION_STREAM",
            passphrase="SPEAK FRIEND AND ENTER",
        )
        assert res["admitted"] is True
        assert res["status"] == "ADMITTED TO FABRIC"
        assert res["sheaf_cohomology"]["h0_consensus"] is True
        assert res["dsw_self_healing"]["healing_cycles"] == 0

    def test_wrong_passphrase_or_adversarial_rejected_and_healed(self):
        res = ALHarasSecurityFabric.evaluate_ingress(
            payload=b"MALICIOUS_PROMPT_INJECTION",
            passphrase="YOU_SHALL_NOT_PASS",
        )
        assert res["admitted"] is False
        assert res["status"] == "REJECTED & HEALED"
        assert res["dsw_self_healing"]["healing_cycles"] == 1


class TestSovereignComplianceAndOS:
    def test_ncsc_14_principles(self):
        audit = SovereignGovernanceEngine.audit_sovereign_compliance("sovereign_defence_hq")
        assert len(audit["ncsc_14_principles"]) == 14
        assert all(v == "COMPLIANT_PASS" for v in audit["ncsc_14_principles"].values())
        assert audit["fedramp_high_readiness"] == "FEDRAMP_HIGH_CERTIFIED"
        assert audit["dod_il6_compliance"] == "DOD_IL6_AIRGAPPED_READY"

    def test_al_haras_topological_kernel_boot(self):
        kernel = ALHarasTopologicalKernel("UK_DEFENCE_CYBER")
        boot = kernel.boot_kernel()
        assert boot["boot_status"] == "KERNEL_BOOT_SUCCESSFUL"
        assert boot["maclane_pentagon_coherence"] is True
        assert boot["spectral_mass_gap"]["is_spectral_gap_valid"] is True


class TestALHarasAPIRouter:
    def test_status_endpoint(self, api_client):
        resp = api_client.get("/v1/al-haras/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "OPERATIONAL"
        assert data["paradigm"] == "REMOVED_DOOR_TOPOLOGICAL_IMMUNITY"
        assert "pillars" in data
        assert data["pillars"]["ramanujan_expander_gap"]["spectral_mass_gap"] == 229.14

    def test_inspect_clean_workload(self, api_client):
        resp = api_client.post(
            "/v1/al-haras/inspect",
            json={
                "payload": "AUTHENTIC_DISPATCH_CODE",
                "passphrase": "SPEAK FRIEND AND ENTER",
                "simulate_adversarial": False,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["admitted_to_execution_fabric"] is True
        assert data["sheaf_cohomology"]["h0_harmonic_section"] is True
        assert data["dsw_instanton_self_healing"]["repair_latency_cycles"] == 0

    def test_inspect_adversarial_injection(self, api_client):
        resp = api_client.post(
            "/v1/al-haras/inspect",
            json={
                "payload": "PROMPT_INJECTION_EXPLOIT",
                "simulate_adversarial": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["admitted_to_execution_fabric"] is False
        assert data["sheaf_cohomology"]["h0_harmonic_section"] is False
        assert data["dsw_instanton_self_healing"]["cobordism_status"] == "INSTANTON_COBORDISM_TRACE_HEALED"
        assert data["dsw_instanton_self_healing"]["repair_latency_cycles"] == 1

    def test_heal_trace_endpoint(self, api_client):
        resp = api_client.post(
            "/v1/al-haras/heal",
            json={
                "trace_payload": "FAULTY_MEMORY_TRACE",
                "is_corrupted": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["healed"] is True
        assert data["healing_cycles"] == 1
        assert data["cobordism_type"] == "INSTANTON_COBORDISM_TRACE_HEALED"
