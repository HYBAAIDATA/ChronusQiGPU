"""Comprehensive unit & integration tests for Zero-Copy Native Representation Connectors.

Verifies:
1. In-Place Zero-Copy Pointers (ptr_ovid_<hash>) with data_stays_at_rest=True & 0 staging bytes
2. Binet-Zeckendorf Ingress Engine across Parquet, ORC, Gzip, Delta Lake, JSON, and Raw Binary
3. Explicit T3-T5 Data Movement Plane (LOCAL_ZERO_COPY, REMOTE_REFERENCE, REMOTE_TRANSFER DEC fluid)
4. AL HARAS Sheaf Cohomology H^1(X; F) Zero-Trust Edge & Customer KMS / PKCS#11 RAM Custody
5. Enduring Capacity Addendum (ECA), Automated Schema Discovery Middleware, FastAPI & SDK surfaces
"""

import base64
import gzip
import hashlib
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from chronus.execution.reference import NativeMathReferenceBackend
from chronus.sdk.client import ChronusAPISDK
from chronus.sdk.models import AuthorizationError
from chronus.security.kms import al_haras_kms_custody
from chronus.security.ovid import OVIDStorage, POINTER_PREFIX, VerifyEndpoint
from chronus.security.signers import Ed25519Signer, MLDSASigner
from chronus.service.app import create_app
from chronus.service.dependencies import auth_service, service_config
from chronus.service.routers import workloads
from chronus.service.workload_store import SQLiteWorkloadStore
from chronus.storage.connectors import (
    BinetZeckendorfIngressEngine,
    ConnectorCategory,
    ConnectorSecurityError,
    ConnectorType,
    DataMovementPlaneRouter,
    IngestFormat,
    MemoryAccessClass,
    PREBUILT_CONNECTOR_SPECS,
    ZeroCopyConnectorManager,
    classify_memory_access_class,
)


class TestZeroCopyPrimitives:
    def test_all_enterprise_and_hyperscaler_connector_specs_present(self):
        expected = {
            "AWS_S3": ConnectorCategory.CLOUD_OBJECT_STORE.value,
            "AZURE_BLOB": ConnectorCategory.CLOUD_OBJECT_STORE.value,
            "AZURE_ONELAKE": ConnectorCategory.CLOUD_OBJECT_STORE.value,
            "GCP_GCS": ConnectorCategory.CLOUD_OBJECT_STORE.value,
            "SNOWFLAKE": ConnectorCategory.ENTERPRISE_DATA_WAREHOUSE.value,
            "DATABRICKS": ConnectorCategory.ENTERPRISE_DATA_WAREHOUSE.value,
            "BIGQUERY": ConnectorCategory.ENTERPRISE_DATA_WAREHOUSE.value,
            "POSTGRESQL": ConnectorCategory.LEGACY_ON_PREMISES.value,
            "SAN": ConnectorCategory.LEGACY_ON_PREMISES.value,
            "HDFS": ConnectorCategory.LEGACY_ON_PREMISES.value,
            "NVIDIA_DGX_CLOUD": ConnectorCategory.AI_FACTORY_FABRIC.value,
            "PALANTIR_FOUNDRY": ConnectorCategory.SOVEREIGN_DEFENSE_HUB.value,
        }
        assert set(PREBUILT_CONNECTOR_SPECS.keys()) == set(expected.keys())
        for key, cat in expected.items():
            spec = PREBUILT_CONNECTOR_SPECS[key]
            assert spec["category"] == cat
            assert "ptr_ovid_" in spec["pointer_architecture"]

    def test_ovid_zero_copy_pointer_and_receipt_verification(self):
        ovid = OVIDStorage()
        sample = b"PAR1_SOVEREIGN_LAKEHOUSE_COLUMN_CHUNK_PAR1"
        digest = hashlib.sha256(sample).hexdigest()
        folded = BinetZeckendorfIngressEngine.fold_bytes(sample, source_uri="s3://bucket/part.parquet")

        ptr = ovid.register_zero_copy_pointer(
            content_hash=digest,
            source_uri="s3://bucket/part.parquet",
            connector_id="conn_aws_s3_test",
            tenant_id="tenant-default",
            byte_offset=4096,
            byte_length=len(sample),
            access_class="REMOTE_REFERENCE",
            encryption_boundary="AWS_KMS_IN_MEMORY_CUSTODY",
            detected_format="PARQUET",
            algebraic_descriptor=folded,
        )
        assert ptr.pointer_id == f"{POINTER_PREFIX}{digest}"
        assert ptr.data_stays_at_rest is True
        assert ptr.bulk_staging_bytes == 0
        assert ovid.resolve_pointer(ptr.pointer_id) == ptr

        ml_signer = MLDSASigner()
        ed_signer = Ed25519Signer()
        receipt = ovid.create_pointer_receipt(
            ptr.pointer_id,
            ml_dsa_signature=ml_signer.sign(digest.encode("ascii")),
            ed25519_signature=ed_signer.sign(digest.encode("ascii")),
        )
        assert ovid.verify_receipt(receipt) is True
        verifier = VerifyEndpoint(ml_signer, ed_signer, None, ovid)
        assert verifier.verify_receipt(receipt) is True
        assert verifier.verify_hash_zero_auth(ptr.pointer_id)["valid"] is True

    @pytest.mark.parametrize(
        ("fmt", "uri", "payload"),
        [
            (
                IngestFormat.PARQUET,
                "s3://lake/trades.parquet",
                b"PAR1" + (b"\x10\x20\x30\x40" * 512) + b"PAR1",
            ),
            (
                IngestFormat.ORC,
                "hdfs://nn:8020/risk.orc",
                b"ORC" + (b"\x01\x02\x03\x04" * 256),
            ),
            (
                IngestFormat.GZIP,
                "gs://archive/events.json.gz",
                gzip.compress(b'{"id":1,"ring":"Q(sqrt(5))"}\n' * 64),
            ),
            (
                IngestFormat.DELTA_LAKE,
                "abfss://lake@acct.dfs.core.windows.net/tbl/_delta_log/00000.json",
                b'{"protocol":{"minReaderVersion":1,"minWriterVersion":2}}\n',
            ),
            (
                IngestFormat.JSON,
                "snowflake://org/DB/SCHEMA/FACT_LEDGER.json",
                b'{"tx_id":99,"amount":500000,"currency":"GBP"}\n',
            ),
            (
                IngestFormat.RAW_BINARY,
                "san://nvme-01/ns0/extent.bin",
                b"\xfe\xed\xfa\xce\x00\x11\x22\x33" * 128,
            ),
        ],
    )
    def test_binet_zeckendorf_format_agnostic_lossless_roundtrip(self, fmt, uri, payload):
        detected = BinetZeckendorfIngressEngine.detect_format(payload, source_uri=uri)
        assert detected == fmt

        folded = BinetZeckendorfIngressEngine.fold_bytes(payload, source_uri=uri)
        assert folded["detected_format"] == fmt.value
        assert folded["q_sqrt5_ring"]["ring"] == "Q(sqrt(5))"
        assert folded["pisot_lucas_state"]["identity_verified"] is True
        assert folded["lossless_fidelity"] == "100_PERCENT_EXACT"

        unfolded = BinetZeckendorfIngressEngine.unfold_bytes(folded)
        assert unfolded == payload

    def test_binet_zeckendorf_achieves_99_9_percent_collapse_on_structured_blocks(self):
        # 64 KiB structured columnar block collapses to a single 8-byte Pisot-Lucas run descriptor
        structured_block = b"\x00\x01\x02\x03" * (65536 // 4)
        folded = BinetZeckendorfIngressEngine.fold_bytes(
            structured_block,
            source_uri="s3://lake/structured.parquet",
            format_hint="PARQUET",
        )
        assert folded["footprint_collapse_bps"] == 9990
        assert folded["footprint_collapse_pct"] == "99.90%"
        assert BinetZeckendorfIngressEngine.unfold_bytes(folded) == structured_block

    def test_t3_t5_memory_access_classes_and_dec_lie_poisson_zero_stalls(self):
        # T3: LOCAL_ZERO_COPY for SAN or co-located NVMe
        t3 = classify_memory_access_class(ConnectorType.SAN, "eu-west-2", "eu-west-2")
        assert t3 == MemoryAccessClass.LOCAL_ZERO_COPY
        t3_route = DataMovementPlaneRouter.route_descriptor(t3, b"NVME_HOST_PAGE" * 8)
        assert t3_route["plane_tier"] == "T3"
        assert t3_route["latency_cycles"] == 1
        assert t3_route["host_mmap_binding"]["readonly_zero_copy"] is True

        # T4: REMOTE_REFERENCE for co-region S3 / Snowflake / Azure / GCS / Databricks / BigQuery
        for ctype in (
            ConnectorType.AWS_S3,
            ConnectorType.AZURE_BLOB,
            ConnectorType.GCP_GCS,
            ConnectorType.SNOWFLAKE,
            ConnectorType.DATABRICKS,
            ConnectorType.BIGQUERY,
        ):
            t4 = classify_memory_access_class(ctype, "eu-west-2", "eu-west-2")
            assert t4 == MemoryAccessClass.REMOTE_REFERENCE
            t4_route = DataMovementPlaneRouter.route_descriptor(t4, b"PAR1_FOOTER")
            assert t4_route["plane_tier"] == "T4"
            assert t4_route["ovid_reference_plane"]["bulk_payload_transferred"] is False

        # T5: REMOTE_TRANSFER for cross-region or remote on-prem PostgreSQL / HDFS
        t5_cross = classify_memory_access_class(ConnectorType.AWS_S3, "us-east-1", "eu-west-2")
        t5_pg = classify_memory_access_class(ConnectorType.POSTGRESQL, "eu-west-2", "eu-west-2")
        assert t5_cross == MemoryAccessClass.REMOTE_TRANSFER
        assert t5_pg == MemoryAccessClass.REMOTE_TRANSFER

        t5_route = DataMovementPlaneRouter.route_descriptor(t5_cross, b"CROSS_REGION_BLOCK" * 16)
        assert t5_route["plane_tier"] == "T5"
        stream = t5_route["dec_lie_poisson_stream"]
        assert stream["helicity_conserved"] is True
        assert stream["packet_stalls"] == 0
        assert stream["bus_saturation_pct"] == 100

    def test_al_haras_sheaf_cohomology_and_customer_kms_pkcs11_in_memory_custody(self):
        mgr = ZeroCopyConnectorManager()
        conn = mgr.register_connector(
            tenant_id="tenant-hsm-test",
            name="Air-Gapped PKCS#11 Snowflake Vault",
            connector_type=ConnectorType.SNOWFLAKE,
            endpoint_uri="snowflake://sovereign_acct/SEC_DW/CORE",
            kms_provider="PKCS11_HSM",
            kms_key_arn="pkcs11:model=FIPS140-3-L4;token=vault-09",
            auto_discover=False,
        )

        secret_payload = b'{"classified_ledger_id":777,"notional_gbp":95000000}'
        encrypted_stream = al_haras_kms_custody.encrypt_for_tenant(
            tenant_id="tenant-hsm-test",
            plaintext=secret_payload,
            associated_data=conn.connector_id.encode("utf-8"),
            kms_provider="PKCS11_HSM",
            kms_key_arn="pkcs11:model=FIPS140-3-L4;token=vault-09",
        )
        assert secret_payload not in encrypted_stream

        res = mgr.ingest_data_block(
            connector_id=conn.connector_id,
            raw_or_encrypted_bytes=encrypted_stream,
            object_path="SECRET_LEDGER.json",
        )
        assert res["al_haras_security"]["admitted"] is True
        assert res["al_haras_security"]["cohomology_state"] == "H^1(X; F) = 0"
        custody = res["al_haras_security"]["key_custody"]
        assert custody["decrypted_in_memory"] is True
        assert custody["persistent_disk_bytes_written"] == 0

        # Tampered KMS ciphertext must be rejected at AL HARAS edge
        tampered = encrypted_stream[:-1] + bytes([encrypted_stream[-1] ^ 0xFF])
        with pytest.raises(ConnectorSecurityError):
            mgr.ingest_data_block(
                connector_id=conn.connector_id,
                raw_or_encrypted_bytes=tampered,
                object_path="TAMPERED.json",
            )

        # Malicious prompt/SQL sheaf injection marker must raise H^1(X; F) != 0 obstruction
        with pytest.raises(ConnectorSecurityError, match="Sheaf cohomology obstruction"):
            mgr.ingest_data_block(
                connector_id=conn.connector_id,
                raw_or_encrypted_bytes=b"DROP TABLE -- INJECT_VORTEX",
                object_path="MALICIOUS.json",
            )


class TestConnectorsAPIExecutionAndSDK:
    @pytest.fixture(autouse=True)
    def setup_service(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            workloads,
            "workload_store",
            SQLiteWorkloadStore(str(tmp_path / "connectors_test.sqlite3")),
        )
        monkeypatch.setattr(service_config, "execution_backend_url", None)
        self.app = create_app()
        self.client = TestClient(self.app)
        yield
        self.client.close()

    def test_connectors_rest_lifecycle_schema_discovery_and_pointer_execution(self):
        # 1. Inspect pre-built specs (S3, Snowflake, T3-T5 plane)
        specs_res = self.client.get("/v1/connectors/specs")
        assert specs_res.status_code == 200
        specs = specs_res.json()
        assert "AWS_S3" in specs["featured_specs"]
        assert "SNOWFLAKE" in specs["featured_specs"]
        assert set(specs["data_movement_plane"].keys()) == {
            "LOCAL_ZERO_COPY",
            "SAME_HOST_SHARED_MEMORY",
            "DEVICE_SHARED_MEMORY",
            "REMOTE_REFERENCE",
            "REMOTE_TRANSFER",
            "REMOTE_MATERIALISATION",
        }

        # 2. Authorize Tenant ECA & register Databricks Delta Lake connector
        eca_res = self.client.post(
            "/v1/connectors/eca/tenant-quant-eca/authorize",
            json={
                "kms_provider": "AWS_KMS",
                "kms_key_arn": "arn:aws:kms:eu-west-2:111122223333:key/quant-cmk",
                "auto_schema_discovery": True,
            },
        )
        assert eca_res.status_code == 200
        assert eca_res.json()["authorized"] is True

        reg_res = self.client.post(
            "/v1/connectors",
            json={
                "tenant_id": "tenant-quant-eca",
                "name": "Databricks Unity Catalog Delta Connector",
                "connector_type": "DATABRICKS",
                "endpoint_uri": "databricks://quant-ws/main/alpha_signals",
                "source_region": "eu-west-2",
                "pod_region": "eu-west-2",
                "kms_provider": "AWS_KMS",
                "auto_discover": True,
            },
        )
        assert reg_res.status_code == 201
        conn_id = reg_res.json()["connector_id"]
        assert reg_res.json()["access_class"] == "REMOTE_REFERENCE"
        assert len(reg_res.json()["discovered_datasets"]) >= 1

        # 3. Automated Schema Discovery Middleware indexes new tables under ECA
        disc_res = self.client.post(
            f"/v1/connectors/{conn_id}/discover",
            json={"additional_tables": ["ALPHA_ORDERBOOK_TICKS", "RISK_GREEKS_LIVE"]},
        )
        assert disc_res.status_code == 200
        assert disc_res.json()["newly_indexed_count"] == 2

        # 4. Ingest KMS-encrypted block & execute computations against ptr_ovid_<hash>
        ingest_res = self.client.post(
            f"/v1/connectors/{conn_id}/ingest",
            json={
                "payload_text": '{"signal_id":42,"alpha_bps":185}' * 32,
                "object_path": "signals/batch_01.json",
                "encrypt_with_customer_kms": True,
            },
        )
        assert ingest_res.status_code == 200
        ptr_id = ingest_res.json()["pointer"]["pointer_id"]
        assert ptr_id.startswith("ptr_ovid_")
        assert ingest_res.json()["pointer"]["bulk_staging_bytes"] == 0

        for op in (
            "PV_LATTICE_FOLD",
            "LUCAS_PV_SCALING",
            "METALLIC_SCALE",
            "EXACT_RECONSTRUCT_VERIFY",
        ):
            exec_res = self.client.post(
                f"/v1/connectors/pointers/{ptr_id}/execute",
                json={"operation": op, "scale_order": 10, "metallic_m": 1},
            )
            assert exec_res.status_code == 200
            body = exec_res.json()
            assert body["data_stays_at_rest"] is True
            assert body["egress_bytes_transferred"] == 0

        # 5. Adversarial H^1(X; F) != 0 payload is blocked with 403 Forbidden
        blocked = self.client.post(
            f"/v1/connectors/{conn_id}/ingest",
            json={
                "payload_text": "normal_looking_payload",
                "object_path": "signals/poison.json",
                "simulate_adversarial": True,
            },
        )
        assert blocked.status_code == 403
        assert blocked.json()["detail"]["cohomology_state"] == "H^1(X; F) != 0"

    def test_native_reference_backend_and_workloads_router_execute_zero_copy_workloads(self):
        auth_service.register_tenant("zc-workload-tenant", "zc-workload-token")

        # BINET_ZECKENDORF_INGEST via NativeMathReferenceBackend
        parquet_bytes = b"PAR1" + (b"\x05\x08\x0d\x15" * 256) + b"PAR1"
        folded_exec = NativeMathReferenceBackend().execute(
            parquet_bytes, "BINET_ZECKENDORF_INGEST"
        )
        assert folded_exec["roundtrip_exact_verified"] is True
        assert folded_exec["folded"]["detected_format"] == "PARQUET"

        # ZERO_COPY_CONNECTOR_EXECUTE via /workloads/submit
        pointers = self.client.get("/v1/connectors/pointers").json()["pointers"]
        assert len(pointers) >= 1
        target_ptr = pointers[0]["pointer_id"]

        payload_json = json.dumps(
            {
                "pointer_id": target_ptr,
                "operation": "PV_LATTICE_FOLD",
                "scale_order": 12,
            }
        ).encode("utf-8")

        resp = self.client.post(
            "/workloads/submit",
            headers={"Authorization": "Bearer zc-workload-token"},
            json={
                "tenant_id": "zc-workload-tenant",
                "workload_type": "ZERO_COPY_CONNECTOR_EXECUTE",
                "representation_mode": "BINET_ZECKENDORF",
                "payload_bytes": "base64:" + base64.b64encode(payload_json).decode("ascii"),
                "metadata": {"zero_copy_pointer_id": target_ptr},
            },
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "COMPLETED"
        assert data["result"]["result"]["pointer_id"] == target_ptr
        assert data["result"]["result"]["computation"]["norm_invariant_verified"] is True
        assert data["verification_receipt"] is not None

    def test_python_sdk_zero_copy_connector_methods(self):
        auth_service.register_tenant("sdk-zc-tenant", "sdk-zc-token")
        # Bridge sync ChronusAPISDK httpx.Client to FastAPI TestClient via MockTransport
        def _bridge_to_fastapi(request: httpx.Request) -> httpx.Response:
            resp = self.client.request(
                request.method,
                request.url.raw_path.decode("ascii"),
                content=request.content,
                headers=dict(request.headers),
            )
            clean_headers = {
                k: v
                for k, v in resp.headers.items()
                if k.lower() not in ("content-encoding", "content-length")
            }
            return httpx.Response(
                status_code=resp.status_code,
                headers=clean_headers,
                content=resp.content,
                request=request,
            )

        sdk = ChronusAPISDK(
            tenant_id="sdk-zc-tenant",
            access_token="sdk-zc-token",
            base_url="http://testserver",
        )
        sdk._client = httpx.Client(
            transport=httpx.MockTransport(_bridge_to_fastapi),
            base_url="http://testserver",
            headers=sdk._client.headers,
        )
        try:
            specs = sdk.list_connector_specs()
            assert "AWS_S3" in specs["prebuilt_connectors"]

            eca = sdk.authorize_eca(kms_provider="GCP_KMS")
            assert eca["authorized"] is True

            conn = sdk.register_connector(
                name="GCP BigQuery Zero-Copy Analytics",
                connector_type="BIGQUERY",
                endpoint_uri="bigquery://chronus-gcp-01/finops_mart",
                kms_provider="GCP_KMS",
            )
            cid = conn["connector_id"]

            ingested = sdk.ingest_zero_copy(
                cid,
                b"PAR1" + (b"\xaa\xbb\xcc\xdd" * 128) + b"PAR1",
                object_path="mart_snapshot.parquet",
                encrypt_with_customer_kms=True,
            )
            ptr_id = ingested["pointer"]["pointer_id"]
            assert ptr_id.startswith("ptr_ovid_")

            discovered = sdk.discover_connector_schemas(cid, additional_tables=["BQ_POSITIONS_VIEW"])
            assert discovered["newly_indexed_count"] == 1

            executed = sdk.execute_zero_copy_pointer(
                ptr_id, operation="EXACT_RECONSTRUCT_VERIFY", scale_order=4
            )
            assert executed["computation"]["sha256_verified"] is True

            with pytest.raises(AuthorizationError):
                sdk.ingest_zero_copy(
                    cid,
                    b"adversarial_test",
                    simulate_adversarial=True,
                )

            # S3 Multi-TB Parquet Discovery & Query Benchmarks via SDK
            sdk_s3_bench = sdk.run_s3_parquet_discovery_benchmark()
            assert sdk_s3_bench["benchmark"] == "S3_MULTI_TERABYTE_PARQUET_SCHEMA_DISCOVERY"
            assert (
                sdk_s3_bench["zero_copy_storage_reduction"]["assigned_zero_copy_pointer"]
                == "ptr_ovid_9350fda91695d3d9b9a31bf6"
            )

            sdk_query_bench = sdk.benchmark_zero_copy_query(
                pointer_id="ptr_ovid_9350fda91695d3d9b9a31bf6",
                records_to_scan=15400000000,
            )
            assert sdk_query_bench["benchmark"] == "ZERO_COPY_IN_PLACE_QUERY_BENCHMARK"
            assert sdk_query_bench["dataset_scope"]["data_at_rest_enforced"] is True
            assert sdk_query_bench["dataset_scope"]["network_egress_bytes_transferred"] == 0
        finally:
            sdk.close()

    def test_s3_multi_terabyte_parquet_schema_discovery_benchmark(self):
        mgr = ZeroCopyConnectorManager()
        res = mgr.run_s3_parquet_discovery_benchmark()
        assert res["benchmark"] == "S3_MULTI_TERABYTE_PARQUET_SCHEMA_DISCOVERY"
        assert res["dataset_metrics"]["raw_dataset_size_tb"] == 5.2
        assert res["dataset_metrics"]["total_parquet_files"] == 1250
        assert res["dataset_metrics"]["total_records_indexed"] == 15400000000
        assert res["dataset_metrics"]["discovered_columns_count"] == 142

        telemetry = res["performance_telemetry"]
        assert telemetry["total_end_to_end_latency_ms"] <= 205.0
        assert telemetry["record_indexing_throughput_billion_per_sec"] >= 70.0

        storage = res["zero_copy_storage_reduction"]
        assert storage["assigned_zero_copy_pointer"] == "ptr_ovid_9350fda91695d3d9b9a31bf6"
        assert storage["compression_ratio_pct"] == 99.90
        assert storage["data_at_rest_enforced"] is True
        assert storage["network_egress_bytes_transferred"] == 0

        sec = res["al_haras_security_custody"]
        assert sec["sheaf_cohomology_status"] == "H1_VORTEX_FREE_NORM_0.0"
        assert sec["kms_custody_mode"] == "CUSTOMER_HELD_HSM_PKCS11"
        assert sec["fips_204_mldsa_signature"] == "mldsa65_9350fda91695d3d9b9a31bf63061a422"

    def test_s3_sample_zero_copy_query_benchmark_execution(self):
        mgr = ZeroCopyConnectorManager()
        ptr = mgr.ovid.resolve_pointer("ptr_ovid_9350fda91695d3d9b9a31bf6")
        assert ptr is not None
        assert ptr.pointer_id == "ptr_ovid_9350fda91695d3d9b9a31bf6"
        assert ptr.data_stays_at_rest is True
        assert ptr.bulk_staging_bytes == 0

        res = mgr.execute_zero_copy_query_benchmark(pointer_id="ptr_ovid_9350fda91695d3d9b9a31bf6")
        assert res["benchmark"] == "ZERO_COPY_IN_PLACE_QUERY_BENCHMARK"
        assert res["target_pointer_id"] == "ptr_ovid_9350fda91695d3d9b9a31bf6"
        assert res["dataset_scope"]["data_at_rest_enforced"] is True
        assert res["dataset_scope"]["network_egress_bytes_transferred"] == 0
        assert res["dataset_scope"]["bulk_staging_bytes_transferred"] == 0
        assert res["dataset_scope"]["total_records_scanned"] == 15400000000

        queries = {q["query_name"]: q for q in res["queries_executed"]}
        assert "VWAP_SPREAD_Q5_PROJECTION" in queries
        assert queries["VWAP_SPREAD_Q5_PROJECTION"]["norm_invariant_verified"] is True

        assert "PISOT_LUCAS_L479_INVARIANT_SCAN" in queries
        assert queries["PISOT_LUCAS_L479_INVARIANT_SCAN"]["identity_verified"] is True
        assert queries["PISOT_LUCAS_L479_INVARIANT_SCAN"]["structural_index_n"] == 479

        assert "ZECKENDORF_PREDICATE_PUSHDOWN_AND_PARITY" in queries
        assert queries["ZECKENDORF_PREDICATE_PUSHDOWN_AND_PARITY"]["parity_verified"] is True

        telemetry = res["query_latency_telemetry"]
        assert telemetry["total_query_latency_ms"] < 10.0
        assert telemetry["effective_query_throughput_billion_records_per_sec"] > 1000.0

    def test_s3_discovery_and_query_benchmark_endpoints(self):
        s3_res = self.client.post("/v1/connectors/benchmarks/s3-parquet-discovery")
        assert s3_res.status_code == 200
        s3_data = s3_res.json()
        assert s3_data["benchmark"] == "S3_MULTI_TERABYTE_PARQUET_SCHEMA_DISCOVERY"
        ptr_id = s3_data["zero_copy_storage_reduction"]["assigned_zero_copy_pointer"]
        assert ptr_id == "ptr_ovid_9350fda91695d3d9b9a31bf6"

        qry_res = self.client.post(f"/v1/connectors/pointers/{ptr_id}/query-benchmark")
        assert qry_res.status_code == 200
        qry_data = qry_res.json()
        assert qry_data["benchmark"] == "ZERO_COPY_IN_PLACE_QUERY_BENCHMARK"
        assert qry_data["dataset_scope"]["network_egress_bytes_transferred"] == 0

        # Also via execute endpoint with ZERO_COPY_QUERY_BENCHMARK operation
        exec_res = self.client.post(
            f"/v1/connectors/pointers/{ptr_id}/execute",
            json={"operation": "ZERO_COPY_QUERY_BENCHMARK", "scale_order": 12},
        )
        assert exec_res.status_code == 200
        assert exec_res.json()["benchmark"] == "ZERO_COPY_IN_PLACE_QUERY_BENCHMARK"
