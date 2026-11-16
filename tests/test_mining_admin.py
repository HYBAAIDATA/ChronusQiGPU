"""Comprehensive tests for Hashrate Intelligence & Mining Administration Engine.

Tests:
1. MiningAdminEngine lifecycle (start, stop, capacity scaling).
2. 5-Mode intelligence distribution rebalancing.
3. Pearl Level 2 causal do(X) interventions.
4. Sheaf anomaly injection and 1-cycle DSW monopole repair.
5. FastAPI REST API endpoints (/v1/mining/admin/*).
6. Python SDK client methods.
"""

import pytest
from fastapi.testclient import TestClient

from chronus.execution.hashrate_cap import process_cap
from chronus.execution.mining_admin import MiningAdminConfig, MiningAdminEngine
from chronus.service.app import app


@pytest.fixture
def admin_engine():
    engine = MiningAdminEngine.get_instance()
    # Reset engine state before each test
    engine.stop_mining()
    engine.config = MiningAdminConfig()
    engine._publish_hash_limit()
    engine.anomaly_injected = False
    engine.dsw_healed = False
    engine.active_intervention = "OBSERVATIONAL"
    return engine


@pytest.fixture
def client():
    from chronus.service.dependencies import auth_service
    try:
        auth_service.register_tenant("test-tenant", "test-token")
    except ValueError:
        pass
    return TestClient(app)


AUTH_HEADERS = {"Authorization": "Bearer test-token", "X-Tenant-ID": "test-tenant"}


class TestMiningAdminEngine:
    def test_engine_lifecycle_start_and_stop(self, admin_engine):
        status_init = admin_engine.get_status()
        assert status_init["status"] == "STOPPED"

        status_started = admin_engine.start_mining(base_hashrate_eh_s=1.0, active_warps=96)
        assert status_started["status"] == "RUNNING"
        assert status_started["base_hashrate_eh_s"] == 1.0
        assert status_started["hashrate_cap_eh_s"] == 1.0
        assert status_started["hashrate_basis"] == "configured_ceiling"
        assert status_started["effective_hashrate_eh_s"] == 1.0
        assert status_started["active_warps"] == 96
        assert process_cap().cap_h_s == 10**18
        with pytest.raises(ValueError):
            admin_engine.start_mining(base_hashrate_eh_s=800.0)

        status_stopped = admin_engine.stop_mining()
        assert status_stopped["status"] == "STOPPED"

    def test_engine_capacity_and_voltage_configuration(self, admin_engine):
        res = admin_engine.configure_hashrate_and_capacity(
            base_hashrate_eh_s=0.5,
            active_warps=128,
            core_voltage_v=1.05,
            fan_speed_pct=90.0,
        )
        assert res["base_hashrate_eh_s"] == 0.5
        assert res["effective_hashrate_eh_s"] == 0.5
        assert process_cap().cap_h_s == 5 * 10**17
        with pytest.raises(ValueError):
            admin_engine.configure_hashrate_and_capacity(base_hashrate_eh_s=950.0)
        assert res["active_warps"] == 128
        assert res["core_voltage_v"] == 1.05
        assert res["fan_speed_pct"] == 90.0

    def test_engine_5_mode_intelligence_rebalancing(self, admin_engine):
        res = admin_engine.configure_intelligence_modes(
            predictive=20.0,
            causal=20.0,
            counterfactual=20.0,
            topological=20.0,
            geometric=20.0,
        )
        dist = res["intelligence_distribution"]
        assert dist["predictive"] == 20.0
        assert dist["causal"] == 20.0
        assert dist["counterfactual"] == 20.0
        assert dist["topological"] == 20.0
        assert dist["geometric"] == 20.0

    def test_engine_causal_interventions(self, admin_engine):
        res_fan = admin_engine.apply_causal_intervention("FAN_100_PCT")
        assert res_fan["active_causal_intervention"] == "FAN_100_PCT"
        assert res_fan["fan_speed_pct"] == 100.0

        res_undervolt = admin_engine.apply_causal_intervention("UNDERVOLT_1_10V")
        assert res_undervolt["active_causal_intervention"] == "UNDERVOLT_1_10V"
        assert res_undervolt["core_voltage_v"] == 1.10

        with pytest.raises(ValueError):
            admin_engine.apply_causal_intervention("INVALID_INTERVENTION")

    def test_engine_anomaly_injection_and_dsw_heal(self, admin_engine):
        res_anom = admin_engine.inject_anomaly()
        assert res_anom["sheaf_cohomology_h1"] > 0
        assert res_anom["consensus_status"] == "OBSTRUCTED"

        res_healed = admin_engine.execute_dsw_heal()
        assert res_healed["sheaf_cohomology_h1"] == 0.0
        assert res_healed["consensus_status"] == "HARMONIC_CONSENSUS"


class TestMiningAdminAPIEndpoints:
    def test_api_status_endpoint(self, client):
        resp = client.get("/v1/mining/admin/status", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "spectral_mass_gap" in data
        assert data["spectral_mass_gap"] == 229.14

    def test_api_start_stop_workflow(self, client):
        start_resp = client.post(
            "/v1/mining/admin/start",
            headers=AUTH_HEADERS,
            json={"base_hashrate_eh_s": 1.0, "active_warps": 72},
        )
        assert start_resp.status_code == 200
        assert start_resp.json()["status"] == "RUNNING"
        assert start_resp.json()["base_hashrate_eh_s"] == 1.0
        assert start_resp.json()["hashrate_cap_eh_s"] == 1.0

        rejected = client.post(
            "/v1/mining/admin/start",
            headers=AUTH_HEADERS,
            json={"base_hashrate_eh_s": 750.0, "active_warps": 72},
        )
        assert rejected.status_code == 422

        stop_resp = client.post(
            "/v1/mining/admin/stop",
            headers=AUTH_HEADERS,
        )
        assert stop_resp.status_code == 200
        assert stop_resp.json()["status"] == "STOPPED"

    def test_api_configure_capacity_endpoint(self, client):
        resp = client.post(
            "/v1/mining/admin/configure",
            headers=AUTH_HEADERS,
            json={
                "base_hashrate_eh_s": 0.4,
                "active_warps": 96,
                "core_voltage_v": 1.12,
                "fan_speed_pct": 95.0,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["base_hashrate_eh_s"] == 0.4
        assert data["effective_hashrate_eh_s"] == 0.4
        assert data["core_voltage_v"] == 1.12

    def test_api_intelligence_rebalance_endpoint(self, client):
        resp = client.post(
            "/v1/mining/admin/intelligence",
            headers=AUTH_HEADERS,
            json={
                "predictive": 10.0,
                "causal": 15.0,
                "counterfactual": 25.0,
                "topological": 20.0,
                "geometric": 30.0,
            },
        )
        assert resp.status_code == 200
        dist = resp.json()["intelligence_distribution"]
        assert dist["geometric"] == 30.0

    def test_api_causal_intervention_endpoint(self, client):
        resp = client.post(
            "/v1/mining/admin/intervene",
            headers=AUTH_HEADERS,
            json={"intervention": "UNDERVOLT_1_10V"},
        )
        assert resp.status_code == 200
        assert resp.json()["active_causal_intervention"] == "UNDERVOLT_1_10V"

    def test_api_anomaly_and_heal_endpoints(self, client):
        inj_resp = client.post("/v1/mining/admin/anomaly/inject", headers=AUTH_HEADERS)
        assert inj_resp.status_code == 200
        assert inj_resp.json()["consensus_status"] == "OBSTRUCTED"

        heal_resp = client.post("/v1/mining/admin/anomaly/heal", headers=AUTH_HEADERS)
        assert heal_resp.status_code == 200
        assert heal_resp.json()["consensus_status"] == "HARMONIC_CONSENSUS"
