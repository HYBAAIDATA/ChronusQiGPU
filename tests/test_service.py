"""Tests for the Chronus service API and mathematical reference execution."""

import pytest
from fastapi.testclient import TestClient

from chronus.execution import NativeMathReferenceBackend
from chronus.service.app import create_app
from chronus.service.dependencies import auth_service, service_config
from chronus.service.routers import workloads
from chronus.service.models import (
    WorkloadRequest,
    WorkloadResponse,
    WorkloadStatus,
    HealthResponse,
    HealthStatus,
    VerificationResult,
)
from chronus.service.workload_store import SQLiteWorkloadStore


class TestServiceModels:
    """Tests for service data models."""

    def test_workload_request_model(self):
        """Test WorkloadRequest model validation."""
        request = WorkloadRequest(
            payload_bytes=b"test payload",
            tenant_id="test-tenant",
            workload_type="QUANTUM_CHEMISTRY_VQE",
        )
        assert request.payload_bytes == b"test payload"
        assert request.tenant_id == "test-tenant"
        assert request.workload_type == "QUANTUM_CHEMISTRY_VQE"

    def test_workload_request_validator(self):
        """Test WorkloadRequest validators."""
        with pytest.raises(ValueError):
            WorkloadRequest(
                payload_bytes=b"",
                tenant_id="test-tenant",
                workload_type="TEST",
            )

    def test_workload_response_model(self):
        """Test WorkloadResponse model serialization."""
        response = WorkloadResponse(
            workload_id="00000000-0000-0000-0000-000000000001",
            status="SUBMITTED",
            workload_type="EXACT_Q5_ALGEBRAIC",
            representation_mode="EXACT_Q5_RATIONAL",
            priority="HIGH",
            tenant_id="test",
            region="us-east-1",
        )
        data = response.model_dump()
        assert str(data["workload_id"]) == "00000000-0000-0000-0000-000000000001"
        assert data["status"] == "SUBMITTED"

    def test_health_response_model(self):
        """Test HealthResponse model."""
        health = HealthResponse(
            status=HealthStatus.HEALTHY,
            components=[],
            uptime_seconds=0.0,
            total_workloads=0,
            active_workloads=0,
        )
        assert health.status == HealthStatus.HEALTHY
        assert health.version == "36.0.1"

    def test_base64_wire_payload_preserves_binary_bytes(self):
        request = WorkloadRequest(
            payload_bytes="base64:/wA=",
            tenant_id="test-tenant",
            workload_type="EXACT_Q5_ALGEBRAIC",
        )
        assert request.payload_bytes == b"\xff\x00"
        assert WorkloadRequest.model_validate_json(request.model_dump_json()).payload_bytes == b"\xff\x00"

    def test_verification_result_does_not_imply_release_qualification(self):
        result = VerificationResult()
        assert result.qualification_status == "NOT_A_RELEASE_QUALIFICATION"
        assert result.total_release_gates_evaluated == 0
        assert result.total_invariants_evaluated == 0

    def test_sqlite_workload_store_survives_reopen(self, tmp_path):
        workload = WorkloadResponse(
            workload_id="00000000-0000-0000-0000-000000000002",
            status="COMPLETED",
            workload_type="LUCAS_PV_SCALING",
            representation_mode="PV_LUCAS_COLLAPSE",
            priority="HIGH",
            tenant_id="persisted-tenant",
            region="us-east-1",
        )
        path = str(tmp_path / "workloads.sqlite3")
        SQLiteWorkloadStore(path).save(workload)
        reopened = SQLiteWorkloadStore(path)
        stored = reopened.get(str(workload.workload_id))
        assert stored is not None
        assert stored.tenant_id == "persisted-tenant"
        assert stored.status == WorkloadStatus.COMPLETED

    def test_lucas_pv_exact_reference_identity(self):
        result = NativeMathReferenceBackend().execute(
            b'{"index":10}', "LUCAS_PV_SCALING"
        )
        assert result["fibonacci"] == "55"
        assert result["lucas"] == "123"
        assert result["identity_verified"] is True

    def test_lucas_large_result_is_json_safe(self):
        result = NativeMathReferenceBackend().execute(
            b'{"index":22000}', "LUCAS_PV_SCALING"
        )
        assert len(result["lucas"]) > 4300
        assert result["identity_verified"] is True

    def test_q5_multiplication_is_exact(self):
        result = NativeMathReferenceBackend().execute(
            b'{"operation":"multiply","left":{"rational":[1,1],"sqrt5":[1,1]},'
            b'"right":{"rational":[1,1],"sqrt5":[-1,1]}}',
            "EXACT_Q5_ALGEBRAIC",
        )
        assert result["result"]["rational"] == [-4, 1]
        assert result["result"]["sqrt5"] == [0, 1]


class TestServiceAPI:
    @pytest.fixture(autouse=True)
    def setup_api(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            workloads, "workload_store", SQLiteWorkloadStore(str(tmp_path / "test.sqlite3"))
        )
        monkeypatch.setattr(service_config, "execution_backend_url", None)
        self.client = TestClient(create_app())
        yield
        self.client.close()

    def test_health_reports_actual_unconfigured_backend(self):
        service_config.execution_backend_url = None
        response = self.client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "HEALTHY"
        backend = next(c for c in body["components"] if c["name"] == "execution_backend")
        assert backend["details"]["mode"] == "native-reference"
        assert "python-math-reference" in backend["details"]["registered_backends"]
        qigpu = backend["details"]["qigpu"]
        assert qigpu["hardware_agnostic"] is True
        assert qigpu["default_surface"] == "python-math-reference"
        assert body["total_workloads"] == 0

    def test_readiness_for_native_reference_backend(self):
        service_config.execution_backend_url = None
        response = self.client.get("/health/ready")
        assert response.status_code == 200
        assert response.json()["execution_mode"] == "native-reference"

    def test_workload_submission_rejects_unregistered_credentials(self):
        response = self.client.post(
            "/workloads/submit",
            headers={"Authorization": "Bearer forged:token"},
            json={
                "payload_bytes": "base64:d29ya2xvYWQ=",
                "tenant_id": "forged",
                "workload_type": "EXACT_Q5_ALGEBRAIC",
            },
        )
        assert response.status_code == 401

    def test_bad_base64_payload_returns_validation_error(self):
        auth_service.register_tenant("service-test", "service-test-token")
        response = self.client.post(
            "/workloads/submit",
            headers={"Authorization": "Bearer service-test-token"},
            json={
                "payload_bytes": "base64:!",
                "tenant_id": "service-test",
                "workload_type": "EXACT_Q5_ALGEBRAIC",
            },
        )
        assert response.status_code == 422

    def test_lucas_workload_executes_on_native_reference_backend(self):
        service_config.execution_backend_url = None
        auth_service.register_tenant("service-test", "service-test-token")
        response = self.client.post(
            "/workloads/submit",
            headers={"Authorization": "Bearer service-test-token"},
            json={
                "payload_bytes": "base64:eyJpbmRleCI6MTB9",
                "tenant_id": "service-test",
                "workload_type": "LUCAS_PV_SCALING",
                "representation_mode": "PV_LUCAS_COLLAPSE",
            },
        )
        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "COMPLETED"
        assert body["result"]["backend"] == "python-math-reference"
        assert body["result"]["execution_state"] == "EXECUTED"
        assert body["result"]["result"]["lucas"] == "123"
        auth_service.register_tenant("other-service-test", "other-service-test-token")
        denied = self.client.get(
            f"/workloads/{body['workload_id']}",
            headers={"Authorization": "Bearer other-service-test-token"},
        )
        assert denied.status_code == 403

    def test_pv_lattice_cpu_result_persists(self):
        auth_service.register_tenant("service-test", "service-test-token")
        response = self.client.post(
            "/workloads/submit",
            headers={"Authorization": "Bearer service-test-token"},
            json={
                "payload_bytes": '{"order":90,"values":[{"a":"1","b":"0","denominator":"1"}]}',
                "tenant_id": "service-test",
                "workload_type": "PV_LATTICE_FOLD",
            },
        )
        assert response.status_code == 202
        body = response.json()
        result = body["result"]
        assert result["execution_mode"] == "NATIVE_CPU_REFERENCE"
        assert result["result"]["device_signature"] is None
        assert result["result"]["norm_invariant_verified"] is True
        assert result["result"]["values"][0]["b"] == "2880067194370816120"
        stored = self.client.get(
            f"/workloads/{body['workload_id']}",
            headers={"Authorization": "Bearer service-test-token"},
        )
        assert stored.status_code == 200
        assert stored.json()["result"] == result

    def test_phyllotaxis_store_and_theseus_retrieve_api(self):
        auth_service.register_tenant("service-test", "service-test-token")
        store = self.client.post(
            "/workloads/submit",
            headers={"Authorization": "Bearer service-test-token"},
            json={
                "payload_bytes": '{"data":"base64:Z29sZGVu","tenant_id":"service-test"}',
                "tenant_id": "service-test",
                "workload_type": "PHYLOTAXIS_STORE",
            },
        )
        assert store.status_code == 202
        record = store.json()["result"]["result"]["theseus_record"]
        assert 0 <= record["coordinate"]["lane"] < 32
        retrieve = self.client.post(
            "/workloads/submit",
            headers={"Authorization": "Bearer service-test-token"},
            json={
                "payload_bytes": '{"object_id":"%s","tenant_id":"service-test"}' % record["object_id"],
                "tenant_id": "service-test",
                "workload_type": "THESEUS_RETRIEVE",
            },
        )
        assert retrieve.status_code == 202
        result = retrieve.json()["result"]["result"]
        assert result["digest_verified"] is True
        assert result["data"] == "base64:Z29sZGVu"

    def test_auto_backend_preference_and_console_dashboard(self):
        auth_service.register_tenant("service-test", "service-test-token")
        response = self.client.post(
            "/workloads/submit",
            headers={"Authorization": "Bearer service-test-token"},
            json={
                "payload_bytes": '{"index":10}',
                "tenant_id": "service-test",
                "workload_type": "LUCAS_PV_SCALING",
                "backend_preference": "auto",
            },
        )
        assert response.status_code == 202
        assert response.json()["result"]["backend"] == "python-math-reference"
        console = self.client.get(
            "/console", headers={"Authorization": "Bearer service-test-token"}
        )
        assert console.status_code == 200
        assert "Sovereign Control Plane" in console.text
        assert "python-math-reference" in console.text
        denied = self.client.get("/console")
        assert denied.status_code in (401, 403)

    def test_billing_usage_receipt_is_signed_and_tenant_scoped(self):
        auth_service.register_tenant("service-test", "service-test-token")
        self.client.post(
            "/workloads/submit",
            headers={"Authorization": "Bearer service-test-token"},
            json={
                "payload_bytes": '{"index":10}',
                "tenant_id": "service-test",
                "workload_type": "LUCAS_PV_SCALING",
            },
        )
        response = self.client.get(
            "/billing/usage", headers={"Authorization": "Bearer service-test-token"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["usage"]["workloads_completed"] >= 1
        assert "LUCAS_PV_SCALING" in body["usage"]["by_type"]
        from chronus.service.routers.verify import _ed25519_signer
        assert _ed25519_signer.verify(body["digest"].encode("ascii"), body["signature"])
        unauthenticated = self.client.get("/billing/usage")
        assert unauthenticated.status_code in (401, 403)

    def test_trinity_symbolic_workload_api(self):
        auth_service.register_tenant("service-test", "service-test-token")
        response = self.client.post(
            "/workloads/submit",
            headers={"Authorization": "Bearer service-test-token"},
            json={
                "payload_bytes": '{"increment":4781,"values":[{"a":1,"b":0,"denominator":1}]}',
                "tenant_id": "service-test",
                "workload_type": "TRINITY_SCALE_FOLD_STORE",
            },
        )
        assert response.status_code == 202
        result = response.json()["result"]["result"]
        assert result["state"]["scale_index"] == 4781
        assert result["cassini_verified"] is False

    def test_receipt_is_signed_and_verified_without_release_claim(self):
        unauthenticated = self.client.post(
            "/verify/receipt?hash_value=receipt-payload"
        )
        assert unauthenticated.status_code == 401
        auth_service.register_tenant("receipt-test", "receipt-test-token")
        created = self.client.post(
            "/verify/receipt?hash_value=receipt-payload",
            headers={"Authorization": "Bearer receipt-test-token"},
        )
        assert created.status_code == 200
        receipt_id = created.json()["receipt_id"]
        verified = self.client.get(f"/verify/{receipt_id}")
        assert verified.status_code == 200
        assert verified.json()["qualification_status"] == "VERIFIED"
        assert verified.json()["total_release_gates_evaluated"] == 0

    def test_workload_receipt_uses_shared_ed25519_key_and_no_fake_proof(self):
        auth_service.register_tenant("receipt-workload", "receipt-workload-token")
        submitted = self.client.post(
            "/workloads/submit",
            headers={"Authorization": "Bearer receipt-workload-token"},
            json={
                "payload_bytes": '{"index":10}',
                "tenant_id": "receipt-workload",
                "workload_type": "LUCAS_PV_SCALING",
            },
        )
        assert submitted.status_code == 202
        receipt_handle = submitted.json()["verification_receipt"]
        verified = self.client.get(f"/verify/{receipt_handle}")
        assert verified.status_code == 200
        body = verified.json()
        assert body["qualification_status"] == "VERIFIED"
        assert body["ed25519_verified"] is True
        assert body["ml_dsa_verified"] is False
        assert body["stark_quotient_verified"] is False
        assert "not a release qualification" in body["invariant_summary"]

    def test_mldsa_receipt_request_fails_closed(self):
        auth_service.register_tenant("receipt-test-mldsa", "receipt-test-mldsa-token")
        response = self.client.post(
            "/verify/receipt?hash_value=receipt-payload&use_ml_dsa=true",
            headers={"Authorization": "Bearer receipt-test-mldsa-token"},
        )
        assert response.status_code == 501
        assert response.json()["detail"]["error"] == "algorithm_unavailable"


    def test_capabilities_endpoint_reports_inventory_not_qualification(self):
        response = self.client.get("/v1/capabilities")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "inventory_only"
        assert body["measurement_scope"] == "process-local"
        assert body["release_qualification"] == "not_assessed"
        assert "purity_gate" not in body
        assert "hardware_abstraction" not in body

    def test_capacity_endpoint_exposes_observed_counters_only(self):
        response = self.client.get("/v1/capacity")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "observed"
        assert body["measurement_scope"] == "process-local"
        assert "workloads" in body
        assert "ccu" not in body
        assert "hardware_pool" not in body
        assert "qualification_note" in body
