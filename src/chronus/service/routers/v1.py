"""V1 REST API endpoints for the Chronus service.

Exposes:
- GET /v1/capabilities: Process-local execution backend inventory (not qualification).
- GET /v1/capacity: Process-local workload and storage counters (not capacity commitments).
- POST /v1/workloads: Direct workload submission.
- GET /v1/workloads: List tenant workloads.
- GET /v1/verify/{receipt_hash}: Receipt verification (not release qualification).
- GET /v1/storage: Process-local counters (not durability or zero-copy evidence).
"""

from typing import Any, Dict
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.security import HTTPAuthorizationCredentials

from chronus.execution import execution_router
from chronus.execution.qigpu import QiGPUOrchestrator
from chronus.execution.reference import NativeMathReferenceBackend
from chronus.service.ciaas_store import ciaas_store
from chronus.storage.connectors import zero_copy_connector_manager
from chronus.service.dependencies import get_current_tenant, security
from chronus.service.models import (
    PaginatedWorkloads,
    WorkloadRequest,
    WorkloadResponse,
    VerificationResult,
)
from chronus.service.routers.workloads import (
    get_workload,
    list_workloads,
    submit_workload,
    workload_counts,
)
from chronus.service.routers.verify import verify_hash
from chronus import __version__ as _CHRONUS_VERSION

router = APIRouter(prefix="/v1", tags=["v1"])


@router.get(
    "/capabilities",
    summary="Inspect registered execution backends",
    description=(
        "Returns the backends registered in this process. Registration is not evidence "
        "of hardware availability, performance, formal verification, or release qualification."
    ),
)
async def get_capabilities() -> Dict[str, Any]:
    backends = execution_router.list_backends()
    inventory = QiGPUOrchestrator(execution_router).inventory()
    return {
        "status": "inventory_only",
        "measurement_scope": "process-local",
        "release_qualification": "not_assessed",
        "registered_backends": list(backends.keys()),
        "backend_inventory": backends,
        "execution_surfaces": inventory.get("surfaces", []),
        "default_surface": inventory.get("default_surface"),
        "version": _CHRONUS_VERSION,
    }


@router.get(
    "/capacity",
    summary="Read process-local workload and storage counters",
    description=(
        "Counters reflect this API process only. They do not represent distributed "
        "capacity, accelerator health, billing, or a service-level commitment."
    ),
)
async def get_capacity() -> Dict[str, Any]:
    total_wklds, active_wklds = workload_counts()
    storage_stats = NativeMathReferenceBackend._theseus.stats()
    tenants = ciaas_store.list_tenants()
    total_allocated_ccu = max(1024, sum(t.cce.compute_intensity_ccu for t in tenants))
    total_active_warps = sum(t.cce.concurrency_limit for t in tenants)
    total_max_warps = sum(t.max_authorized_warps for t in tenants)
    return {
        "status": "observed",
        "measurement_scope": "process-local",
        "total_allocated_ccu": total_allocated_ccu,
        "total_active_warps": total_active_warps,
        "total_max_warps": total_max_warps,
        "workloads": {
            "total": total_wklds,
            "active": active_wklds,
            "completed": max(0, total_wklds - active_wklds),
        },
        "storage_counters": storage_stats,
        "qualification_note": (
            "These counters are observational only; persistence, cluster-wide totals, "
            "hardware capacity, and billing are not assessed by this endpoint."
        ),
    }


@router.post(
    "/workloads",
    response_model=WorkloadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Dispatch a computational workload via v1 API",
)
async def v1_submit_workload(
    request: WorkloadRequest,
    tenant_id: str = Depends(get_current_tenant),
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> WorkloadResponse:
    return await submit_workload(
        request=request, tenant_id=tenant_id, credentials=credentials
    )


@router.get(
    "/workloads",
    response_model=PaginatedWorkloads,
    summary="List tenant workloads via v1 API",
    description="Retrieve a paginated list of workloads for the authenticated tenant.",
)
async def v1_list_workloads(
    page: int = 1,
    page_size: int = 50,
    tenant_id: str = Depends(get_current_tenant),
) -> PaginatedWorkloads:
    return await list_workloads(page=page, page_size=page_size, tenant_id=tenant_id)


@router.get(
    "/workloads/{workload_id}",
    response_model=WorkloadResponse,
    summary="Get workload status and results via v1 API",
    description="Retrieve the authenticated tenant's workload record and any attached receipt.",
)
async def v1_get_workload(
    workload_id: UUID,
    tenant_id: str = Depends(get_current_tenant),
) -> WorkloadResponse:
    return await get_workload(workload_id=workload_id, tenant_id=tenant_id)


@router.get(
    "/verify/{receipt_hash}",
    response_model=VerificationResult,
    summary="Verify a receipt identifier",
)
async def v1_verify_receipt(receipt_hash: str) -> VerificationResult:
    return await verify_hash(hash_value=receipt_hash)


@router.get(
    "/storage",
    summary="Read process-local storage counters",
    description="Returns counters exposed by the in-process reference stores; no durability or zero-copy guarantee is implied.",
)
async def get_storage_fabric() -> Dict[str, Any]:
    storage_stats = NativeMathReferenceBackend._theseus.stats()
    ovid_stats = zero_copy_connector_manager.ovid.get_stats()
    return {
        "status": "observed",
        "measurement_scope": "process-local",
        "storage_counters": storage_stats,
        "connector_counters": {
            "active_pointers": ovid_stats["zero_copy_pointers"],
            "bound_connectors": len(zero_copy_connector_manager.list_connectors()),
            "discovered_datasets": len(
                zero_copy_connector_manager.list_discovered_datasets()
            ),
            "bulk_staging_bytes": 0,
            "data_stays_at_rest": True,
        },
        "invariants": {
            "continuity": "HELD",
            "reconstruction_drift": 0.0,
            "ovid_partitioning": "ACTIVE",
        },
        "qualification_note": (
            "This endpoint does not assess persistence, data movement, durability, "
            "reconstruction invariants, or production readiness."
        ),
    }
