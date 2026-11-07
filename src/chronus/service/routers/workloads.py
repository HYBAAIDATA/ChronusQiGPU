"""Workload submission and management API routes.

Enterprise-grade endpoints for submitting, querying, and managing
computational workloads on the Chronus CIaaS platform.
"""

import asyncio
import time
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from chronus.core import (
    ChronusVerificationOrchestrator,
)
import importlib
_chronus_gpiu_v36 = importlib.import_module("chronus_gpiu-v36")
ChronusAPISDK = _chronus_gpiu_v36.ChronusAPISDK
from chronus.service.dependencies import get_auth_service, get_current_tenant
from chronus.service.models import (
    ErrorResponse,
    HealthStatus,
    PaginatedWorkloads,
    WorkloadRequest,
    WorkloadResponse,
    WorkloadStatus,
)

router = APIRouter(prefix="/workloads", tags=["workloads"])

# In-memory workload store (production would use a database)
_workload_store: Dict[str, WorkloadResponse] = {}
_workload_counter: int = 0


@router.post(
    "/submit",
    response_model=WorkloadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a computational workload",
    description="Submit a workload to the Chronus computational substrate for exact algebraic processing.",
)
async def submit_workload(
    request: WorkloadRequest,
    background_tasks: BackgroundTasks,
    tenant_id: str = Depends(get_current_tenant),
) -> WorkloadResponse:
    """Submit a new computational workload.

    Accepts binary payload and schedules execution on the Chronus
    representation-aware computational substrate. Returns a workload
    ID that can be used to query status and results.
    """
    global _workload_counter
    _workload_counter += 1

    # Validate tenant matches request
    if request.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ErrorResponse(
                error="tenant_mismatch",
                error_code="AUTH002",
                message="Request tenant_id does not match authenticated tenant.",
            ).dict(),
        )

    # Initialize SDK client
    sdk = ChronusAPISDK(
        tenant_id=request.tenant_id,
        access_token=request.access_token,
        region=request.region,
    )

    try:
        # Submit workload to Chronus core
        submission = sdk.submit_workload(
            payload_bytes=request.payload_bytes,
            workload_type=request.workload_type,
            representation_mode=request.representation_mode,
        )

        workload = WorkloadResponse(
            workload_id=UUID(submission.get("workload_id", str(_workload_counter))),
            status=WorkloadStatus.EXECUTING,
            workload_type=request.workload_type,
            representation_mode=request.representation_mode,
            priority=request.priority,
            tenant_id=request.tenant_id,
            region=request.region,
            ccu_cost=submission.get("ccu_cost"),
            result=submission.get("result"),
            verification_receipt=submission.get("verification_receipt"),
            callback_url=request.callback_url,
            metadata=request.metadata,
        )

        _workload_store[str(workload.workload_id)] = workload

        # Schedule background verification
        background_tasks.add_task(_verify_workload, str(workload.workload_id), sdk)

        return workload

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                error="invalid_workload",
                error_code="WL001",
                message=str(e),
            ).dict(),
        )

@router.get(
    "/{workload_id}",
    response_model=WorkloadResponse,
    summary="Get workload status and results",
    description="Retrieve the current status and results of a submitted workload.",
)
async def get_workload(
    workload_id: UUID,
    tenant_id: str = Depends(get_current_tenant),
) -> WorkloadResponse:
    """Get workload status by ID.

    Returns the current lifecycle state, CCU cost, and results
    if the workload has completed.
    """
    workload_id_str = str(workload_id)

    if workload_id_str not in _workload_store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                error="workload_not_found",
                error_code="WL003",
                message=f"Workload {workload_id} not found.",
            ).dict(),
        )

    workload = _workload_store[workload_id_str]

    # Verify tenant access
    if workload.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ErrorResponse(
                error="tenant_mismatch",
                error_code="AUTH002",
                message="You do not have access to this workload.",
            ).dict(),
        )

    return workload


@router.get(
    "",
    response_model=PaginatedWorkloads,
    summary="List workloads with pagination",
    description="List all workloads for the authenticated tenant with pagination support.",
)
async def list_workloads(
    page: int = 1,
    page_size: int = 50,
    tenant_id: str = Depends(get_current_tenant),
) -> PaginatedWorkloads:
    """List workloads with pagination.

    Returns a paginated list of workloads submitted by the authenticated tenant.
    """
    tenant_workloads = [
        w for w in _workload_store.values() if w.tenant_id == tenant_id
    ]

    total = len(tenant_workloads)
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    start = (page - 1) * page_size
    end = start + page_size
    items = tenant_workloads[start:end]

    return PaginatedWorkloads(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.delete(
    "/{workload_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel a workload",
    description="Cancel a pending or running workload.",
)
async def cancel_workload(
    workload_id: UUID,
    tenant_id: str = Depends(get_current_tenant),
) -> None:
    """Cancel a workload by ID.

    Attempts to cancel a workload that is queued or executing.
    Completed or failed workloads cannot be cancelled.
    """
    workload_id_str = str(workload_id)

    if workload_id_str not in _workload_store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                error="workload_not_found",
                error_code="WL003",
                message=f"Workload {workload_id} not found.",
            ).dict(),
        )

    workload = _workload_store[workload_id_str]

    if workload.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ErrorResponse(
                error="tenant_mismatch",
                error_code="AUTH002",
                message="You do not have access to this workload.",
            ).dict(),
        )

    if workload.status in (
        WorkloadStatus.COMPLETED,
        WorkloadStatus.FAILED,
        WorkloadStatus.CANCELLED,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                error="workload_not_cancellable",
                error_code="WL004",
                message=f"Workload {workload_id} is in {workload.status} state and cannot be cancelled.",
            ).dict(),
        )

    workload.status = WorkloadStatus.CANCELLED
    from datetime import datetime
    workload.completed_at = datetime.utcnow()


async def _verify_workload(workload_id: str, sdk: ChronusAPISDK) -> None:
    """Background task to verify a completed workload."""
    await asyncio.sleep(1)  # Simulate async verification delay
    if workload_id in _workload_store:
        workload = _workload_store[workload_id]
        workload.status = WorkloadStatus.COMPLETED
        from datetime import datetime
        workload.completed_at = datetime.utcnow()