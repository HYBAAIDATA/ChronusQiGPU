"""OpenAPI endpoints for CIaaS multi-tenancy, AL HARAS RBAC, and commercial settlement.

Exposes:
- GET  /v1/auth/rbac/matrix: Returns the AL HARAS 4-tier privileges matrix.
- POST /v1/auth/token: Mints a scoped JWT token for testing/API access.
- GET  /v1/tenants: Lists onboarded enterprise tenants.
- POST /v1/tenants/onboard: Onboards a new tenant and provisions CCE quotas.
- GET  /v1/tenants/{tenant_id}: Retrieves tenant profile and CCE allocations.
- POST /v1/tenants/{tenant_id}/cce: Updates 5-dimension CCE quotas.
- GET  /v1/tenants/{tenant_id}/pricing: Four-part pricing breakdown (P_total).
- POST /v1/tenants/{tenant_id}/settlement: Reconciles Hermiten 25% value-share settlement.
- GET  /v1/fabric/pods: Disaggregated regional fleet pods (alpha..delta) and DEC routing.
- GET  /v1/governance/sovereign: Sovereign profile, NCSC 14 principles, and Sheaf Cohomology.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from chronus.service.auth_middleware import (
    AL_HARAS_PRIVILEGES_MATRIX,
    AuthenticatedIdentity,
    Role,
    create_jwt_token,
    get_current_identity,
    require_roles,
)
from chronus.service.ciaas_store import (
    ChronusCapacityEntitlement,
    HermitenSettlement,
    PricingBreakdown,
    TenantProfile,
    ciaas_store,
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
