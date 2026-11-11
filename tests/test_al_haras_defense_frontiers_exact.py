"""Exact tests for the AL HARAS capability demonstrations (no web framework needed).

Known answers are derived independently here: textbook normal-shock values at
Mach 2, conservation identities of the shock jump, a Lucas recurrence loop, a
recomputation of the SHA-256 noise model, and Ed25519 verification of the
returned receipts. Mutation tests show that a wrong engine is caught.
"""

import hashlib
import json
import os
import re
import sys
from datetime import datetime
from fractions import Fraction

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pytest

from chronus.security.al_haras import golden
from chronus.security.al_haras.defense_frontiers import (
    CNISelfHealingEngine,
    HyperscaleDefenseSimulationEngine,
    PostQuantumSubstrateEngine,
    StrategicDefenseCoordinator,
    TacticalSwarmMeshEngine,
)
from chronus.security.al_haras.receipts import ReceiptSigner

BANNED_LABELS = [
    "Pentagon", "JADC2", "GCHQ", "NCSC", "DARPA", "NATO", "Five Eyes", "FIVE_EYES", "FedRAMP", "IL6",
    "OPERATIONAL_DEPLOYED", "SUPREMACY", "MISSION_QUALIFIED", "CERTIFIED", "mldsa87_", "EXASCALE", "1-Cycle", "1_CYCLE",
]


def _assert_no_theatre(result):
    text = json.dumps(result)
    for label in BANNED_LABELS:
        assert label not in text, label
    assert not re.search(r"\bNSA\b", text)


class TestSwarmConsensus:
    def test_noise_is_real_and_the_tolerance_is_the_exact_bound(self):
        res = TacticalSwarmMeshEngine.evaluate_swarm_mesh(node_count=16, jamming_intensity_db=30.0, injected_adversarial_vector=False)
        bound = Fraction(30, 1000)
        assert res["tolerance"]["edge_residual_norm_sq_max"] == str(4 * bound * bound * 8) == "18/625"
        assert res["sheaf_check"]["exactly_equal_states"] is False  # exact equality would reject these honest nodes
        worst = Fraction(res["sheaf_check"]["max_edge_residual_norm_sq"])
        assert 0 < worst <= Fraction(18, 625)
        assert res["sheaf_consensus_achieved"] is True and res["outlier_nodes"] == []
        assert res["status"] == "CONSENSUS_WITHIN_NOISE_BOUND"
        _assert_no_theatre(res)

    def test_injected_node_is_isolated_and_replaced_by_the_exact_mean(self):
        res = TacticalSwarmMeshEngine.evaluate_swarm_mesh(node_count=16, jamming_intensity_db=60.0, injected_adversarial_vector=True)
        assert res["sheaf_consensus_achieved"] is False
        assert res["injected_node"] == "node_08" and res["outlier_nodes"] == ["node_08"]
        assert res["sheaf_check"]["edges_over_tolerance"] == [["node_07", "node_08"], ["node_08", "node_09"]]
        # independent recomputation of the noise model and of the replacement
        bound = Fraction(1, 20)  # min(60/1000, 1/20)
        reference = [golden.fibonacci(k) for k in range(2, 10)]
        assert reference == [1, 2, 3, 5, 8, 13, 21, 34]

        def noise(i, d):
            h = hashlib.sha256(f"swarm-noise:{i}:{d}".encode()).digest()[0]
            return bound * Fraction(2 * h - 255, 255)

        mean = [sum(reference[d] + noise(i, d) for i in range(16) if i != 8) / 15 for d in range(8)]
        assert res["repair"]["replacement_state"] == [str(x) for x in mean]
        assert res["repair"]["verified_within_tolerance"] is True
        assert res["status"] == "OUTLIER_ISOLATED_AND_REPLACED"

    def test_zero_jamming_demands_exact_agreement(self):
        res = TacticalSwarmMeshEngine.evaluate_swarm_mesh(node_count=8, jamming_intensity_db=0)
        assert res["tolerance"]["edge_residual_norm_sq_max"] == "0"
        assert res["sheaf_check"]["exactly_equal_states"] is True and res["sheaf_consensus_achieved"] is True

    def test_invalid_inputs_are_rejected(self):
        with pytest.raises(ValueError):
            TacticalSwarmMeshEngine.evaluate_swarm_mesh(node_count=1)
        two = TacticalSwarmMeshEngine.evaluate_swarm_mesh(node_count=2, injected_adversarial_vector=True)
        assert two["outlier_nodes"] == ["node_00", "node_01"] and two["status"] == "DISAGREEMENT_NOT_LOCALISED"
        with pytest.raises(ValueError):
            TacticalSwarmMeshEngine.evaluate_swarm_mesh(jamming_intensity_db=-1)


class TestSignedReceipts:
    def test_receipt_verifies_and_is_bound_to_packet_and_tenant(self):
        res = PostQuantumSubstrateEngine.generate_line_rate_ivc_receipt(c4isr_stream_packet=b"P1", tenant_id="tenant-a")
        body, signature = res["receipt"]["body"], res["receipt"]["signature"]
        assert ReceiptSigner.verify(body, signature) is True
        assert body["packet_sha256"] == hashlib.sha256(b"P1").hexdigest() == res["packet_sha256"]
        altered = dict(body, tenant_id="tenant-b")
        assert ReceiptSigner.verify(altered, signature) is False
        assert res["signature_verified"] is True and res["tampered_body_rejected"] is True
        assert res["post_quantum"] is True and signature["algorithm"] == "Ed25519 + ML-DSA-87 (both must verify)"
        assert ReceiptSigner.verify_ml_dsa(body, signature) is True and ReceiptSigner.verify_ed25519(body, signature) is True
        assert ReceiptSigner.verify_ml_dsa(altered, signature) is False
        assert "HSM" in res["key_custody"] and "not HSM-backed" in res["key_custody"]
        text = json.dumps(res).lower()
        assert "immune" not in text and "o(1)" not in text
        # The only FIPS 140 mention is the statement that no validated module is claimed.
        assert text.count("fips 140") == 1 and "not_implemented" in res and any("fips 140-3" in item.lower() for item in res["not_implemented"])
        _assert_no_theatre(res)


class TestNormalShockRelations:
    def test_mach_2_textbook_values(self):
        res = HyperscaleDefenseSimulationEngine.execute_hypersonic_cfd_simulation(mach_number=2, state_dimensions=10)
        shock = res["normal_shock"]
        assert shock["pressure_ratio_p2_p1"]["exact"] == "9/2"
        assert shock["density_ratio_rho2_rho1"]["exact"] == "8/3"
        assert shock["temperature_ratio_t2_t1"]["exact"] == "27/16"
        assert shock["downstream_mach_squared"]["exact"] == "1/3"
        assert shock["downstream_mach"]["decimal"] == "0.577350"
        assert shock["stagnation_to_static_temperature_t0_t1"]["exact"] == "9/5"
        assert shock["density_ratio_limit_large_mach"]["exact"] == "6"
        assert res["status"] == "NORMAL_SHOCK_RELATIONS_COMPUTED"

    def test_jump_conditions_hold_exactly_at_mach_12_5(self):
        g, mach = Fraction(7, 5), Fraction(25, 2)
        r = HyperscaleDefenseSimulationEngine.normal_shock_ratios(mach, g)
        m2, p, rho, t = mach * mach, r["pressure_ratio_p2_p1"], r["density_ratio_rho2_rho1"], r["temperature_ratio_t2_t1"]
        assert p == Fraction(1457, 8)
        assert p == 1 + g * m2 * (1 - 1 / rho)  # momentum: p1 + rho1 u1^2 = p2 + rho2 u2^2
        assert r["downstream_mach_squared"] == m2 / (rho * rho * t)  # mass: rho1 u1 = rho2 u2
        assert r["stagnation_to_static_temperature_t0_t1"] == t * (1 + (g - 1) / 2 * r["downstream_mach_squared"])  # energy
        k = (g + 1) / (g - 1)
        assert p == (k * rho - 1) / (k - rho)  # Rankine-Hugoniot shock adiabat

    def test_no_shock_at_or_below_mach_1(self):
        res = HyperscaleDefenseSimulationEngine.execute_hypersonic_cfd_simulation(mach_number=0.8)
        assert res["normal_shock"] is None and res["status"] == "NO_NORMAL_SHOCK_AT_MACH_1_OR_BELOW"

    def test_lucas_numbers_are_exact(self):
        a, b = 2, 1
        for _ in range(479):
            a, b = b, a + b
        res = HyperscaleDefenseSimulationEngine.execute_hypersonic_cfd_simulation(state_dimensions=479)
        assert res["lucas_number"]["value"] == str(a) and res["lucas_number"]["decimal_digits"] == len(str(a))
        assert res["lucas_number"]["binet_identity_verified"] is True
        zero = HyperscaleDefenseSimulationEngine.execute_hypersonic_cfd_simulation(mach_number=5, state_dimensions=0)
        assert zero["lucas_number"]["value"] == "2"

    def test_nothing_is_presented_as_cfd_or_memory_compression(self):
        res = HyperscaleDefenseSimulationEngine.execute_hypersonic_cfd_simulation()
        for removed in ("dec_fluid_crossbar", "pisot_lucas_ram_footprint_bytes", "silicon_bypass_factor", "state_space_dimension"):
            assert removed not in res
        assert "not a CFD simulation" in res["capability"]
        _assert_no_theatre(res)

    def test_invalid_inputs_are_rejected(self):
        for kwargs in ({"mach_number": 0}, {"mach_number": 101}, {"gamma": 2}, {"state_dimensions": -1}, {"state_dimensions": 10_001}):
            with pytest.raises(ValueError):
                HyperscaleDefenseSimulationEngine.execute_hypersonic_cfd_simulation(**kwargs)


class TestTraceRepair:
    def test_nominal_trace_has_nothing_to_repair(self):
        res = CNISelfHealingEngine.audit_and_heal_cni_asset(asset_name="SOVEREIGN_GRID_NODE_A")
        assert res["cyber_physical_strike_detected"] is False
        assert res["trace_repair"]["symbol_errors_corrected"] == 0 and res["trace_repair"]["integrity_verified"] is True
        assert res["trace_integrity_status"] == "NO_CORRUPTION_DETECTED"

    def test_injected_faults_are_located_corrected_and_verified(self):
        res = CNISelfHealingEngine.audit_and_heal_cni_asset(
            asset_name="NUCLEAR_POWER_SCADA_NODE_1", simulated_cyber_physical_strike=True, fault_count=3
        )
        repair = res["trace_repair"]
        assert sorted(repair["corrected_positions"]) == sorted(repair["injected_fault_positions"])
        assert repair["symbol_errors_corrected"] == 3 and repair["integrity_verified"] is True
        assert repair["repaired_trace_sha256"] == repair["trace_sha256"]
        assert res["cyber_physical_strike_detected"] is True
        assert res["trace_integrity_status"] == "TRACE_REPAIRED_AND_VERIFIED"

    def test_corruption_beyond_capacity_is_reported_not_hidden(self):
        # 30 faults in a 63-byte trace put at least 15 in one 32-byte block; RS(48, 32) corrects 8.
        res = CNISelfHealingEngine.audit_and_heal_cni_asset(simulated_cyber_physical_strike=True, fault_count=30)
        assert res["trace_repair"]["integrity_verified"] is False
        assert res["trace_integrity_status"] == "UNCORRECTABLE_CORRUPTION"
        assert res["cyber_physical_strike_detected"] is True

    def test_no_fabricated_compliance_or_custody_fields(self):
        res = CNISelfHealingEngine.audit_and_heal_cni_asset(simulated_cyber_physical_strike=True)
        for removed in ("ncsc_principles_passed", "key_custody", "dsw_instanton_monopole", "cni_defense_posture"):
            assert removed not in res
        _assert_no_theatre(res)


class TestCoordinator:
    def test_overview_is_neutral_and_its_checks_are_computed(self):
        overview = StrategicDefenseCoordinator.get_strategic_posture_overview()
        assert [f["frontier_id"] for f in overview["frontiers"]] == ["FRONTIER_1", "FRONTIER_2", "FRONTIER_3", "FRONTIER_4"]
        assert overview["self_checks_all_true"] is True and all(overview["self_checks"].values())
        for removed in ("strategic_posture", "operational_frontiers", "governance_compliance", "production_gate"):
            assert removed not in overview
        _assert_no_theatre(overview)

    def test_self_check_catches_a_broken_engine(self, monkeypatch):
        def wrong(mach, gamma):
            return {
                "pressure_ratio_p2_p1": Fraction(5),
                "density_ratio_rho2_rho1": Fraction(8, 3),
                "temperature_ratio_t2_t1": Fraction(27, 16),
                "downstream_mach_squared": Fraction(1, 3),
            }

        monkeypatch.setattr(HyperscaleDefenseSimulationEngine, "normal_shock_ratios", staticmethod(wrong))
        checks = StrategicDefenseCoordinator.self_checks()
        assert checks["frontier_3_mach_2_known_answer"] is False
        assert checks["frontier_1_injected_outlier_located"] is True

    def test_run_all_returns_four_computed_runs(self):
        res = StrategicDefenseCoordinator.run_all_frontier_simulations()
        assert res["summary"]["runs"] == 4 and res["summary"]["all_checks_true"] is True
        assert res["frontier_1_swarm_consensus"]["frontier"] == "FRONTIER_1_SWARM_STATE_CONSENSUS"
        assert res["frontier_2_signed_receipts"]["frontier"] == "FRONTIER_2_SIGNED_STREAM_RECEIPTS"
        assert res["frontier_3_flow_relations"]["frontier"] == "FRONTIER_3_EXACT_FLOW_RELATIONS"
        assert res["frontier_4_trace_repair"]["frontier"] == "FRONTIER_4_TRACE_REPAIR"
        datetime.fromisoformat(res["timestamp"])
        _assert_no_theatre(res)
        StrategicDefenseCoordinator()  # still constructible without arguments (SecurityContext)
