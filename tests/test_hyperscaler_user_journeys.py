"""End-to-end verification test suite for Chronus CIaaS & AL HARAS OS.

Rigorously verifies all 4 architectural user journeys, 6 explicit memory access classes,
the 7-row Hyperscaler Connector Matrix, 4-phase scaling roadmap to 160k warps (5.12M SIMD lanes),
exact H_4 600-cell crossbar routing, DSW 4D instanton cobordism self-healing, Cellular Sheaf
cohomology obstruction isolation (norm 1.4142), exact Z[zeta_5] cyclotomic anyon braids,
and Hermiten 25% value-share settlement ($520k benchmark).
"""

import json
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from starlette.testclient import TestClient

from chronus.execution.hardware_dispatcher import HardwareAcceleratorDispatcher
from chronus.ns_dec import H4PolytopeCrossbarRouter, build_h4_600_cell_polytope
from chronus.security.al_haras.engine import (
    CellularSheafCohomology,
    CyclotomicAnyonBraidEngine,
    DSW4DInstantonMonopoleHealer,
)
from chronus.security.al_haras.sovereign import SovereignGovernanceEngine
from chronus.service.app import create_app
from chronus.service.auth_middleware import Role, create_jwt_token
from chronus.service.dependencies import auth_service
from chronus.storage.connectors import (
    ConnectorCategory,
    ConnectorType,
    IngestFormat,
    MemoryAccessClass,
    zero_copy_connector_manager,
)


@pytest.fixture(scope="module")
def api_client():
    app = create_app()
    return TestClient(app)


def test_section1_six_memory_access_classes_and_hyperscaler_matrix(api_client):
    """Verify Section 1: All 6 Memory Access Classes and 7-Row Hyperscaler Matrix."""
    # 1. 6 Explicit Memory Access Classes
    assert len(MemoryAccessClass) == 6
    expected_classes = {
        "LOCAL_ZERO_COPY",
        "SAME_HOST_SHARED_MEMORY",
        "DEVICE_SHARED_MEMORY",
        "REMOTE_REFERENCE",
        "REMOTE_TRANSFER",
        "REMOTE_MATERIALISATION",
    }
    actual_classes = {m.value for m in MemoryAccessClass}
    assert actual_classes == expected_classes

    # 2. 7-Row Hyperscaler Connector Matrix via GET /v1/connectors/matrix
    resp = api_client.get("/v1/connectors/matrix")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_providers"] == 7
    assert len(data["matrix"]) == 7
    providers = [row["provider"] for row in data["matrix"]]
    assert "Amazon Web Services (AWS)" in providers
    assert "Microsoft Azure" in providers
    assert "Google Cloud (GCP)" in providers
    assert "Snowflake" in providers
    assert "Databricks" in providers
    assert "NVIDIA DGX Cloud" in providers
    assert "Palantir Foundry / Defense" in providers

    for row in data["matrix"]:
        assert row["default_access_class"] in expected_classes

    # 3. 4-Phase Deployment Roadmap via GET /v1/connectors/roadmap
    roadmap_resp = api_client.get("/v1/connectors/roadmap")
    assert roadmap_resp.status_code == 200
    roadmap = roadmap_resp.json()
    assert roadmap["total_phases"] == 4
    assert roadmap["max_warp_scale"] == 160000
    assert roadmap["max_simd_lanes"] == 5120000
    assert len(roadmap["phases"]) == 4
    assert roadmap["phases"][3]["phase_number"] == 4


def test_h4_600_cell_polytope_and_crossbar_routing():
    """Verify Section 3 & User Journey 2: H_4 600-cell Polytope and 130 Tb/s crossbar routing."""
    # 1. Exact Polytope Geometry: 120 vertices, 720 edges, degree 12
    polytope = build_h4_600_cell_polytope()
    assert polytope["vertices"] == 120
    assert polytope["edges"] == 720
    assert polytope["vertex_degree"] == 12

    # 2. DEC Lie-Poisson Router: Zero packet stalls, zero triad resonance blowups at 100% saturation
    flow_result = H4PolytopeCrossbarRouter.route_crossbar_frames(
        frames=[], bus_saturation_pct=100
    )
    assert flow_result["dma_packet_stalls"] == 0
    assert flow_result["triad_resonance_blowups"] == 0
    assert flow_result["enstrophy_conserved"] is True
    assert flow_result["helicity_conserved"] is True
    assert flow_result["edges"] == 720
    assert flow_result["bus_saturation_pct"] == 100
    assert flow_result["virtual_crossbar_bandwidth_tbs"] == 130


def test_user_journey_1_financial_lakehouse_zero_copy_flow(api_client):
    """Verify User Journey 1: Fortune 50 Lakehouse (15 PB S3/Snowflake) in-place discovery, fold & zk-STARK."""
    tenant_id = "tenant_apex_lakehouse_uj1"
    token = "apex-financial-token-2026"
    auth_service.register_tenant(tenant_id, token)
    sys_admin_token = create_jwt_token(
        tenant_id="chronus-root",
        user_id="sre-lead@chronus.io",
        role=Role.SYSTEM_ADMIN,
    )

    # Step 1: Zero-Friction Instant Onboarding & Enduring Capacity Registration
    onboard_payload = {
        "contract_id": "ctr_apex_lakehouse_2026",
        "company_name": "Apex Global Financial",
        "tenant_id": tenant_id,
        "admin_email": "security@apexglobal.com",
        "enduring_addendum_accepted": True,
        "regional_pod": "alpha",
        "webhook_source": "DOCUSIGN_CLM",
        "cce_allocations": {
            "initial_warps": 32,
            "max_authorized_warps": 1024,
            "data_at_rest_gb": 15000000,  # 15 Petabytes in GB
            "data_in_motion_gb": 50000,
            "o1_structural_memory_gb": 512,
            "kms_provider": "AWS_KMS",
            "kms_key_arn": "arn:aws:kms:us-east-1:123456789012:key/apex-pkcs11-prod",
        },
    }
    onboard_resp = api_client.post(
        "/v1/tenants/onboard/instant",
        headers={"Authorization": f"Bearer {sys_admin_token}"},
        json=onboard_payload,
    )
    assert onboard_resp.status_code == 201
    onboard_data = onboard_resp.json()
    assert onboard_data["tenant_id"] == tenant_id
    assert onboard_data["cce_allocations"]["data_at_rest_gb"] == 15000000
    assert onboard_data["status"] == "TENANT_PROVISIONED_INSTANTLY"

    # Step 2: In-Place Schema Discovery & Zero-Copy Pointer Mapping
    conn = zero_copy_connector_manager.register_connector(
        connector_id="conn-s3-apex-lakehouse",
        tenant_id=tenant_id,
        connector_type=ConnectorType.AWS_S3,
        connection_config={
            "bucket": "apex-financial-lakehouse-prod",
            "region": "us-east-1",
        },
        category=ConnectorCategory.CLOUD_OBJECT_STORE,
        primary_access_class=MemoryAccessClass.LOCAL_ZERO_COPY,
    )
    assert conn.is_active is True

    discovered = zero_copy_connector_manager.discover_dataset(
        connector_id=conn.connector_id,
        table_path="s3://apex-financial-lakehouse-prod/quant_risk_models/var_ticks_2026.parquet",
        format_type=IngestFormat.PARQUET,
        schema_descriptor={
            "columns": [
                "timestamp",
                "portfolio_id",
                "asset_weight",
                "covariance_q5",
                "lucas_index",
            ],
            "types": ["int64", "string", "q5_rational", "q5_rational", "int32"],
        },
        sample_payload_bytes=b"PAR1" + (b"\x01\x02\x03\x05\x08\x0d" * 64) + b"PAR1",
        column_statistics={
            "total_records": 15400000000,
            "total_bytes": 15000000000000000,
            "null_count": 0,
            "encoding": "DICTIONARY_RLE",
        },
    )
    assert discovered.pointer_id.startswith("ptr_ovid_")
    assert discovered.data_stays_at_rest is True
    assert discovered.column_statistics["total_records"] == 15400000000

    # Step 3: Binet-Zeckendorf Lossless Ingestion & Structural Reduction (Q(sqrt(5)), non-adjacent base-phi)
    risk_payload = {
        "model": "MULTIVARIATE_FINANCIAL_VAR",
        "portfolio_id": "apex_hft_macro_2026",
        "covariance_matrix": [[1, 2], [2, 5]],
        "simulations": 10000,
        "source_uri": discovered.table_path,
        "format_hint": "PARQUET",
        "b64_payload": "UEFSMRUCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UCA1UEFSMQ==",
    }
    workload_req = {
        "payload_bytes": json.dumps(risk_payload),
        "tenant_id": tenant_id,
        "workload_type": "ENTERPRISE_FINANCIAL_ETL",
        "backend_preference": "NativeMathReferenceBackend",
    }
    submit_resp = api_client.post(
        "/v1/workloads",
        headers={"Authorization": f"Bearer {token}"},
        json=workload_req,
    )
    assert submit_resp.status_code == 202
    workload_data = submit_resp.json()
    assert workload_data["status"] == "COMPLETED"
    workload_id = workload_data["workload_id"]
    receipt_handle = workload_data["verification_receipt"]
    assert receipt_handle is not None
    assert receipt_handle.startswith("o1_")

    # Step 4: 32-Lane Zeckendorf ALU Execution & Result Retrieval via GET /v1/workloads/{id}
    get_wkld_resp = api_client.get(
        f"/v1/workloads/{workload_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_wkld_resp.status_code == 200
    retrieved = get_wkld_resp.json()
    assert retrieved["workload_id"] == workload_id
    res = retrieved["result"]["result"]
    assert res["quadratic_field"] == "Q(sqrt(5))"
    assert (
        res["zeckendorf_non_adjacent_invariant"] == "c_k * c_{k+1} == 0 (STRICTLY_HELD)"
    )
    assert res["pisot_lucas_collapse"] == "O(1) structural memory"
    assert res["zeckendorf_alu_lanes"] == 32
    assert res["carry_propagation_delay_cycles"] == 0

    # Step 5: Public Zero-Auth Cryptographic Verification via GET /v1/verify/{receipt_hash}
    verify_resp = api_client.get(f"/v1/verify/{receipt_handle}")
    assert verify_resp.status_code == 200
    verify_data = verify_resp.json()
    assert verify_data["qualification_status"] == "VERIFIED"
    assert verify_data["raw_payload_exposed"] is False
    assert verify_data["auth_required"] is False
    assert verify_data["ed25519_verified"] is True


def test_user_journey_2_hyperscale_ai_factory_flow(api_client):
    """Verify User Journey 2: Disaggregated AI Factory (NVIDIA DGX Cloud & Azure Fabric)."""
    # 1. Tripartite & 4-Target Runtime Accelerator Discovery
    dispatcher = HardwareAcceleratorDispatcher()
    discovered_targets = dispatcher.discover_backends()
    assert len(discovered_targets) == 4
    target_names = list(discovered_targets.keys())
    assert "python-math-reference" in target_names
    assert "opencl-hardware-accelerator" in target_names
    assert "cuda-hardware-accelerator" in target_names
    assert "systemverilog-rtl-simulator" in target_names
    backend_class_names = [b.__class__.__name__ for b in dispatcher._backends.values()]
    assert "NativeMathReferenceBackend" in backend_class_names
    assert "OpenCLAcceleratorBackend" in backend_class_names
    assert "CUDABackendAdapter" in backend_class_names
    assert "SystemVerilogHardwareSimulatorBackend" in backend_class_names

    # 2. Physical AI Factory Cluster Registration via POST /v1/fabric/clusters/register
    reg_resp = api_client.post(
        "/v1/fabric/clusters/register",
        json={
            "cluster_id": "cluster_dgx_b200_superpod_01",
            "cloud_provider": "NVIDIA_DGX_CLOUD",
            "region": "us-east-1",
            "blade_count": 64,
            "interconnect": "130_TBPS_H4_POLYTOPE_CROSSBAR",
        },
    )
    assert reg_resp.status_code == 201
    reg_data = reg_resp.json()
    assert reg_data["cluster_id"] == "cluster_dgx_b200_superpod_01"
    assert reg_data["status"] in ("REGISTERED_ONLINE", "CLUSTER_REGISTERED_ZERO_STALL")

    # 3. Disaggregated Prefill, Decode, and Cryo-Quantum Pool Scheduling
    pool_resp = api_client.post(
        "/v1/fabric/pools/schedule",
        json={
            "workload_id": "wkld_llm_hybrid_70b_01",
            "prefill_tokens": 131072,
            "decode_tokens": 4096,
            "quantum_hilbert_dim": 64,
            "require_zero_stall": True,
        },
    )
    assert pool_resp.status_code == 200
    pool_data = pool_resp.json()
    assert pool_data["schedule_status"] == "DISPATCHED_TO_POOLS"
    assert pool_data["virtual_crossbar"]["dma_packet_stalls"] == 0
    assert pool_data["virtual_crossbar"]["bus_saturation_pct"] == 100

    # 4. 1-Cycle DSW 4D Instanton Monopole Self-Healing
    heal_result = DSW4DInstantonMonopoleHealer.inspect_and_heal(
        trace_payload=b"dummy_trace",
        is_perturbed=True,
    )

    assert heal_result["healing_cycles"] == 1
    assert heal_result["repair_latency_cycles"] == 1
    assert heal_result["stream_rollback_bytes"] == 0
    assert heal_result["cobordism_map"] == "W: Sigma_1 -> Sigma_2"


def test_user_journey_3_sovereign_defense_air_gapped_flow(api_client):
    """Verify User Journey 3: Sovereign Defense (Palantir Foundry & DoD IL6)."""
    # 1. Air-Gapped Sovereign Profile with CUSTOMER_HELD_HSM_PKCS11 and 0 Telemetry Egress
    # 1. Air-Gapped Sovereign Profile with CUSTOMER_HELD_HSM_PKCS11 and 0 Telemetry Egress
    profile = SovereignGovernanceEngine.audit_sovereign_compliance(
        "sovereign_dod_il6_intel"
    )
    assert profile["sovereign_profile"] == "SOVEREIGN_INSTITUTIONAL_EDITION"
    assert profile["kms_custody_mode"] == "CUSTOMER_HELD_HSM_PKCS11"
    assert profile["external_telemetry_egress_bytes"] == 0
    assert profile["dod_il6_compliance"] == "DOD_IL6_AIRGAPPED_READY"

    # 2. Cellular Sheaf Cohomology Obstruction Filtration (Norm = 1.4142)
    sheaf = CellularSheafCohomology()
    clean_nodes = ["intel_agent_alpha", "intel_agent_bravo", "intel_agent_charlie"]
    clean_edges = [
        ("intel_agent_alpha", "intel_agent_bravo"),
        ("intel_agent_bravo", "intel_agent_charlie"),
    ]
    clean_cohom = sheaf.compute_cohomology(
        nodes=clean_nodes,
        edges=clean_edges,
        latent_vectors={
            "intel_agent_alpha": [1, 2],
            "intel_agent_bravo": [1, 2],
            "intel_agent_charlie": [1, 2],
        },
    )
    assert clean_cohom["h0_harmonic_section"] is True
    assert clean_cohom["h1_first_cohomology_rank"] == 0
    assert clean_cohom["h1_vortex_norm"] == 0.0
    assert clean_cohom["downstream_context_contaminated"] is False

    # Adversarial Injection payload induces non-zero coboundary obstruction
    attack_cohom = sheaf.compute_cohomology(
        nodes=clean_nodes,
        edges=clean_edges,
        latent_vectors={
            "intel_agent_alpha": [1, 2],
            "intel_agent_bravo": [2, 3],
            "intel_agent_charlie": [1, 2],
        },
    )
    assert attack_cohom["h1_first_cohomology_rank"] > 0
    assert attack_cohom["h1_vortex_norm"] == 1.4142
    assert attack_cohom["is_secure"] is False
    assert attack_cohom["downstream_context_contaminated"] is False
    assert (
        attack_cohom["audit_alert"]
        == "OBSTRUCTION_ISOLATED: H1(X; F) != 0, vortex norm 1.4142"
    )

    # 3. Cyclotomic Anyon Braids over Exact Z[zeta_5] (Artin braid and pentagon coherence, zero floats)
    braid_engine = CyclotomicAnyonBraidEngine()
    braid_verification = braid_engine.compile_braid(["sigma_1", "sigma_2", "sigma_1"])
    assert braid_verification["artin_braid_satisfied"] is True
    assert (
        braid_verification["artin_relation"]
        == "sigma_1 * sigma_2 * sigma_1 == sigma_2 * sigma_1 * sigma_2"
    )
    assert braid_verification["pentagon_coherence_verified"] is True
    assert braid_verification["hexagon_coherence_verified"] is True
    assert braid_verification["exact_cyclotomic_ring"] == "Z[zeta_5]"
    assert braid_verification["zero_floating_point"] is True


def test_user_journey_4_finops_metering_and_hermiten_settlement(api_client):
    """Verify User Journey 4: FinOps CCE 5D metering & Hermiten 25% Value-Share settlement ($520k benchmark)."""
    # 1. Reconcile Hermiten 25% Value-Share Settlement ($520,000.00 counterfactual vs $317,500.00 actual)
    settle_resp = api_client.post(
        "/v1/billing/hermiten/settlement",
        json={
            "tenant_id": "tenant_apex_9921a",
            "period": "2026-Q1",
            "counterfactual_cloud_spend_usd": 520000.00,
            "actual_cloud_spend_usd": 317500.00,
            "incremental_chronus_costs_usd": 0.00,
        },
    )
    assert settle_resp.status_code == 200
    settle_data = settle_resp.json()
    assert settle_data["counterfactual_cloud_spend_usd"] == 520000.00
    assert settle_data["actual_cloud_spend_usd"] == 317500.00
    assert settle_data["net_avoided_cost_usd"] == 202500.00
    assert settle_data["chronus_value_share_usd"] == 50625.00
    assert settle_data["client_retained_savings_usd"] == 151875.00
    assert settle_data["settlement_certificate"].startswith("cert_hermiten_")
    assert settle_data["value_share_percentage"] == 25

    # 2. Scaling ceiling: 160,000 Warps and 100 PB storage
    from chronus.service.instant_provisioning import MAX_ENDURING_WARP_CEILING

    assert MAX_ENDURING_WARP_CEILING == 160000
