"""OpenAPI endpoints for CIaaS multi-tenancy, AL HARAS RBAC, and commercial settlement.

Exposes:
- GET  /v1/auth/rbac/matrix: Returns the AL HARAS 4-tier privileges matrix.
- POST /v1/auth/token: Mints a scoped JWT token for testing/API access.
- GET  /v1/tenants: Lists onboarded enterprise tenants.
- POST /v1/tenants/onboard: Onboards a new tenant and provisions CCE quotas.
- POST /v1/tenants/onboard/instant: Zero-friction (<30s) automated webhook/admin tenant onboarding.
- POST /v1/tenants/onboard/instant/load-test: Concurrent multi-tenant activation load simulator.
- GET  /v1/tenants/{tenant_id}: Retrieves tenant profile and CCE allocations.
- POST /v1/tenants/{tenant_id}/cce: Updates 5-dimension CCE quotas.
- GET  /v1/tenants/{tenant_id}/capacity: Retrieves Enduring Capacity Addendum (ECA) & FinOps state.
- PATCH /v1/tenants/{tenant_id}/capacity: Dynamic self-service capacity scaling (no addendum required).
- GET  /v1/tenants/{tenant_id}/pricing: Four-part pricing breakdown (P_total).
- POST /v1/tenants/{tenant_id}/settlement: Reconciles Hermiten 25% value-share settlement.
- GET  /v1/fabric/pods: Disaggregated regional fleet pods (alpha..delta) and DEC routing.
- GET  /v1/governance/sovereign: Sovereign profile, NCSC 14 principles, and Sheaf Cohomology.
"""

import os
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from chronus.service.auth_middleware import (
    AL_HARAS_PRIVILEGES_MATRIX,
    AuthenticatedIdentity,
    Role,
    create_jwt_token,
    get_current_identity,
    require_roles,
    security as bearer_security,
)
from chronus.service.ciaas_store import (
    ChronusCapacityEntitlement,
    HermitenSettlement,
    PricingBreakdown,
    TenantProfile,
    ciaas_store,
)
from chronus.service.instant_provisioning import (
    CapacityExpansionRequest,
    CapacityExpansionResponse,
    EnduringAddendumError,
    InstantOnboardRequest,
    InstantOnboardResponse,
    LoadSimulationRequest,
    LoadSimulationResponse,
    ProvisioningConflictError,
    TenantCapacityStatusResponse,
    instant_provisioning_engine,
    verify_webhook_hmac_signature,
)

router = APIRouter(prefix="/v1", tags=["ciaas"])


class OnboardTenantRequest(BaseModel):
    tenant_id: str = Field(..., description="Unique tenant identifier e.g. tenant-acme")
    organization_name: str = Field(..., description="Legal entity name")
    admin_email: str = Field(..., description="Lead administrative contact")
    regional_pod: str = Field(default="alpha", description="Primary regional execution pod")
    cce: Optional[ChronusCapacityEntitlement] = None
    sovereign_profile_enabled: bool = True


class TokenRequest(BaseModel):
    tenant_id: str = Field(default="tenant-default")
    user_id: str = Field(default="user-dev-01")
    role: str = Field(default="developer", description="system_admin, tenant_admin, developer, external_auditor")
    expires_in_seconds: int = Field(default=86400)


class SettlementRequest(BaseModel):
    counterfactual_cost: int = Field(default=120000, description="Counterfactual legacy GPU cost in USD")
    actual_cost: int = Field(default=28000, description="Actual Chronus QiGPU cost in USD")
    incremental_cost: int = Field(default=4000, description="Pipeline overhead in USD")


@router.get(
    "/auth/rbac/matrix",
    summary="AL HARAS Enterprise RBAC & Privileges Matrix",
    description="Inspect the 4-tier role authority matrix, administrative scopes, and execution privileges.",
)
async def get_rbac_matrix() -> Dict[str, Any]:
    return {
        "authority": "AL HARAS Sovereign Governance Authority",
        "standard": "Multi-Tenant Enterprise Isolation & Zero-Trust Key Custody",
        "role_tiers": AL_HARAS_PRIVILEGES_MATRIX,
    }


@router.post(
    "/auth/token",
    summary="Mint scoped JWT access token",
    description="Generate a signed JWT bearer token with specific AL HARAS role claims.",
)
async def issue_token(request: TokenRequest) -> Dict[str, Any]:
    try:
        role_enum = Role(request.role.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown role '{request.role}'. Allowed: {[r.value for r in Role]}",
        )
    token = create_jwt_token(
        tenant_id=request.tenant_id,
        user_id=request.user_id,
        role=role_enum,
        expires_in_seconds=request.expires_in_seconds,
    )
    return {
        "access_token": token,
        "token_type": "Bearer",
        "tenant_id": request.tenant_id,
        "user_id": request.user_id,
        "role": request.role,
        "expires_in_seconds": request.expires_in_seconds,
    }


@router.get(
    "/tenants",
    response_model=List[TenantProfile],
    summary="List all onboarded enterprise tenants",
    description="Retrieve all tenant profiles under AL HARAS authority.",
)
async def list_tenants() -> List[TenantProfile]:
    return ciaas_store.list_tenants()


@router.post(
    "/tenants/onboard",
    response_model=TenantProfile,
    status_code=status.HTTP_201_CREATED,
    summary="Onboard new enterprise tenant",
)
async def onboard_tenant(request: OnboardTenantRequest) -> TenantProfile:
    existing = ciaas_store.get_tenant(request.tenant_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tenant '{request.tenant_id}' already exists.",
        )
    profile = ciaas_store.onboard_tenant(
        tenant_id=request.tenant_id,
        organization_name=request.organization_name,
        admin_email=request.admin_email,
        regional_pod=request.regional_pod,
        cce=request.cce,
        sovereign_profile_enabled=request.sovereign_profile_enabled,
    )
    return profile


async def _authorize_instant_ingress(
    http_request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_security),
) -> AuthenticatedIdentity:
    """Authorize Stage 1 ingress via SYSTEM_ADMIN Bearer token or HMAC webhook signature."""
    sig_header = (
        http_request.headers.get("X-Chronus-Webhook-Signature")
        or http_request.headers.get("X-DocuSign-Signature-1")
        or http_request.headers.get("X-Ironclad-Signature")
    )
    if sig_header:
        raw_body = await http_request.body()
        if verify_webhook_hmac_signature(raw_body, sig_header):
            return AuthenticatedIdentity(
                tenant_id="chronus-system-webhook",
                user_id="clm-webhook-ingress",
                roles={Role.SYSTEM_ADMIN},
                claims={"sub": "clm-webhook-ingress", "webhook_verified": True},
                is_jwt=False,
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "invalid_webhook_signature",
                "message": "Cryptographic webhook HMAC signature verification failed.",
            },
        )

    configured_sys_token = os.getenv("CHRONUS_SYSTEM_ADMIN_TOKEN", "").strip()
    if (
        credentials is not None
        and configured_sys_token
        and credentials.credentials == configured_sys_token
    ):
        return AuthenticatedIdentity(
            tenant_id="chronus-system-root",
            user_id="system-admin-token",
            roles={Role.SYSTEM_ADMIN},
            claims={"sub": "system-admin-token"},
            is_jwt=False,
        )

    identity = get_current_identity(request=http_request, credentials=credentials)
    if not identity.has_any_role({Role.SYSTEM_ADMIN, Role.ADMIN}):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "insufficient_permissions",
                "message": "Instant tenant provisioning requires system_admin authority or signed CLM webhook.",
                "current_roles": [r.value for r in identity.roles],
            },
        )
    return identity


@router.post(
    "/tenants/onboard/instant",
    response_model=InstantOnboardResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Zero-Friction Instant Automated Tenant Onboarding (< 30s T0 SLA)",
    description=(
        "Executes all 4 stages of the Chronus CIaaS Instant Provisioning Engine: "
        "MSA webhook ingress validation, PostgreSQL REPEATABLE READ & OVID/THESEUS "
        "fabric initialization, AL HARAS PKCS#11 KMS key custody binding, and "
        "Enduring Capacity Addendum (ECA) activation."
    ),
)
async def instant_onboard_tenant(
    payload: InstantOnboardRequest,
    _admin: AuthenticatedIdentity = Depends(_authorize_instant_ingress),
) -> InstantOnboardResponse:
    try:
        return await run_in_threadpool(
            instant_provisioning_engine.provision_instant_tenant,
            payload,
        )
    except ProvisioningConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "tenant_or_contract_conflict", "message": str(exc)},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_provisioning_request", "message": str(exc)},
        ) from exc


@router.post(
    "/tenants/onboard/instant/load-test",
    response_model=LoadSimulationResponse,
    summary="Simulate concurrent Zero-Friction tenant activations (up to 1000 tenants)",
)
async def simulate_instant_onboarding_load(
    sim_request: LoadSimulationRequest,
    _admin: AuthenticatedIdentity = Depends(_authorize_instant_ingress),
) -> LoadSimulationResponse:
    return await run_in_threadpool(
        instant_provisioning_engine.simulate_concurrent_activations,
        sim_request,
    )


@router.get(
    "/tenants/{tenant_id}",
    response_model=TenantProfile,
    summary="Retrieve tenant profile and CCE status",
)
async def get_tenant_profile(tenant_id: str) -> TenantProfile:
    tenant = ciaas_store.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{tenant_id}' not found.",
        )
    return tenant


@router.get(
    "/tenants/{tenant_id}/capacity",
    response_model=TenantCapacityStatusResponse,
    summary="Inspect Enduring Capacity Addendum (ECA), active warps, and Hermiten settlement",
)
async def get_tenant_capacity_status(tenant_id: str) -> TenantCapacityStatusResponse:
    try:
        return instant_provisioning_engine.get_capacity_status(tenant_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{tenant_id}' not found.",
        ) from exc


@router.patch(
    "/tenants/{tenant_id}/capacity",
    response_model=CapacityExpansionResponse,
    summary="Dynamic Self-Service Capacity Expansion (No Addendum Required)",
    description=(
        "Adjusts active 32-lane execution warps, OVID/THESEUS storage limits, and O(1) "
        "structural memory allocations in real time under the Enduring Capacity Addendum "
        "(ECA), automatically reconciling Hermiten 25% Value-Share settlement."
    ),
)
async def expand_tenant_capacity(
    tenant_id: str,
    request: CapacityExpansionRequest,
    identity: AuthenticatedIdentity = Depends(
        require_roles(Role.TENANT_ADMIN, Role.SYSTEM_ADMIN)
    ),
) -> CapacityExpansionResponse:
    is_sys_admin = identity.has_any_role({Role.SYSTEM_ADMIN, Role.ADMIN})
    if not is_sys_admin and identity.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "tenant_isolation_violation",
                "message": (
                    f"Tenant Admin for '{identity.tenant_id}' cannot modify "
                    f"capacity for tenant '{tenant_id}'."
                ),
            },
        )
    try:
        return await run_in_threadpool(
            instant_provisioning_engine.expand_capacity,
            tenant_id,
            request,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "tenant_not_found", "message": f"Tenant '{tenant_id}' not found."},
        ) from exc
    except EnduringAddendumError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "enduring_addendum_constraint",
                "message": str(exc),
                "additional_approval_required": True,
            },
        ) from exc


@router.post(
    "/tenants/{tenant_id}/cce",
    response_model=TenantProfile,
    summary="Update Chronus Capacity Entitlements (CCE)",
)
async def update_tenant_cce(
    tenant_id: str,
    cce: ChronusCapacityEntitlement,
) -> TenantProfile:
    updated = ciaas_store.update_cce(tenant_id, cce)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{tenant_id}' not found.",
        )
    return updated


@router.get(
    "/tenants/{tenant_id}/pricing",
    response_model=PricingBreakdown,
    summary="Calculate 4-part pricing breakdown",
)
async def get_pricing_breakdown(tenant_id: str, consumed_ccu: int = 128) -> PricingBreakdown:
    return ciaas_store.calculate_pricing(tenant_id=tenant_id, consumed_ccu=consumed_ccu)


@router.post(
    "/tenants/{tenant_id}/settlement",
    response_model=HermitenSettlement,
    summary="Hermiten 25% value-share settlement reconciliation",
)
async def reconcile_settlement(
    tenant_id: str,
    request: SettlementRequest,
) -> HermitenSettlement:
    return ciaas_store.calculate_hermiten_settlement(
        tenant_id=tenant_id,
        counterfactual_cost=request.counterfactual_cost,
        actual_cost=request.actual_cost,
        incremental_cost=request.incremental_cost,
    )


@router.get(
    "/fabric/pods",
    summary="Disaggregated hyperscale fleet pods status",
    description="Inspect Pods alpha..delta, DEC Lie-Poisson routing, and DSW 4D Instanton Self-Healer.",
)
async def get_fabric_pods() -> Dict[str, Any]:
    return ciaas_store.get_pods_fleet()


@router.get(
    "/governance/sovereign",
    summary="Sovereign governance, NCSC 14, and Sheaf Cohomology status",
)
async def get_sovereign_governance() -> Dict[str, Any]:
    return ciaas_store.get_sovereign_profile()

