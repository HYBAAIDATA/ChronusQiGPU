"""Workload submission and management API routes."""

from datetime import datetime
from datetime import timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from starlette.concurrency import run_in_threadpool

from chronus.backends.lattice import (
    HardwareUnavailableError,
    LatticeOverflowError,
    ParityVerificationError,
)
from chronus.execution import execution_router
from chronus.sdk.client import ChronusAPISDK, ChronusSDKError
from chronus.service.dependencies import get_current_tenant, security, service_config
from chronus.service.models import (
    ErrorResponse,
    PaginatedWorkloads,
    WorkloadRequest,
    WorkloadResponse,
    WorkloadStatus,
)
from chronus.service.workload_store import SQLiteWorkloadStore

router = APIRouter(prefix="/workloads", tags=["workloads"])

workload_store = SQLiteWorkloadStore()


def workload_counts() -> tuple[int, int]:
    return workload_store.counts()


@router.post(
    "/submit",
    response_model=WorkloadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a computational workload",
    description="Submit a workload to the Chronus computational substrate for exact algebraic processing.",
)
async def submit_workload(
    request: WorkloadRequest,
    tenant_id: str = Depends(get_current_tenant),
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> WorkloadResponse:
    """Execute on the mathematical reference backend or a configured adapter."""
    if request.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ErrorResponse(
                error="tenant_mismatch",
                error_code="AUTH002",
                message="Request tenant_id does not match authenticated tenant.",
            ).model_dump(),
        )

    try:
        if service_config.execution_backend_url:
            sdk = ChronusAPISDK(
                tenant_id=request.tenant_id,
                access_token=credentials.credentials,
                region=request.region,
                base_url=service_config.execution_backend_url,
            )
            try:
                submission = await run_in_threadpool(
                    sdk.submit_workload,
                    payload_bytes=request.payload_bytes,
                    workload_type=request.workload_type,
                    representation_mode=request.representation_mode,
                    priority=request.priority,
                    callback_url=request.callback_url,
                    metadata=request.metadata,
                    backend_preference=request.backend_preference,
                )
            finally:
                sdk.close()
            workload_id = submission.get("workload_id")
            if not workload_id:
                raise ChronusSDKError(
                    "Execution adapter returned no workload ID",
                    status_code=502,
                    response=submission,
                )
            parsed_id = UUID(workload_id)
            backend_status = WorkloadStatus(submission["status"])
            result = submission.get("result")
            receipt = submission.get("verification_receipt")
            ccu_cost = submission.get("ccu_cost")
        else:
            execution = await run_in_threadpool(
                execution_router.execute,
                request.payload_bytes,
                request.workload_type,
                request.backend_preference,
            )
            parsed_id = uuid4()
            backend_status = WorkloadStatus.COMPLETED
            result = execution.to_dict()
            receipt = None
            ccu_cost = None
    except (ValueError, LatticeOverflowError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                error="invalid_or_unsupported_workload",
                error_code="WL001",
                message=str(exc),
            ).model_dump(),
        ) from exc
    except ChronusSDKError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=ErrorResponse(
                error="execution_adapter_error",
                error_code="EXE002",
                message="Chronus accelerator adapter rejected or could not process the workload.",
            ).model_dump(),
        ) from exc
    except HardwareUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorResponse(
                error="accelerator_unavailable",
                error_code="EXE003",
                message="The selected accelerator could not execute the workload.",
            ).model_dump(),
        ) from exc
    except ParityVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=ErrorResponse(
                error="accelerator_parity_failure",
                error_code="EXE004",
                message="Accelerator result failed exact parity verification.",
            ).model_dump(),
        ) from exc

    workload = WorkloadResponse(
        workload_id=parsed_id,
        status=backend_status,
        workload_type=request.workload_type,
        representation_mode=request.representation_mode,
        priority=request.priority,
        tenant_id=request.tenant_id,
        region=request.region,
        ccu_cost=ccu_cost,
        result=result,
        verification_receipt=receipt,
        callback_url=request.callback_url,
        metadata=request.metadata,
        completed_at=(
            datetime.now(timezone.utc)
            if backend_status == WorkloadStatus.COMPLETED
            else None
        ),
    )
    workload_store.save(workload)
    return workload

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

    workload = workload_store.get(workload_id_str)
    if workload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                error="workload_not_found",
                error_code="WL003",
                message=f"Workload {workload_id} not found.",
            ).model_dump(),
        )

    # Verify tenant access
    if workload.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ErrorResponse(
                error="tenant_mismatch",
                error_code="AUTH002",
                message="You do not have access to this workload.",
            ).model_dump(),
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
    if page < 1 or page_size < 1 or page_size > 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=ErrorResponse(
                error="invalid_pagination",
                error_code="WL005",
                message="page must be positive and page_size must be between 1 and 100.",
            ).model_dump(),
        )
    items, total = workload_store.list_for_tenant(
        tenant_id, offset=(page - 1) * page_size, limit=page_size
    )
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

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

    workload = workload_store.get(workload_id_str)
    if workload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                error="workload_not_found",
                error_code="WL003",
                message=f"Workload {workload_id} not found.",
            ).model_dump(),
        )

    if workload.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ErrorResponse(
                error="tenant_mismatch",
                error_code="AUTH002",
                message="You do not have access to this workload.",
            ).model_dump(),
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
            ).model_dump(),
        )

    workload.status = WorkloadStatus.CANCELLED
    workload.completed_at = datetime.now(timezone.utc)
    workload_store.save(workload)