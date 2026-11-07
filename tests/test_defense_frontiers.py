"""Tests for AL HARAS 4-Frontier Strategic Defense Operations."""

import pytest
from fastapi.testclient import TestClient

from chronus.security.al_haras.defense_frontiers import (
    TacticalSwarmMeshEngine,
    PostQuantumSubstrateEngine,
    HyperscaleDefenseSimulationEngine,
    CNISelfHealingEngine,
    StrategicDefenseCoordinator,
)
from chronus.service.app import create_app


@pytest.fixture
def api_client():
    app = create_app()
    return TestClient(app)


class TestFrontier1TacticalSwarmMesh:
    def test_clean_tactical_swarm_consensus(self):
        res = TacticalSwarmMeshEngine.evaluate_swarm_mesh(
            node_count=16,
            jamming_intensity_db=30.0,
            injected_adversarial_vector=False,
        )
        assert res["sheaf_consensus_achieved"] is True
        assert res["sheaf_cohomology"]["h0_consensus"] is True
        assert res["operational_status"] == "TACTICAL_HARMONIC_CONSENSUS_LOCKED"
        assert res["cyclotomic_topological_braids"]["zero_float_truncation"] is True

    def test_adversarial_spoof_isolated(self):
        res = TacticalSwarmMeshEngine.evaluate_swarm_mesh(
            node_count=16,
            jamming_intensity_db=60.0,
            injected_adversarial_vector=True,
        )
        assert res["sheaf_consensus_achieved"] is False
        assert res["sheaf_cohomology"]["h0_consensus"] is False
        assert res["operational_status"] == "ADVERSARIAL_SPOOF_ISOLATED"


class TestFrontier2PostQuantumSubstrate:
    def test_line_rate_ivc_receipt_fips_204(self):
        res = PostQuantumSubstrateEngine.generate_line_rate_ivc_receipt(
            c4isr_stream_packet=b"TACTICAL_TELEMETRY_NATO_FiveEyes",
            tenant_id="NATO_HQ_BRUSSELS",
        )
        assert res["standard"] == "NIST FIPS 204 (ML-DSA) & FRI zk-STARK"
        assert res["mldsa_lattice_signature"].startswith("mldsa87_")
        assert res["fri_stark_quotient"]["vanishing_polynomial_status"] == "P(x)/Z_H(x) QUOTIENT_SATISFIED"
        assert len(res["packet_sha256"]) == 64


class TestFrontier3HyperscaleSimulation:
    def test_hypersonic_cfd_pisot_lucas_collapse(self):
        res = HyperscaleDefenseSimulationEngine.execute_hypersonic_cfd_simulation(
            mach_number=12.5,
            state_dimensions=479,
        )
        assert res["pisot_lucas_ram_footprint_bytes"] == 64
        assert res["dec_fluid_crossbar"]["zero_stall_guaranteed"] is True
        assert res["dec_fluid_crossbar"]["dma_packet_stalls"] == 0
        assert res["dec_fluid_crossbar"]["bus_saturation_pct"] == 100.0


class TestFrontier4CNISelfHealing:
    def test_nominal_grid_operation(self):
        res = CNISelfHealingEngine.audit_and_heal_cni_asset(
            asset_name="SOVEREIGN_GRID_NODE_A",
            simulated_cyber_physical_strike=False,
        )
        assert res["cyber_physical_strike_detected"] is False
        assert res["dsw_instanton_monopole"]["instanton_number_k"] == 0
        assert res["dsw_instanton_monopole"]["healing_cycles"] == 0
        assert res["cni_defense_posture"] == "NOMINAL_STABLE_GRID_OPERATION"

    def test_cyber_physical_strike_1cycle_healing(self):
        res = CNISelfHealingEngine.audit_and_heal_cni_asset(
            asset_name="NUCLEAR_POWER_SCADA_NODE_1",
            simulated_cyber_physical_strike=True,
        )
        assert res["cyber_physical_strike_detected"] is True
        assert res["dsw_instanton_monopole"]["instanton_number_k"] == 1
        assert res["dsw_instanton_monopole"]["healing_cycles"] == 1
        assert res["dsw_instanton_monopole"]["context_rollback_bytes"] == 0
        assert res["cni_defense_posture"] == "TOPOLOGICALLY_HEALED_UNINTERRUPTED_OPERATION"


class TestStrategicDefenseCoordinatorAPI:
    def test_frontiers_overview_endpoint(self, api_client):
        resp = api_client.get("/v1/al-haras/frontiers")
        assert resp.status_code == 200
        data = resp.json()
        assert data["strategic_posture"] == "TOPOLOGICAL_DEFENSE_SUPREMACY"
        assert len(data["operational_frontiers"]) == 4

    def test_frontier_simulation_endpoints(self, api_client):
        for fid in ["FRONTIER_1", "FRONTIER_2", "FRONTIER_3", "FRONTIER_4"]:
            resp = api_client.post(
                "/v1/al-haras/frontiers/simulate",
                json={"frontier_id": fid, "simulate_hostile_strike": False},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "frontier" in data

    def test_all_frontiers_combined_simulation(self, api_client):
        resp = api_client.post(
            "/v1/al-haras/frontiers/simulate",
            json={"frontier_id": "ALL"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["strategic_summary"] == "ALL_4_DEFENSE_FRONTIERS_MISSION_QUALIFIED"
        assert "frontier_1_jadc2_swarm" in data
        assert "frontier_2_gchq_pqc" in data
        assert "frontier_3_darpa_hyperscale" in data
        assert "frontier_4_nato_cni" in data
