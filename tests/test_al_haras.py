"""AL HARAS (HYBA Security) API tests.

The engine mathematics is covered exactly in tests/test_al_haras_core_exact.py;
these tests exercise the HTTP surface end to end: authentication, computed
decisions, signed receipts, the repair round trip, and the absence of
certification or hardware claims.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pytest
from fastapi.testclient import TestClient

from chronus.security.al_haras import ReceiptSigner, reed_solomon
from chronus.service.app import create_app
from chronus.service.dependencies import auth_service

TOKEN = "al-haras-test-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def api_client():
    auth_service.register_tenant("al-haras-test", TOKEN)
    return TestClient(create_app())


class TestStatus:
    def test_status_is_computed_and_claims_no_certification(self, api_client):
        resp = api_client.get("/v1/al-haras/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == ("SELF_TEST_PASSED" if all(data["self_tests"].values()) else "SELF_TEST_FAILED")
        assert data["governance"]["certifications_held"] == []
        assert data["governance"]["principles_independently_assessed"] == 0
        expander = data["implemented_checks"]["expander"]
        assert expander["degree"] == 128 and expander["certified_exactly"] is True
        assert data["implemented_checks"]["receipts"].startswith("Ed25519 and ML-DSA-87 (FIPS 204)")
        assert any("FIPS 140-3" in item for item in data["not_implemented"])
        text = resp.text
        for forbidden in ("FEDRAMP_HIGH_CERTIFIED", "COMPLIANT_PASS", "OPERATIONAL", "229.14"):
            assert forbidden not in text


class TestAuthentication:
    @pytest.mark.parametrize(
        "path,body",
        [
            ("/v1/al-haras/inspect", {"payload": "x"}),
            ("/v1/al-haras/heal", {"trace_payload": "x"}),
            ("/v1/al-haras/protect", {"trace_payload": "x"}),
        ],
    )
    def test_post_endpoints_require_a_tenant_token(self, api_client, path, body):
        assert api_client.post(path, json=body).status_code == 401
        assert api_client.post(path, json=body, headers={"Authorization": "Bearer wrong"}).status_code == 401


class TestInspect:
    def test_consistent_states_are_admitted_with_a_valid_receipt(self, api_client):
        resp = api_client.post(
            "/v1/al-haras/inspect",
            headers=AUTH,
            json={"payload": "dispatch", "state_vectors": [[1, 2, 3]] * 3},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["admitted_to_execution"] is True
        assert data["sheaf_cohomology"]["status"] == "CONSISTENT"
        receipt = data["receipt"]
        assert receipt["signature"]["algorithm"] == "Ed25519 + ML-DSA-87 (both must verify)"
        assert receipt["signature"]["post_quantum"]["algorithm"] == "ML-DSA-87"
        assert ReceiptSigner.verify_ed25519(receipt["body"], receipt["signature"]) is True
        assert ReceiptSigner.verify_ml_dsa(receipt["body"], receipt["signature"]) is True
        assert ReceiptSigner.verify(receipt["body"], receipt["signature"]) is True

    def test_disagreeing_named_agent_is_located(self, api_client):
        resp = api_client.post(
            "/v1/al-haras/inspect",
            headers=AUTH,
            json={
                "payload": "turn",
                "node_names": ["Planner", "Coder", "Executor"],
                "state_vectors": [[1, 0], [5, 7], [1, 0]],
                "edges": [["Planner", "Coder"], ["Coder", "Executor"]],
            },
        )
        assert resp.status_code == 200
        sheaf = resp.json()["sheaf_cohomology"]
        assert resp.json()["admitted_to_execution"] is False
        assert sheaf["isolating_nodes"] == ["Coder"]
        assert sheaf["coboundary_max_edge_norm_sq"] == "65"  # (5-1)^2 + 7^2

    def test_exact_strings_and_tolerance(self, api_client):
        resp = api_client.post(
            "/v1/al-haras/inspect",
            headers=AUTH,
            json={"payload": "p", "state_vectors": [["1/3", 1], ["1/3", 1.0]], "tolerance": 0},
        )
        assert resp.status_code == 200 and resp.json()["admitted_to_execution"] is True

    def test_invalid_states_are_rejected_with_422(self, api_client):
        resp = api_client.post(
            "/v1/al-haras/inspect", headers=AUTH, json={"payload": "p", "state_vectors": [[1, 2], [1]]}
        )
        assert resp.status_code == 422


class TestTraceRepair:
    def test_drill_repairs_and_verifies(self, api_client):
        resp = api_client.post(
            "/v1/al-haras/heal", headers=AUTH, json={"trace_payload": "FAULTY_MEMORY_TRACE", "fault_count": 3}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["healed"] is True and data["integrity_verified"] is True
        assert sorted(data["corrected_positions"]) == sorted(data["injected_fault_positions"])
        assert "cycles" not in " ".join(data.keys())

    def test_protect_then_repair_round_trip(self, api_client):
        trace = b"AL HARAS execution trace for repair"
        envelope = api_client.post("/v1/al-haras/protect", headers=AUTH, json={"trace_payload": trace.decode()}).json()
        corrupted = reed_solomon.inject_faults(trace, [0, 5, 17])
        resp = api_client.post(
            "/v1/al-haras/repair", headers=AUTH, json={"received_hex": corrupted.hex(), "envelope": envelope}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["integrity_verified"] is True
        assert sorted(data["corrected_positions"]) == [0, 5, 17]

    def test_repair_rejects_mismatched_envelope(self, api_client):
        envelope = api_client.post("/v1/al-haras/protect", headers=AUTH, json={"trace_payload": "abc"}).json()
        resp = api_client.post(
            "/v1/al-haras/repair", headers=AUTH, json={"received_hex": b"abcd".hex(), "envelope": envelope}
        )
        assert resp.status_code == 422
