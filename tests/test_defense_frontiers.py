"""Tests for the AL HARAS capability demonstrations (formerly "4-Frontier Strategic Defense").

Every asserted value is computed by the engines; the exact, framework-free
suite is tests/test_al_haras_defense_frontiers_exact.py.
"""

import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from chronus.security.al_haras.defense_frontiers import (
    TacticalSwarmMeshEngine,
    PostQuantumSubstrateEngine,
    HyperscaleDefenseSimulationEngine,
    CNISelfHealingEngine,
)
from chronus.security.al_haras.receipts import ReceiptSigner
from chronus.service.app import create_app

pytestmark = pytest.mark.real

TOKEN = "defense-frontiers-test-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def api_client():
    from chronus.service.dependencies import auth_service

    auth_service.register_tenant("defense-frontiers-test", TOKEN)
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
        assert res["sheaf_check"]["consistent_within_tolerance"] is True
        assert res["sheaf_check"]["exactly_equal_states"] is False  # bounded noise is present
        assert res["outlier_nodes"] == []
        assert res["status"] == "CONSENSUS_WITHIN_NOISE_BOUND"

    def test_adversarial_spoof_isolated(self):
        res = TacticalSwarmMeshEngine.evaluate_swarm_mesh(
            node_count=16,
            jamming_intensity_db=60.0,
            injected_adversarial_vector=True,
        )
        assert res["sheaf_consensus_achieved"] is False
        assert res["outlier_nodes"] == ["node_08"] == [res["injected_node"]]
        assert res["repair"]["verified_within_tolerance"] is True
        assert res["status"] == "OUTLIER_ISOLATED_AND_REPLACED"


class TestFrontier2PostQuantumSubstrate:
    def test_signed_stream_receipt(self):
        packet = b"TACTICAL_TELEMETRY_PACKET"
        res = PostQuantumSubstrateEngine.generate_line_rate_ivc_receipt(
            c4isr_stream_packet=packet,
            tenant_id="tenant-a",
        )
        assert res["signature_scheme"] == (
            "Ed25519 (RFC 8032) and ML-DSA-87 (FIPS 204) over canonical JSON; both must verify"
        )
        assert res["post_quantum"] is True and res["post_quantum_algorithm"] == "ML-DSA-87"
        # FIPS 204 Table 2 sizes for ML-DSA-87, measured from the produced receipt.
        assert res["post_quantum_public_key_bytes"] == 2592 and res["post_quantum_signature_bytes"] == 4627
        assert res["packet_sha256"] == hashlib.sha256(packet).hexdigest()
        assert ReceiptSigner.verify(res["receipt"]["body"], res["receipt"]["signature"]) is True
        assert res["signature_verified"] is True and res["tampered_body_rejected"] is True
        # No validated-module claim: "FIPS 140" appears only in the not-implemented list.
        claims = {k: v for k, v in res.items() if k != "not_implemented"}
        assert "fips 140" not in json.dumps(claims).lower()
        assert any("fips 140-3" in item.lower() for item in res["not_implemented"])


class TestFrontier3HyperscaleSimulation:
    def test_exact_normal_shock_relations(self):
        res = HyperscaleDefenseSimulationEngine.execute_hypersonic_cfd_simulation(
            mach_number=2,
            state_dimensions=10,
        )
        shock = res["normal_shock"]
        assert shock["pressure_ratio_p2_p1"]["exact"] == "9/2"
        assert shock["density_ratio_rho2_rho1"]["exact"] == "8/3"
        assert shock["temperature_ratio_t2_t1"]["exact"] == "27/16"
        assert shock["downstream_mach_squared"]["exact"] == "1/3"
        assert res["lucas_number"]["value"] == "123"
        assert "dec_fluid_crossbar" not in res and "pisot_lucas_ram_footprint_bytes" not in res


class TestFrontier4CNISelfHealing:
    def test_nominal_grid_operation(self):
        res = CNISelfHealingEngine.audit_and_heal_cni_asset(
            asset_name="SOVEREIGN_GRID_NODE_A",
            simulated_cyber_physical_strike=False,
        )
        assert res["cyber_physical_strike_detected"] is False
        assert res["trace_repair"]["symbol_errors_corrected"] == 0
        assert res["trace_repair"]["integrity_verified"] is True
        assert res["trace_integrity_status"] == "NO_CORRUPTION_DETECTED"

    def test_injected_fault_is_repaired_and_verified(self):
        res = CNISelfHealingEngine.audit_and_heal_cni_asset(
            asset_name="NUCLEAR_POWER_SCADA_NODE_1",
            simulated_cyber_physical_strike=True,
        )
        repair = res["trace_repair"]
        assert res["cyber_physical_strike_detected"] is True
        assert repair["symbol_errors_corrected"] == 1
        assert repair["corrected_positions"] == repair["injected_fault_positions"]
        assert repair["integrity_verified"] is True
        assert res["trace_integrity_status"] == "TRACE_REPAIRED_AND_VERIFIED"


class TestStrategicDefenseCoordinatorAPI:
    def test_frontiers_overview_endpoint(self, api_client):
        resp = api_client.get("/v1/al-haras/frontiers")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["frontiers"]) == 4
        assert data["self_checks_all_true"] is True
        for forbidden in ("SUPREMACY", "OPERATIONAL_DEPLOYED", "FedRAMP", "JADC2", "GCHQ", "NATO"):
            assert forbidden not in resp.text

    def test_frontier_simulation_endpoints(self, api_client):
        assert api_client.post("/v1/al-haras/frontiers/simulate", json={"frontier_id": "FRONTIER_1"}).status_code == 401
        for fid in ["FRONTIER_1", "FRONTIER_2", "FRONTIER_3", "FRONTIER_4"]:
            resp = api_client.post(
                "/v1/al-haras/frontiers/simulate",
                headers=AUTH,
                json={"frontier_id": fid, "simulate_hostile_strike": False},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["frontier"].startswith(fid)
        bad = api_client.post("/v1/al-haras/frontiers/simulate", headers=AUTH, json={"frontier_id": "FRONTIER_9"})
        assert bad.status_code == 422

    def test_all_frontiers_combined_simulation(self, api_client):
        resp = api_client.post(
            "/v1/al-haras/frontiers/simulate",
            headers=AUTH,
            json={"frontier_id": "ALL"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["runs"] == 4 and data["summary"]["all_checks_true"] is True
        assert "frontier_1_swarm_consensus" in data
        assert "frontier_2_signed_receipts" in data
        assert "frontier_3_flow_relations" in data
        assert "frontier_4_trace_repair" in data
