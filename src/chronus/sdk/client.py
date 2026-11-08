"""HTTP client for the Chronus workload service."""

import base64
import os
import time
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import httpx

from chronus.sdk.models import (
    AuthenticationError,
    AuthorizationError,
    ChronusSDKError,
    RateLimitError,
    ServiceUnavailableError,
    WorkloadResult,
)


class ChronusAPISDK:
    """Synchronous client for a separately deployed Chronus API."""

    SDK_VERSION = "36.0.0"

    def __init__(
        self,
        tenant_id: str,
        access_token: str,
        region: str = "us-east-1",
        endpoint: str = "v1",
        base_url: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        verify_ssl: bool = True,
    ) -> None:
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required")
        if not access_token or not access_token.strip():
            raise ValueError("access_token is required")
        resolved_url = base_url or os.getenv("CHRONUS_API_URL")
        if not resolved_url:
            raise ValueError("base_url or CHRONUS_API_URL is required")
        if timeout <= 0 or max_retries < 1:
            raise ValueError("timeout and max_retries must be positive")

        self.tenant_id = tenant_id.strip()
        self.access_token = access_token.strip()
        self.region = region
        self.endpoint = endpoint
        self.base_url = resolved_url.rstrip("/")
        self.max_retries = max_retries
        self._request_count = 0
        self._total_latency_ms = 0.0
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            verify=verify_ssl,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "X-Tenant-ID": self.tenant_id,
                "X-Region": self.region,
                "X-Endpoint": self.endpoint,
                "X-SDK-Version": self.SDK_VERSION,
                "User-Agent": f"chronus-sdk/{self.SDK_VERSION}",
            },
        )

    def __enter__(self) -> "ChronusAPISDK":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _request(
        self,
        method: str,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        attempts = (
            self.max_retries
            if method.upper() in {"GET", "PUT", "PATCH", "DELETE"}
            else 1
        )
        for attempt in range(attempts):
            started = time.perf_counter()
            try:
                response = self._client.request(method, path, json=json, params=params)
            except httpx.RequestError as exc:
                if attempt + 1 == attempts:
                    raise ServiceUnavailableError(
                        "Chronus API request failed", status_code=0
                    ) from exc
                time.sleep(min(2**attempt, 8))
                continue

            self._request_count += 1
            self._total_latency_ms += (time.perf_counter() - started) * 1000
            body: Dict[str, Any]
            try:
                decoded = response.json()
                body = decoded if isinstance(decoded, dict) else {"data": decoded}
            except ValueError:
                body = {}

            if response.status_code in (200, 201, 202, 204):
                return body
            if response.status_code == 401:
                raise AuthenticationError(response=body)
            if response.status_code == 403:
                raise AuthorizationError(response=body)
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "60")
                raise RateLimitError(
                    retry_after=int(retry_after) if retry_after.isdigit() else 60,
                    response=body,
                )
            if response.status_code >= 500:
                error = ServiceUnavailableError(
                    f"Chronus API returned HTTP {response.status_code}",
                    status_code=response.status_code,
                    response=body,
                )
                if attempt + 1 < attempts:
                    time.sleep(min(2**attempt, 8))
                    continue
                raise error
            raise ChronusSDKError(
                f"Chronus API returned HTTP {response.status_code}",
                status_code=response.status_code,
                response=body,
            )
        raise ServiceUnavailableError("Chronus API request attempts exhausted")

    def submit_workload(
        self,
        payload_bytes: bytes,
        workload_type: str = "EXACT_Q5_ALGEBRAIC",
        representation_mode: str = "EXACT_Q5_RATIONAL",
        priority: str = "HIGH",
        callback_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        backend_preference: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not payload_bytes:
            raise ValueError("payload_bytes cannot be empty")
        payload: Dict[str, Any] = {
            "payload_bytes": "base64:"
            + base64.b64encode(payload_bytes).decode("ascii"),
            "workload_type": workload_type,
            "representation_mode": representation_mode,
            "priority": priority,
            "tenant_id": self.tenant_id,
            "region": self.region,
            "endpoint": self.endpoint,
        }
        if callback_url:
            payload["callback_url"] = callback_url
        if metadata:
            payload["metadata"] = metadata
        if backend_preference:
            payload["backend_preference"] = backend_preference

        response = self._request("POST", "/workloads/submit", json=payload)
        workload_id = response.get("workload_id")
        state = response.get("status")
        if not isinstance(workload_id, str) or not isinstance(state, str):
            raise ChronusSDKError(
                "Chronus API response is missing workload_id or status",
                status_code=502,
                response=response,
            )
        try:
            UUID(workload_id)
        except ValueError as exc:
            raise ChronusSDKError(
                "Chronus API returned an invalid workload_id",
                status_code=502,
                response=response,
            ) from exc

        return WorkloadResult(
            workload_id=workload_id,
            status=state,
            workload_type=workload_type,
            representation_mode=representation_mode,
            priority=priority,
            tenant_id=self.tenant_id,
            region=self.region,
            ccu_cost=response.get("ccu_cost"),
            result=response.get("result"),
            verification_receipt=response.get("verification_receipt"),
        ).to_dict()

    def get_workload_status(self, workload_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/workloads/{workload_id}")

    def list_workloads(self, page: int = 1, page_size: int = 50) -> Dict[str, Any]:
        return self._request(
            "GET",
            "/workloads",
            params={"page": page, "page_size": page_size},
        )

    def cancel_workload(self, workload_id: str) -> None:
        self._request("DELETE", f"/workloads/{workload_id}")

    def verify_hash(self, hash_value: str) -> Dict[str, Any]:
        return self._request("GET", f"/verify/{hash_value}")

    def get_health(self) -> Dict[str, Any]:
        return self._request("GET", "/health")

    def instant_onboard_tenant(
        self, onboarding_payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Trigger Zero-Friction instant tenant provisioning (<30s T0 SLA)."""
        return self._request(
            "POST", "/v1/tenants/onboard/instant", json=onboarding_payload
        )

    def expand_capacity(
        self,
        requested_warp_capacity: int,
        expand_storage_gb: Optional[int] = None,
        reason: str = "SDK_SELF_SERVICE_EXPANSION",
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Dynamically expand active warps or storage under Enduring Capacity Addendum."""
        target_tenant = tenant_id or self.tenant_id
        payload: Dict[str, Any] = {
            "requested_warp_capacity": requested_warp_capacity,
            "reason": reason,
        }
        if expand_storage_gb is not None:
            payload["expand_storage_gb"] = expand_storage_gb
        return self._request(
            "PATCH", f"/v1/tenants/{target_tenant}/capacity", json=payload
        )

    def get_capacity_status(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Retrieve Enduring Capacity Addendum and real-time Hermiten settlement status."""
        target_tenant = tenant_id or self.tenant_id
        return self._request("GET", f"/v1/tenants/{target_tenant}/capacity")

    def list_connector_specs(self) -> Dict[str, Any]:
        """Retrieve pre-built Zero-Copy Connector specifications and T3-T5 Data Movement Plane."""
        return self._request("GET", "/v1/connectors/specs")

    def authorize_eca(
        self,
        kms_provider: str = "AWS_KMS",
        kms_key_arn: Optional[str] = None,
        auto_schema_discovery: bool = True,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Authorize Tenant Enduring Capacity Addendum (ECA) & Customer KMS/PKCS#11 custody."""
        target_tenant = tenant_id or self.tenant_id
        payload: Dict[str, Any] = {
            "kms_provider": kms_provider,
            "auto_schema_discovery": auto_schema_discovery,
        }
        if kms_key_arn is not None:
            payload["kms_key_arn"] = kms_key_arn
        return self._request(
            "POST", f"/v1/connectors/eca/{target_tenant}/authorize", json=payload
        )

    def register_connector(
        self,
        *,
        name: str,
        connector_type: str,
        endpoint_uri: str,
        source_region: str = "eu-west-2",
        pod_region: str = "eu-west-2",
        kms_provider: str = "AWS_KMS",
        kms_key_arn: Optional[str] = None,
        co_located: bool = False,
        access_class_override: Optional[str] = None,
        auto_discover: bool = True,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Bind a Day-1 Zero-Copy Native Representation Connector to client data at rest."""
        payload: Dict[str, Any] = {
            "tenant_id": tenant_id or self.tenant_id,
            "name": name,
            "connector_type": connector_type,
            "endpoint_uri": endpoint_uri,
            "source_region": source_region,
            "pod_region": pod_region,
            "kms_provider": kms_provider,
            "co_located": co_located,
            "auto_discover": auto_discover,
        }
        if kms_key_arn is not None:
            payload["kms_key_arn"] = kms_key_arn
        if access_class_override is not None:
            payload["access_class_override"] = access_class_override
        return self._request("POST", "/v1/connectors", json=payload)

    def list_connectors(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """List bound Zero-Copy Native Representation Connectors."""
        params: Optional[Dict[str, Any]] = (
            {"tenant_id": tenant_id} if tenant_id else None
        )
        return self._request("GET", "/v1/connectors", params=params)

    def ingest_zero_copy(
        self,
        connector_id: str,
        payload_bytes: bytes,
        *,
        object_path: str = "part-00000.parquet",
        byte_offset: int = 0,
        format_hint: Optional[str] = None,
        encrypt_with_customer_kms: bool = False,
        simulate_adversarial: bool = False,
    ) -> Dict[str, Any]:
        """Ingest external block via Binet-Zeckendorf Fold & return ptr_ovid_<hash> pointer."""
        if not payload_bytes:
            raise ValueError("payload_bytes cannot be empty")
        body: Dict[str, Any] = {
            "payload_b64": "base64:" + base64.b64encode(payload_bytes).decode("ascii"),
            "object_path": object_path,
            "byte_offset": byte_offset,
            "encrypt_with_customer_kms": encrypt_with_customer_kms,
            "simulate_adversarial": simulate_adversarial,
        }
        if format_hint is not None:
            body["format_hint"] = format_hint
        return self._request("POST", f"/v1/connectors/{connector_id}/ingest", json=body)

    def discover_connector_schemas(
        self,
        connector_id: str,
        additional_tables: Optional[list[str]] = None,
    ) -> Dict[str, Any]:
        """Run Automated Schema Discovery Middleware under Tenant ECA."""
        body: Dict[str, Any] = {}
        if additional_tables is not None:
            body["additional_tables"] = additional_tables
        return self._request(
            "POST", f"/v1/connectors/{connector_id}/discover", json=body
        )

    def execute_zero_copy_pointer(
        self,
        pointer_id: str,
        operation: str = "PV_LATTICE_FOLD",
        scale_order: int = 8,
        metallic_m: int = 1,
    ) -> Dict[str, Any]:
        """Execute exact algebraic computation directly against ptr_ovid_<hash>."""
        return self._request(
            "POST",
            f"/v1/connectors/pointers/{pointer_id}/execute",
            json={
                "operation": operation,
                "scale_order": scale_order,
                "metallic_m": metallic_m,
            },
        )

    def run_s3_parquet_discovery_benchmark(
        self,
        target_s3_uri: str = "s3://apex-financial-lakehouse-prod/quant_models_v4/historical_ticks_2026.parquet",
        total_parquet_files: int = 1250,
        total_records_indexed: int = 15400000000,
        discovered_columns_count: int = 142,
    ) -> Dict[str, Any]:
        """Execute Multi-Terabyte S3 Parquet Schema Discovery Benchmark under ECA."""
        payload: Dict[str, Any] = {
            "target_s3_uri": target_s3_uri,
            "total_parquet_files": total_parquet_files,
            "total_records_indexed": total_records_indexed,
            "discovered_columns_count": discovered_columns_count,
        }
        return self._request(
            "POST", "/v1/connectors/benchmarks/s3-parquet-discovery", json=payload
        )

    def benchmark_zero_copy_query(
        self,
        pointer_id: str = "ptr_ovid_9350fda91695d3d9b9a31bf6",
        query_type: str = "ALL_BENCHMARKS",
        scale_order: int = 12,
        records_to_scan: int = 15400000000,
    ) -> Dict[str, Any]:
        """Execute in-place zero-copy query response time benchmark against ptr_ovid_<hash>."""
        payload: Dict[str, Any] = {
            "query_type": query_type,
            "scale_order": scale_order,
            "records_to_scan": records_to_scan,
        }
        return self._request(
            "POST",
            f"/v1/connectors/pointers/{pointer_id}/query-benchmark",
            json=payload,
        )

    def get_workload_v1(self, workload_id: Any) -> Dict[str, Any]:
        """Retrieve workload execution status and cryptographic verification receipt via GET /v1/workloads/{id}."""
        wid = str(workload_id)
        return self._request("GET", f"/v1/workloads/{wid}")

    def list_workloads_v1(self, page: int = 1, page_size: int = 50) -> Dict[str, Any]:
        """List tenant workloads via GET /v1/workloads."""
        return self._request(
            "GET", "/v1/workloads", params={"page": page, "page_size": page_size}
        )

    def verify_receipt_v1(self, receipt_hash: str) -> Dict[str, Any]:
        """Public zero-auth cryptographic verification via GET /v1/verify/{receipt_hash}."""
        return self._request("GET", f"/v1/verify/{receipt_hash}")

    def get_hyperscaler_matrix(self) -> Dict[str, Any]:
        """Retrieve the 7-row Hyperscaler Connector Matrix via GET /v1/connectors/matrix."""
        return self._request("GET", "/v1/connectors/matrix")

    def get_deployment_roadmap(self) -> Dict[str, Any]:
        """Retrieve the 4-phase Deployment Roadmap via GET /v1/connectors/roadmap."""
        return self._request("GET", "/v1/connectors/roadmap")

    def register_cluster(
        self,
        cluster_id: str,
        cloud_provider: str = "NVIDIA_DGX_CLOUD",
        region: str = "us-east-1",
        blade_count: int = 32,
        interconnect: str = "130_TBPS_H4_POLYTOPE_CROSSBAR",
        subsystems: Optional[list] = None,
    ) -> Dict[str, Any]:
        """Register physical AI Factory cluster via POST /v1/fabric/clusters/register."""
        payload = {
            "cluster_id": cluster_id,
            "cloud_provider": cloud_provider,
            "region": region,
            "blade_count": blade_count,
            "interconnect": interconnect,
            "subsystems": subsystems
            or [
                "NVIDIA_BLACKWELL_B200",
                "NVFP4_TENSOR_CORES",
                "HBM3E_DISAGGREGATED_POOL",
                "H4_600_CELL_VIRTUAL_CROSSBAR",
            ],
        }
        return self._request("POST", "/v1/fabric/clusters/register", json=payload)

    def schedule_disaggregated_pools(
        self,
        workload_id: str,
        prefill_tokens: int = 131072,
        decode_tokens: int = 4096,
        quantum_hilbert_dim: int = 64,
        require_zero_stall: bool = True,
    ) -> Dict[str, Any]:
        """Schedule disaggregated Prefill, Decode, and Cryo-Quantum pools via POST /v1/fabric/pools/schedule."""
        payload = {
            "workload_id": workload_id,
            "prefill_tokens": prefill_tokens,
            "decode_tokens": decode_tokens,
            "quantum_hilbert_dim": quantum_hilbert_dim,
            "require_zero_stall": require_zero_stall,
        }
        return self._request("POST", "/v1/fabric/pools/schedule", json=payload)

    def reconcile_settlement(
        self,
        tenant_id: str,
        period: str = "2026-Q1",
        counterfactual_cloud_spend_usd: float = 520000.00,
        actual_cloud_spend_usd: float = 317500.00,
        incremental_chronus_costs_usd: float = 0.00,
    ) -> Dict[str, Any]:
        """Calculate Hermiten 25% Value-Share settlement via POST /v1/billing/hermiten/settlement."""
        payload = {
            "tenant_id": tenant_id,
            "period": period,
            "counterfactual_cloud_spend_usd": counterfactual_cloud_spend_usd,
            "actual_cloud_spend_usd": actual_cloud_spend_usd,
            "incremental_chronus_costs_usd": incremental_chronus_costs_usd,
        }
        return self._request("POST", "/v1/billing/hermiten/settlement", json=payload)

    def onboard_instant_tenant(
        self,
        tenant_id: str,
        organization_name: str,
        requested_warps: int = 256,
        aws_kms_key_arn: Optional[str] = None,
        contact_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Instant tenant onboarding under ECA via POST /v1/tenants/onboard/instant."""
        payload = {
            "tenant_id": tenant_id,
            "organization_name": organization_name,
            "requested_warps": requested_warps,
            "aws_kms_key_arn": aws_kms_key_arn
            or "arn:aws:kms:us-east-1:112233445566:key/chronus-pkcs11-custody",
            "contact_email": contact_email or f"admin@{tenant_id}.internal",
        }
        return self._request("POST", "/v1/tenants/onboard/instant", json=payload)

    def execute_agentic_sheaf_turn(
        self,
        agent_states: Optional[Dict[str, List[float]]] = None,
        stalk_dim: int = 4,
    ) -> Dict[str, Any]:
        """Verify and execute turn with Cellular Sheaf cohomology and 1-cycle DSW healing."""
        states = agent_states or {
            "Planner": [1.0, 0.0, 0.0, 1.0],
            "Coder": [1.0, 0.0, 0.0, 1.0],
            "Executor": [1.0, 0.0, 0.0, 1.0],
            "Tool": [1.0, 0.0, 0.0, 1.0],
        }
        return self._request(
            "POST",
            "/v1/al-haras/applications/agentic-sheaf/verify-turn",
            json={"agent_states": states, "stalk_dim": stalk_dim},
        )

    def transmit_orbital_telemetry(
        self,
        packet_payload: str = "SDA_PWSA_TELEMETRY_STREAM_PACKET_001",
        source_sat: str = "SAT_00",
        target_sat: str = "SAT_07",
        constellation_size: int = 16,
    ) -> Dict[str, Any]:
        """Transmit satellite telemetry over PSL_2(F_257) Ramanujan LPS Expander."""
        return self._request(
            "POST",
            "/v1/al-haras/applications/orbital-mesh/transmit",
            json={
                "packet_payload": packet_payload,
                "source_sat": source_sat,
                "target_sat": target_sat,
                "constellation_size": constellation_size,
            },
        )

    def prove_and_verify_zk_neural(
        self,
        sensor_input: Optional[List[int]] = None,
        weights_commitment: str = "sovereign_weights_merkle_root_v4_7f9c2b",
    ) -> Dict[str, Any]:
        """Generate and verify line-rate FRI zk-STARK neural inference proof."""
        return self._request(
            "POST",
            "/v1/al-haras/applications/zk-neural/prove-and-verify",
            json={
                "sensor_input": sensor_input or [12, 24, 36, 48],
                "weights_commitment": weights_commitment,
            },
        )

    def process_cbdc_cross_border_settlement(
        self,
        sender_bank: str = "FEDERAL_RESERVE",
        receiver_bank: str = "BANK_OF_ENGLAND",
        amount_tokens: int = 10_000_000,
        simulate_double_spend: bool = False,
    ) -> Dict[str, Any]:
        """Process wholesale CBDC cross-border transfer under homological conservation partial_1=0."""
        return self._request(
            "POST",
            "/v1/al-haras/applications/cbdc-settlement/process",
            json={
                "sender_bank": sender_bank,
                "receiver_bank": receiver_bank,
                "amount_tokens": amount_tokens,
                "simulate_double_spend": simulate_double_spend,
            },
        )

    def execute_t_isa_microcode(
        self,
        funct7: int = 0x02,
        rs1_val: Optional[Tuple[int, int, int, int]] = (1, 2, 0, 0),
        rs2_val: Optional[Tuple[int, int, int, int]] = (3, 1, 0, 0),
        rs1: int = 1,
        rs2: int = 2,
        rd: int = 3,
    ) -> Dict[str, Any]:
        """Execute T-ISA instruction on RISC-V RoCC silicon ALU."""
        return self._request(
            "POST",
            "/v1/al-haras/applications/t-isa/execute",
            json={
                "funct7": funct7,
                "rs1": rs1,
                "rs2": rs2,
                "rd": rd,
                "rs1_val": list(rs1_val or (1, 2, 0, 0)),
                "rs2_val": list(rs2_val or (3, 1, 0, 0)),
            },
        )

    def route_euclid_workload(
        self,
        workload_type: str,
        content: Optional[str] = None,
        agent_states: Optional[Dict[str, Any]] = None,
        bus_saturation_pct: float = 100.0,
    ) -> Dict[str, Any]:
        """Route workload via EUCLID 5-Mode Meta-Intelligence Engine."""
        return self._request(
            "POST",
            "/euclid/route",
            json={
                "workload_type": workload_type,
                "content": content,
                "agent_states": agent_states,
                "bus_saturation_pct": bus_saturation_pct,
            },
        )

    def get_euclid_telemetry(self) -> Dict[str, Any]:
        """Retrieve EUCLID DEC Fluid and Lie-Poisson telemetry."""
        return self._request("GET", "/euclid/telemetry")

    def get_mining_status(self) -> Dict[str, Any]:
        """Retrieve real-time mining administration status."""
        return self._request("GET", "/v1/mining/admin/status")

    def start_mining(
        self,
        base_hashrate_eh_s: Optional[float] = None,
        active_warps: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Start mining engine with specified hashrate and warp allocation."""
        return self._request(
            "POST",
            "/v1/mining/admin/start",
            json={
                "base_hashrate_eh_s": base_hashrate_eh_s,
                "active_warps": active_warps,
            },
        )

    def stop_mining(self) -> Dict[str, Any]:
        """Stop active mining engine."""
        return self._request("POST", "/v1/mining/admin/stop")

    def configure_mining_capacity(
        self,
        base_hashrate_eh_s: Optional[float] = None,
        active_warps: Optional[int] = None,
        core_voltage_v: Optional[float] = None,
        fan_speed_pct: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Dynamically configure hashrate, warps, and die voltage."""
        return self._request(
            "POST",
            "/v1/mining/admin/configure",
            json={
                "base_hashrate_eh_s": base_hashrate_eh_s,
                "active_warps": active_warps,
                "core_voltage_v": core_voltage_v,
                "fan_speed_pct": fan_speed_pct,
            },
        )

    def configure_mining_intelligence(
        self,
        predictive: float,
        causal: float,
        counterfactual: float,
        topological: float,
        geometric: float,
    ) -> Dict[str, Any]:
        """Rebalance 5-mode meta-intelligence distribution."""
        return self._request(
            "POST",
            "/v1/mining/admin/intelligence",
            json={
                "predictive": predictive,
                "causal": causal,
                "counterfactual": counterfactual,
                "topological": topological,
                "geometric": geometric,
            },
        )

    def apply_mining_causal_intervention(self, intervention: str) -> Dict[str, Any]:
        """Apply Pearl Level 2 do(X) intervention."""
        return self._request(
            "POST",
            "/v1/mining/admin/intervene",
            json={"intervention": intervention},
        )

    def inject_mining_anomaly(self) -> Dict[str, Any]:
        """Simulate reorg or stratum poisoning perturbation."""
        return self._request("POST", "/v1/mining/admin/anomaly/inject")

    def heal_mining_anomaly(self) -> Dict[str, Any]:
        """Trigger 1-cycle DSW instanton monopole cobordism heal."""
        return self._request("POST", "/v1/mining/admin/anomaly/heal")

    def get_patroclus_telemetry(self) -> Dict[str, Any]:
        """Retrieve Patroclus Gateway & 600 Myrmidon Searchers telemetry."""
        return self._request("GET", "/v1/mining/admin/patroclus")

    def configure_mining_stealth(
        self,
        max_configured_eh_s: Optional[float] = None,
        stealth_target_eh_s: Optional[float] = None,
        never_consecutive_blocks: Optional[bool] = None,
        persistent_presence: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Configure stealth hashrate shaping and block suppression policies."""
        payload: Dict[str, Any] = {}
        if max_configured_eh_s is not None:
            payload["max_configured_eh_s"] = max_configured_eh_s
        if stealth_target_eh_s is not None:
            payload["stealth_target_eh_s"] = stealth_target_eh_s
        if never_consecutive_blocks is not None:
            payload["never_consecutive_blocks"] = never_consecutive_blocks
        if persistent_presence is not None:
            payload["persistent_presence"] = persistent_presence
        return self._request("POST", "/v1/mining/admin/stealth", json=payload)

    def simulate_patroclus_mining(self, pools: Optional[list] = None) -> Dict[str, Any]:
        """Simulate multi-pool Stratum V1 handshake and share acceptance."""
        return self._request(
            "POST",
            "/v1/mining/admin/patroclus/simulate",
            json={"pools": pools},
        )

    def get_metrics(self) -> str:
        response = self._client.get("/metrics")
        if response.status_code != 200:
            raise ChronusSDKError(
                "Chronus metrics endpoint failed",
                status_code=response.status_code,
            )
        return response.text

    def get_stats(self) -> Dict[str, Any]:
        average = (
            self._total_latency_ms / self._request_count if self._request_count else 0.0
        )
        return {
            "sdk_version": self.SDK_VERSION,
            "tenant_id": self.tenant_id,
            "region": self.region,
            "request_count": self._request_count,
            "total_latency_ms": round(self._total_latency_ms, 3),
            "average_latency_ms": round(average, 3),
        }


# Canonical alias for SDK client
ChronusClient = ChronusAPISDK

