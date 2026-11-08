"""Chronus CIaaS Instant Provisioning & Enduring Capacity Engine.

Implements the 4-Stage Zero-Friction Provisioning Architecture (< 30s T0 SLA):
- Stage 1: Contract Signature & Webhook Ingress (DocuSign / Ironclad / CPQ / System Admin)
- Stage 2: Automated Tenant Provisioning & Storage Fabrics (PostgreSQL REPEATABLE READ + OVID o1_<tenant> + THESEUS Journal)
- Stage 3: AL HARAS Security Authority & KMS Key Deployment (4-Tier RBAC + PKCS#11 Cloud KMS Custody + Encrypted Handoff)
- Stage 4: Enduring CCE & Dynamic Self-Service Expansion (Zero-Addendum Scaling + Hermiten 25% Value-Share Settlement)
"""

import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
from typing import Any, Dict, List, Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import BaseModel, Field, model_validator

import chronus.execution  # noqa: F401 - ensure execution package initializes before storage.connectors
from chronus.security.kms import (
    SUPPORTED_CUSTOMER_KMS_PROVIDERS,
    al_haras_kms_custody,
)
from chronus.service.auth_middleware import Role, create_jwt_token
from chronus.service.ciaas_store import (
    CIaaSStore,
    ChronusCapacityEntitlement,
    HermitenSettlement,
    PricingBreakdown,
    TenantProfile,
    ciaas_store,
)
from chronus.service.dependencies import auth_service
from chronus.service.postgres_store import PostgresWorkloadStore
from chronus.storage.theseus import (
    TenantStorageFabricRegistry,
    tenant_storage_registry,
)

MAX_ENDURING_WARP_CEILING = 160000


class ProvisioningConflictError(RuntimeError):
    """Raised when a tenant_id or contract_id has already been provisioned."""


class EnduringAddendumError(PermissionError):
    """Raised when self-service capacity scaling violates ECA terms."""


class InstantCCEAllocations(BaseModel):
    """Initial and pre-authorized Enduring Capacity Addendum (ECA) allocations."""

    initial_warps: int = Field(
        default=32,
        ge=1,
        le=MAX_ENDURING_WARP_CEILING,
        description="Initial active 32-lane execution warps at T0 activation",
    )
    max_authorized_warps: int = Field(
        default=1024,
        ge=1,
        le=MAX_ENDURING_WARP_CEILING,
        description="Maximum pre-authorized warps under Enduring Capacity Addendum",
    )
    data_at_rest_gb: int = Field(
        default=10000,
        ge=1,
        le=100000000,
        description="Provisioned OVID/THESEUS data-at-rest storage in GB (up to 100 PB)",
    )
    data_in_motion_gb: int = Field(
        default=5000,
        ge=1,
        le=100000000,
        description="Provisioned data-in-motion fabric bandwidth quota in GB (up to 100 PB)",
    )
    o1_structural_memory_gb: int = Field(
        default=256,
        ge=1,
        le=65536,
        description="O(1) structural collapse memory allocation in GB",
    )
    kms_provider: str = Field(
        default="AWS_KMS",
        description="Customer cloud KMS / HSM provider (AWS_KMS, AZURE_KEY_VAULT, HASHICORP_VAULT, GCP_KMS, PKCS11_HSM)",
    )
    kms_key_arn: str = Field(
        ...,
        min_length=4,
        max_length=512,
        description="Customer-held KMS key ARN, Vault path, or PKCS#11 URI",
    )

    @model_validator(mode="after")
    def validate_bounds_and_kms(self) -> "InstantCCEAllocations":
        if self.initial_warps > self.max_authorized_warps:
            raise ValueError(
                f"initial_warps ({self.initial_warps}) cannot exceed "
                f"max_authorized_warps ({self.max_authorized_warps})"
            )
        normalized = self.kms_provider.strip().upper()
        if normalized not in SUPPORTED_CUSTOMER_KMS_PROVIDERS:
            raise ValueError(
                f"Unsupported kms_provider '{self.kms_provider}'. "
                f"Allowed: {sorted(SUPPORTED_CUSTOMER_KMS_PROVIDERS)}"
            )
        self.kms_provider = normalized
        return self


class InstantOnboardRequest(BaseModel):
    """Stage 1 automated e-signature webhook / system-admin onboarding payload."""

    contract_id: str = Field(..., min_length=3, max_length=128)
    company_name: str = Field(..., min_length=2, max_length=256)
    tenant_id: str = Field(..., min_length=3, max_length=128)
    admin_email: str = Field(..., min_length=5, max_length=256)
    enduring_addendum_accepted: bool = Field(default=True)
    cce_allocations: InstantCCEAllocations
    regional_pod: str = Field(default="alpha")
    webhook_source: str = Field(
        default="DOCUSIGN_MSA_WEBHOOK",
        description="Originating CLM/CPQ event source (DocuSign, Ironclad, Salesforce CPQ, Console)",
    )


class ProvisioningStageTelemetry(BaseModel):
    """Sub-millisecond stage-by-stage timing across the 4-Stage Architecture."""

    stage_1_webhook_ingress_ms: float
    stage_2_fabric_provision_ms: float
    stage_3_al_haras_kms_ms: float
    stage_4_enduring_cce_ready_ms: float
    total_execution_ms: float
    sla_target_ms: float = 30000.0
    sla_met: bool = True


class CredentialHandoffEnvelope(BaseModel):
    """Encrypted welcome payload metadata delivered to the client Security Officer."""

    recipient_security_officer: str
    encryption_scheme: str = "AES-256-GCM+PKCS11-KEY-WRAP"
    sealed_ciphertext_b64: str
    sealed_envelope_sha256: str
    sdk_api_key: str
    developer_token: str
    oauth2_token_endpoint: str
    sso_oidc_metadata_url: str


class InstantOnboardResponse(BaseModel):
    """201 Created response for POST /v1/tenants/onboard/instant."""

    status: str = "TENANT_PROVISIONED_INSTANTLY"
    tenant_id: str
    assigned_cce_id: str
    al_haras_kms_status: str = "KMS_BOUND_CUSTOMER_CUSTODY"
    tenant_admin_token: str
    console_access_url: str
    zero_copy_prefix: str
    contract_id: str
    company_name: str
    enduring_addendum_accepted: bool
    execution_time_ms: float
    ovid_namespace: str
    theseus_genesis_entry_hash: str
    postgres_isolation: Dict[str, Any]
    kms_binding: Dict[str, Any]
    credential_handoff: CredentialHandoffEnvelope
    stage_telemetry: ProvisioningStageTelemetry
    cce_allocations: Optional[Dict[str, Any]] = None


class CapacityExpansionRequest(BaseModel):
    """Stage 4 self-service capacity update payload (PATCH /v1/tenants/{tenant_id}/capacity)."""

    requested_warp_capacity: int = Field(
        ...,
        ge=1,
        le=MAX_ENDURING_WARP_CEILING,
        description="Target active 32-lane execution warps",
    )
    expand_storage_gb: Optional[int] = Field(
        default=None,
        ge=1,
        le=1000000,
        description="Updated OVID/THESEUS data-at-rest storage limit in GB",
    )
    o1_structural_memory_gb: Optional[int] = Field(
        default=None,
        ge=1,
        le=65536,
        description="Updated O(1) structural collapse memory limit in GB",
    )
    reason: str = Field(
        default="SELF_SERVICE_CONSOLE_SCALING",
        min_length=1,
        max_length=256,
        description="Operational audit tag for burst or enduring scale change",
    )


class CapacityExpansionResponse(BaseModel):
    """200 OK response for PATCH /v1/tenants/{tenant_id}/capacity."""

    status: str = "CAPACITY_EXPANDED_INSTANTLY"
    tenant_id: str
    previous_warps: int
    new_active_warps: int
    enduring_addendum_valid: bool = True
    additional_approval_required: bool = False
    previous_storage_gb: int
    new_storage_gb: int
    o1_structural_memory_gb: int
    max_authorized_warps: int
    assigned_cce_id: str
    reason: str
    execution_time_ms: float
    theseus_journal_entry_hash: str
    pricing_breakdown: PricingBreakdown
    hermiten_settlement: HermitenSettlement


class TenantCapacityStatusResponse(BaseModel):
    """Live Enduring Capacity Addendum, storage fabric, and FinOps settlement state."""

    tenant_id: str
    organization_name: str
    contract_id: str
    assigned_cce_id: str
    regional_pod: str
    enduring_addendum_valid: bool
    additional_approval_required: bool
    active_warps: int
    max_authorized_warps: int
    data_at_rest_gb: int
    data_in_motion_gb: int
    o1_structural_memory_gb: int
    compute_intensity_ccu: int
    al_haras_kms_status: str
    kms_provider: str
    kms_key_arn: str
    ovid_namespace: str
    zero_copy_prefix: str
    console_access_url: str
    theseus_journal_entries: int
    latest_journal_hash: Optional[str] = None
    postgres_isolation: Dict[str, Any]
    pricing_breakdown: PricingBreakdown
    hermiten_settlement: HermitenSettlement


class LoadSimulationRequest(BaseModel):
    """Parameters for concurrent instant tenant activation stress test."""

    tenant_count: int = Field(
        default=500,
        ge=1,
        le=1000,
        description="Number of concurrent tenant activations to execute",
    )
    concurrency_workers: int = Field(
        default=32,
        ge=1,
        le=128,
        description="Worker threads simulating simultaneous webhook bursts",
    )
    cleanup_ephemeral: bool = Field(
        default=True,
        description="Clean up ephemeral simulation tenants after verification",
    )


class LoadSimulationResponse(BaseModel):
    """Aggregated telemetry from concurrent tenant onboarding simulation."""

    status: str = "LOAD_SIMULATION_PASSED"
    tenants_requested: int
    tenants_activated: int
    concurrency_workers: int
    total_wall_time_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    max_latency_ms: float
    throughput_tenants_per_sec: float
    sla_target_seconds: int = 30
    under_30_second_sla: bool
    kms_custody_verified_count: int
    theseus_continuity_verified_count: int


def verify_webhook_hmac_signature(
    raw_body: bytes,
    signature_header: Optional[str],
    webhook_secret: Optional[str] = None,
) -> bool:
    """Verify HMAC-SHA256 webhook signature from DocuSign, Ironclad, or Salesforce CPQ."""
    secret = webhook_secret or os.getenv("CHRONUS_WEBHOOK_SECRET", "")
    if not secret or not signature_header:
        return False

    cleaned = signature_header.strip()
    if cleaned.lower().startswith("sha256="):
        cleaned = cleaned.split("=", 1)[1].strip()

    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
    expected_hex = digest.hex()
    expected_b64 = base64.b64encode(digest).decode("ascii")

    return hmac.compare_digest(
        cleaned.lower(), expected_hex.lower()
    ) or hmac.compare_digest(cleaned, expected_b64)


def _extract_org_slug(tenant_id: str, company_name: str) -> str:
    """Derive short deterministic slug (e.g. 'tenant_apex_9921a' -> 'apex')."""
    stripped = re.sub(r"^tenant[_-]+", "", tenant_id.strip().lower())
    tokens = [tok for tok in re.split(r"[^a-z0-9]+", stripped) if tok]
    if tokens and tokens[0] not in ("id", "org", "prod", "test"):
        return tokens[0][:24]
    company_tokens = [
        tok for tok in re.split(r"[^a-z0-9]+", company_name.strip().lower()) if tok
    ]
    if company_tokens:
        return company_tokens[0][:24]
    return "enterprise"


class InstantProvisioningEngine:
    """Orchestrates 4-Stage Zero-Friction Tenant Onboarding & Dynamic Capacity Scaling."""

    def __init__(
        self,
        store: Optional[CIaaSStore] = None,
        storage_registry: Optional[TenantStorageFabricRegistry] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._store = store or ciaas_store
        self._storage_registry = storage_registry or tenant_storage_registry
        self._assigned_cce_ids: Dict[str, str] = {}
        self._contracts: Dict[str, str] = {}
        self._postgres_descriptors: Dict[str, Dict[str, Any]] = {}

        # Index pre-seeded baseline tenants
        for existing in self._store.list_tenants():
            if existing.assigned_cce_id:
                self._assigned_cce_ids[existing.assigned_cce_id] = existing.tenant_id
            if existing.contract_id:
                self._contracts[existing.contract_id] = existing.tenant_id
            self._postgres_descriptors[existing.tenant_id] = (
                PostgresWorkloadStore.build_tenant_isolation_descriptor(
                    existing.tenant_id
                )
            )

    def _allocate_cce_id(self, tenant_id: str, slug: str) -> str:
        """Assign deterministic CCE identifier (e.g. 'cce_apex_2026_q4'), disambiguating collisions."""
        now_utc = datetime.now(timezone.utc)
        quarter = (now_utc.month - 1) // 3 + 1
        base_cce_id = f"cce_{slug}_{now_utc.year}_q{quarter}"
        owner = self._assigned_cce_ids.get(base_cce_id)
        if owner is None or owner == tenant_id:
            self._assigned_cce_ids[base_cce_id] = tenant_id
            return base_cce_id

        full_slug = re.sub(
            r"[^a-z0-9_]+", "_", re.sub(r"^tenant[_-]+", "", tenant_id.lower())
        ).strip("_")
        candidate = f"cce_{full_slug}_{now_utc.year}_q{quarter}"
        if candidate not in self._assigned_cce_ids:
            self._assigned_cce_ids[candidate] = tenant_id
            return candidate

        unique_cce = f"{base_cce_id}_{secrets.token_hex(3)}"
        self._assigned_cce_ids[unique_cce] = tenant_id
        return unique_cce

    @staticmethod
    def _seal_welcome_envelope(
        handoff_payload: Dict[str, Any],
        kms_fingerprint_hex: str,
    ) -> tuple[str, str]:
        """Encrypt credential handoff payload under customer KMS key fingerprint."""
        aes_key = bytes.fromhex(kms_fingerprint_hex[:64])
        nonce = secrets.token_bytes(12)
        plaintext = json.dumps(handoff_payload, sort_keys=True).encode("utf-8")
        ciphertext = AESGCM(aes_key).encrypt(
            nonce, plaintext, b"CHRONUS_AL_HARAS_HANDOFF_V1"
        )
        envelope_bytes = nonce + ciphertext
        envelope_b64 = base64.b64encode(envelope_bytes).decode("ascii")
        envelope_sha256 = hashlib.sha256(envelope_bytes).hexdigest()
        return envelope_b64, envelope_sha256

    def calculate_dynamic_settlement(
        self,
        tenant_id: str,
        active_warps: int,
        storage_gb: int,
    ) -> HermitenSettlement:
        """Reconcile real-time Hermiten 25% Value-Share settlement from active CCE usage."""
        counterfactual_cost = active_warps * 3750 + (storage_gb // 10) * 12
        actual_cost = active_warps * 875 + (storage_gb // 10) * 3
        incremental_cost = max(1000, active_warps * 125)
        return self._store.calculate_hermiten_settlement(
            tenant_id=tenant_id,
            counterfactual_cost=counterfactual_cost,
            actual_cost=actual_cost,
            incremental_cost=incremental_cost,
        )

    def provision_instant_tenant(
        self,
        request: InstantOnboardRequest,
        register_auth_token: bool = True,
    ) -> InstantOnboardResponse:
        """Execute Stages 1-4 of the Zero-Friction Instant Provisioning Engine."""
        t0_ns = time.perf_counter_ns()

        # ------------------------------------------------------------------
        # Stage 1: Contract Signature & Webhook Ingress Validation
        # ------------------------------------------------------------------
        with self._lock:
            if self._store.get_tenant(request.tenant_id) is not None:
                raise ProvisioningConflictError(
                    f"Tenant '{request.tenant_id}' is already provisioned."
                )
            if request.contract_id in self._contracts:
                raise ProvisioningConflictError(
                    f"Contract '{request.contract_id}' has already been activated."
                )
            slug = _extract_org_slug(request.tenant_id, request.company_name)
            assigned_cce_id = self._allocate_cce_id(request.tenant_id, slug)
            self._contracts[request.contract_id] = request.tenant_id

        t1_ns = time.perf_counter_ns()

        # ------------------------------------------------------------------
        # Stage 2: Automated Tenant Provisioning & Storage Fabrics
        # ------------------------------------------------------------------
        pg_descriptor = PostgresWorkloadStore.build_tenant_isolation_descriptor(
            tenant_id=request.tenant_id,
            pool_size=10,
            isolation_level="REPEATABLE READ",
        )
        ovid_namespace = TenantStorageFabricRegistry.namespace_for(request.tenant_id)
        genesis_doc = {
            "event": "MSA_INSTANT_T0_ACTIVATION",
            "contract_id": request.contract_id,
            "company_name": request.company_name,
            "tenant_id": request.tenant_id,
            "assigned_cce_id": assigned_cce_id,
            "enduring_addendum_accepted": request.enduring_addendum_accepted,
            "initial_warps": request.cce_allocations.initial_warps,
            "max_authorized_warps": request.cce_allocations.max_authorized_warps,
            "data_at_rest_gb": request.cce_allocations.data_at_rest_gb,
            "data_in_motion_gb": request.cce_allocations.data_in_motion_gb,
            "webhook_source": request.webhook_source,
        }
        genesis_entry = self._storage_registry.initialize_tenant_fabric(
            tenant_id=request.tenant_id,
            genesis_payload=json.dumps(genesis_doc, sort_keys=True).encode("utf-8"),
        )
        t2_ns = time.perf_counter_ns()

        # ------------------------------------------------------------------
        # Stage 3: AL HARAS Security Authority & KMS Key Deployment
        # ------------------------------------------------------------------
        kms_binding = al_haras_kms_custody.ingest_customer_key(
            tenant_id=request.tenant_id,
            kms_provider=request.cce_allocations.kms_provider,
            kms_key_arn=request.cce_allocations.kms_key_arn,
        )

        zero_copy_prefix = f"ptr_sdk_{slug}_"
        sdk_api_key = f"{zero_copy_prefix}{secrets.token_hex(12)}"

        tenant_admin_token = create_jwt_token(
            tenant_id=request.tenant_id,
            user_id=request.admin_email,
            role=Role.TENANT_ADMIN,
            expires_in_seconds=86400 * 30,
            additional_claims={
                "contract_id": request.contract_id,
                "assigned_cce_id": assigned_cce_id,
                "enduring_addendum_accepted": request.enduring_addendum_accepted,
            },
        )
        developer_token = create_jwt_token(
            tenant_id=request.tenant_id,
            user_id=f"dev@{slug}.tenant.chronus.io",
            role=Role.DEVELOPER,
            expires_in_seconds=86400 * 30,
            additional_claims={
                "zero_copy_prefix": zero_copy_prefix,
                "ovid_namespace": ovid_namespace,
            },
        )

        if register_auth_token:
            auth_service.register_tenant(request.tenant_id, sdk_api_key)

        console_base = os.getenv(
            "CHRONUS_CONSOLE_BASE_URL", "https://console.chronus.io"
        ).rstrip("/")
        console_access_url = f"{console_base}/tenants/{request.tenant_id}/workloads"
        oauth2_endpoint = f"{console_base}/v1/auth/token"
        sso_metadata_url = (
            f"{console_base}/v1/tenants/{request.tenant_id}/sso/oidc-configuration"
        )

        welcome_payload = {
            "tenant_id": request.tenant_id,
            "contract_id": request.contract_id,
            "assigned_cce_id": assigned_cce_id,
            "sdk_api_key": sdk_api_key,
            "tenant_admin_token": tenant_admin_token,
            "developer_token": developer_token,
            "oauth2_token_endpoint": oauth2_endpoint,
            "sso_oidc_metadata_url": sso_metadata_url,
            "kms_pkcs11_slot_uri": kms_binding.pkcs11_slot_uri,
        }
        sealed_b64, sealed_sha256 = self._seal_welcome_envelope(
            welcome_payload,
            kms_binding.public_key_fingerprint_sha256,
        )
        handoff = CredentialHandoffEnvelope(
            recipient_security_officer=request.admin_email,
            sealed_ciphertext_b64=sealed_b64,
            sealed_envelope_sha256=sealed_sha256,
            sdk_api_key=sdk_api_key,
            developer_token=developer_token,
            oauth2_token_endpoint=oauth2_endpoint,
            sso_oidc_metadata_url=sso_metadata_url,
        )
        t3_ns = time.perf_counter_ns()

        # ------------------------------------------------------------------
        # Stage 4: Enduring CCE Registration & Cluster Activation
        # ------------------------------------------------------------------
        alloc = request.cce_allocations
        cce = ChronusCapacityEntitlement(
            data_at_rest_gb=alloc.data_at_rest_gb,
            data_in_motion_gb=alloc.data_in_motion_gb,
            data_processed_gb=max(alloc.data_at_rest_gb * 4, 16384),
            compute_intensity_ccu=alloc.initial_warps * 16,
            concurrency_limit=alloc.initial_warps,
        )
        profile = TenantProfile(
            tenant_id=request.tenant_id,
            organization_name=request.company_name,
            admin_email=request.admin_email,
            regional_pod=request.regional_pod,
            status="ACTIVE",
            created_at=time.time(),
            cce=cce,
            api_key_prefix=zero_copy_prefix,
            sovereign_profile_enabled=True,
            contract_id=request.contract_id,
            assigned_cce_id=assigned_cce_id,
            enduring_addendum_accepted=request.enduring_addendum_accepted,
            max_authorized_warps=alloc.max_authorized_warps,
            o1_structural_memory_gb=alloc.o1_structural_memory_gb,
            kms_provider=kms_binding.kms_provider,
            kms_key_arn=kms_binding.kms_key_arn,
            al_haras_kms_status=kms_binding.status,
            ovid_namespace=ovid_namespace,
            console_access_url=console_access_url,
        )

        with self._lock:
            self._postgres_descriptors[request.tenant_id] = pg_descriptor
            self._store.save_tenant(profile)

        from chronus.storage.connectors import zero_copy_connector_manager

        if request.enduring_addendum_accepted:
            zero_copy_connector_manager.authorize_eca(
                tenant_id=request.tenant_id,
                kms_provider=kms_binding.kms_provider,
                kms_key_arn=kms_binding.kms_key_arn,
            )

        t4_ns = time.perf_counter_ns()

        s1_ms = round((t1_ns - t0_ns) / 1_000_000, 4)
        s2_ms = round((t2_ns - t1_ns) / 1_000_000, 4)
        s3_ms = round((t3_ns - t2_ns) / 1_000_000, 4)
        s4_ms = round((t4_ns - t3_ns) / 1_000_000, 4)
        total_ms = round((t4_ns - t0_ns) / 1_000_000, 4)

        telemetry = ProvisioningStageTelemetry(
            stage_1_webhook_ingress_ms=s1_ms,
            stage_2_fabric_provision_ms=s2_ms,
            stage_3_al_haras_kms_ms=s3_ms,
            stage_4_enduring_cce_ready_ms=s4_ms,
            total_execution_ms=total_ms,
            sla_target_ms=30000.0,
            sla_met=total_ms < 30000.0,
        )

        return InstantOnboardResponse(
            status="TENANT_PROVISIONED_INSTANTLY",
            tenant_id=request.tenant_id,
            assigned_cce_id=assigned_cce_id,
            al_haras_kms_status=kms_binding.status,
            tenant_admin_token=tenant_admin_token,
            console_access_url=console_access_url,
            zero_copy_prefix=zero_copy_prefix,
            contract_id=request.contract_id,
            company_name=request.company_name,
            enduring_addendum_accepted=request.enduring_addendum_accepted,
            execution_time_ms=total_ms,
            ovid_namespace=ovid_namespace,
            theseus_genesis_entry_hash=genesis_entry.entry_hash,
            postgres_isolation=pg_descriptor,
            kms_binding=kms_binding.to_dict(),
            credential_handoff=handoff,
            stage_telemetry=telemetry,
            cce_allocations=(
                request.cce_allocations.model_dump()
                if request.cce_allocations
                else None
            ),
        )

    def expand_capacity(
        self,
        tenant_id: str,
        request: CapacityExpansionRequest,
    ) -> CapacityExpansionResponse:
        """Dynamically scale active warps and storage under the Enduring Capacity Addendum."""
        started_ns = time.perf_counter_ns()

        with self._lock:
            tenant = self._store.get_tenant(tenant_id)
            if tenant is None:
                raise KeyError(f"Tenant '{tenant_id}' not found.")

            if not tenant.enduring_addendum_accepted:
                raise EnduringAddendumError(
                    f"Tenant '{tenant_id}' has not accepted the Enduring Capacity Addendum (ECA); "
                    "manual legal addendum signature required."
                )

            max_warps = tenant.max_authorized_warps or MAX_ENDURING_WARP_CEILING
            if request.requested_warp_capacity > max_warps:
                raise EnduringAddendumError(
                    f"Requested warp capacity ({request.requested_warp_capacity}) exceeds "
                    f"pre-authorized ECA ceiling ({max_warps} warps)."
                )

            previous_warps = tenant.cce.concurrency_limit
            previous_storage_gb = tenant.cce.data_at_rest_gb
            new_warps = request.requested_warp_capacity
            new_storage_gb = (
                request.expand_storage_gb
                if request.expand_storage_gb is not None
                else previous_storage_gb
            )
            new_o1_mem = (
                request.o1_structural_memory_gb
                if request.o1_structural_memory_gb is not None
                else tenant.o1_structural_memory_gb
            )

            updated_cce = ChronusCapacityEntitlement(
                data_at_rest_gb=new_storage_gb,
                data_in_motion_gb=max(
                    tenant.cce.data_in_motion_gb, new_storage_gb // 2
                ),
                data_processed_gb=max(tenant.cce.data_processed_gb, new_storage_gb * 4),
                compute_intensity_ccu=new_warps * 16,
                concurrency_limit=new_warps,
            )
            tenant.cce = updated_cce
            tenant.o1_structural_memory_gb = new_o1_mem
            self._store.save_tenant(tenant)
            assigned_cce_id = tenant.assigned_cce_id or f"cce_{tenant_id}"

        journal_payload = json.dumps(
            {
                "event": "ENDURING_CCE_SELF_SERVICE_EXPANSION",
                "tenant_id": tenant_id,
                "assigned_cce_id": assigned_cce_id,
                "previous_warps": previous_warps,
                "new_active_warps": new_warps,
                "previous_storage_gb": previous_storage_gb,
                "new_storage_gb": new_storage_gb,
                "o1_structural_memory_gb": new_o1_mem,
                "reason": request.reason,
            },
            sort_keys=True,
        ).encode("utf-8")
        journal_entry = self._storage_registry.append_journal_event(
            tenant_id=tenant_id,
            event_type="CAPACITY_EXPANDED_INSTANTLY",
            payload=journal_payload,
        )

        pricing = self._store.calculate_pricing(
            tenant_id=tenant_id,
            consumed_ccu=new_warps * 8,
        )
        settlement = self.calculate_dynamic_settlement(
            tenant_id=tenant_id,
            active_warps=new_warps,
            storage_gb=new_storage_gb,
        )

        elapsed_ms = round((time.perf_counter_ns() - started_ns) / 1_000_000, 4)

        return CapacityExpansionResponse(
            status="CAPACITY_EXPANDED_INSTANTLY",
            tenant_id=tenant_id,
            previous_warps=previous_warps,
            new_active_warps=new_warps,
            enduring_addendum_valid=True,
            additional_approval_required=False,
            previous_storage_gb=previous_storage_gb,
            new_storage_gb=new_storage_gb,
            o1_structural_memory_gb=new_o1_mem,
            max_authorized_warps=max_warps,
            assigned_cce_id=assigned_cce_id,
            reason=request.reason,
            execution_time_ms=elapsed_ms,
            theseus_journal_entry_hash=journal_entry.entry_hash,
            pricing_breakdown=pricing,
            hermiten_settlement=settlement,
        )

    def get_capacity_status(self, tenant_id: str) -> TenantCapacityStatusResponse:
        """Inspect live Enduring Capacity Addendum state, storage fabric, and Hermiten settlement."""
        with self._lock:
            tenant = self._store.get_tenant(tenant_id)
            if tenant is None:
                raise KeyError(f"Tenant '{tenant_id}' not found.")
            pg_descriptor = self._postgres_descriptors.get(
                tenant_id,
                PostgresWorkloadStore.build_tenant_isolation_descriptor(tenant_id),
            )

        journal = self._storage_registry.get_journal(tenant_id)
        latest_hash = journal[-1].entry_hash if journal else None
        active_warps = tenant.cce.concurrency_limit
        storage_gb = tenant.cce.data_at_rest_gb

        pricing = self._store.calculate_pricing(
            tenant_id=tenant_id,
            consumed_ccu=active_warps * 8,
        )
        settlement = self.calculate_dynamic_settlement(
            tenant_id=tenant_id,
            active_warps=active_warps,
            storage_gb=storage_gb,
        )

        return TenantCapacityStatusResponse(
            tenant_id=tenant.tenant_id,
            organization_name=tenant.organization_name,
            contract_id=tenant.contract_id or f"ctr_{tenant.tenant_id}",
            assigned_cce_id=tenant.assigned_cce_id or f"cce_{tenant.tenant_id}",
            regional_pod=tenant.regional_pod,
            enduring_addendum_valid=tenant.enduring_addendum_accepted,
            additional_approval_required=not tenant.enduring_addendum_accepted,
            active_warps=active_warps,
            max_authorized_warps=tenant.max_authorized_warps,
            data_at_rest_gb=storage_gb,
            data_in_motion_gb=tenant.cce.data_in_motion_gb,
            o1_structural_memory_gb=tenant.o1_structural_memory_gb,
            compute_intensity_ccu=tenant.cce.compute_intensity_ccu,
            al_haras_kms_status=tenant.al_haras_kms_status,
            kms_provider=tenant.kms_provider,
            kms_key_arn=tenant.kms_key_arn or "kms://customer-managed/default",
            ovid_namespace=tenant.ovid_namespace or f"o1_{tenant.tenant_id}",
            zero_copy_prefix=tenant.api_key_prefix,
            console_access_url=tenant.console_access_url
            or f"https://console.chronus.io/tenants/{tenant.tenant_id}/workloads",
            theseus_journal_entries=len(journal),
            latest_journal_hash=latest_hash,
            postgres_isolation=pg_descriptor,
            pricing_breakdown=pricing,
            hermiten_settlement=settlement,
        )

    def remove_tenant_completely(self, tenant_id: str) -> None:
        """Clean up ephemeral simulation tenant across store, KMS, and storage registries."""
        with self._lock:
            profile = self._store.get_tenant(tenant_id)
            if profile:
                if profile.assigned_cce_id:
                    self._assigned_cce_ids.pop(profile.assigned_cce_id, None)
                if profile.contract_id:
                    self._contracts.pop(profile.contract_id, None)
            self._postgres_descriptors.pop(tenant_id, None)
            self._store.remove_tenant(tenant_id)
        al_haras_kms_custody.remove_binding(tenant_id)
        self._storage_registry.remove_tenant_fabric(tenant_id)
        from chronus.storage.connectors import zero_copy_connector_manager

        zero_copy_connector_manager.revoke_tenant(tenant_id)

    def simulate_concurrent_activations(
        self,
        sim_request: LoadSimulationRequest,
    ) -> LoadSimulationResponse:
        """Run N concurrent instant tenant activations across all 4 stages."""
        run_tag = secrets.token_hex(4)
        count = sim_request.tenant_count
        pods = ("alpha", "beta", "gamma", "delta")
        providers = ("AWS_KMS", "AZURE_KEY_VAULT", "HASHICORP_VAULT", "PKCS11_HSM")

        requests_batch: List[InstantOnboardRequest] = []
        for idx in range(count):
            t_id = f"tenant_sim_{run_tag}_{idx:04d}"
            c_id = f"ctr_sim_{run_tag}_{idx:04d}"
            provider = providers[idx % len(providers)]
            requests_batch.append(
                InstantOnboardRequest(
                    contract_id=c_id,
                    company_name=f"Enterprise Sim Client {idx:04d}",
                    tenant_id=t_id,
                    admin_email=f"secops+{idx:04d}@sim-enterprise.io",
                    enduring_addendum_accepted=True,
                    regional_pod=pods[idx % len(pods)],
                    webhook_source="DOCUSIGN_CONCURRENT_BURST",
                    cce_allocations=InstantCCEAllocations(
                        initial_warps=32,
                        max_authorized_warps=2048,
                        data_at_rest_gb=10000,
                        data_in_motion_gb=5000,
                        kms_provider=provider,
                        kms_key_arn=f"arn:aws:kms:us-east-1:123456789012:key/sim-{run_tag}-{idx:04d}",
                    ),
                )
            )

        wall_start_ns = time.perf_counter_ns()

        def _activate_one(
            req: InstantOnboardRequest,
        ) -> tuple[InstantOnboardResponse, bool, bool]:
            resp = self.provision_instant_tenant(
                req,
                register_auth_token=not sim_request.cleanup_ephemeral,
            )
            kms_ok = al_haras_kms_custody.verify_binding(req.tenant_id)
            journal_ok = self._storage_registry.verify_journal_continuity(req.tenant_id)
            return resp, kms_ok, journal_ok

        with ThreadPoolExecutor(
            max_workers=sim_request.concurrency_workers
        ) as executor:
            results = list(executor.map(_activate_one, requests_batch))

        wall_ms = round((time.perf_counter_ns() - wall_start_ns) / 1_000_000, 4)

        latencies = sorted(r[0].execution_time_ms for r in results)
        kms_verified = sum(1 for r in results if r[1])
        journal_verified = sum(1 for r in results if r[2])

        if sim_request.cleanup_ephemeral:
            for req in requests_batch:
                self.remove_tenant_completely(req.tenant_id)

        def _percentile(sorted_vals: List[float], pct: int) -> float:
            if not sorted_vals:
                return 0.0
            idx = min(
                len(sorted_vals) - 1, max(0, (len(sorted_vals) * pct + 99) // 100 - 1)
            )
            return round(sorted_vals[idx], 4)

        throughput = round((count * 1000.0) / max(wall_ms, 0.001), 2)

        return LoadSimulationResponse(
            status="LOAD_SIMULATION_PASSED" if wall_ms < 30000.0 else "SLA_EXCEEDED",
            tenants_requested=count,
            tenants_activated=len(results),
            concurrency_workers=sim_request.concurrency_workers,
            total_wall_time_ms=wall_ms,
            p50_latency_ms=_percentile(latencies, 50),
            p95_latency_ms=_percentile(latencies, 95),
            p99_latency_ms=_percentile(latencies, 99),
            max_latency_ms=round(latencies[-1], 4) if latencies else 0.0,
            throughput_tenants_per_sec=throughput,
            sla_target_seconds=30,
            under_30_second_sla=wall_ms < 30000.0,
            kms_custody_verified_count=kms_verified,
            theseus_continuity_verified_count=journal_verified,
        )


instant_provisioning_engine = InstantProvisioningEngine()
