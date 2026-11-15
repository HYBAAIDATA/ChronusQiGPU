from fastapi import APIRouter, Depends, Query, Response

from chronus.service.api import store
from chronus.service.api.errors import ApiError
from chronus.service.api.idempotency import Guard, idempotency_guard
from chronus.service.api.lease import current_lease
from chronus.service.api.pagination import clamp_limit, decode_cursor, encode_cursor
from chronus.service.api.schemas import (
    Lease, Receipt, Workload, WorkloadCreate, WorkloadPage, WorkloadState,
)
from chronus.service.api.security import Principal, require

router = APIRouter()


@router.post("", status_code=202, response_model=Workload,
             summary="Submit a workload", responses={403: {}, 409: {}, 428: {}})
async def create(
    payload: WorkloadCreate,
    response: Response,
    principal: Principal = Depends(require("workloads:write")),
    lease: Lease = Depends(current_lease),
    guard: Guard = Depends(idempotency_guard),
):
    # Entitlements are optional; empty means unrestricted.
    if lease.entitlements and payload.kind.value not in lease.entitlements:
        raise ApiError(403, "kind_not_entitled", "Not entitled to this workload kind",
                       f"Lease permits {sorted(lease.entitlements)}.")

    workload, replayed = guard.create_workload(payload)
    headers = {"Location": f"/v1/workloads/{workload.id}"}
    response.headers.update(headers)
    if replayed:
        response.headers["Idempotent-Replay"] = "true"
    return workload


@router.get("", response_model=WorkloadPage, summary="List your workloads")
async def list_own(
    limit: int | None = Query(default=None, ge=1, le=100),
    cursor: str | None = Query(default=None),
    state: WorkloadState | None = Query(default=None),
    principal: Principal = Depends(require("workloads:read")),
):
    items, next_cursor = store.list_workloads(
        principal.tenant_id, clamp_limit(limit), decode_cursor(cursor),
        state.value if state else None,
    )
    return WorkloadPage(items=items,
                        next_cursor=encode_cursor(next_cursor) if next_cursor else None)


@router.get("/{workload_id}", response_model=Workload, summary="Get one workload")
async def get_one(workload_id: str,
                  principal: Principal = Depends(require("workloads:read"))):
    return store.get_workload(principal.tenant_id, workload_id)


@router.delete("/{workload_id}", status_code=202, response_model=Workload,
               summary="Request cancellation")
async def cancel(workload_id: str,
                 principal: Principal = Depends(require("workloads:write"))):
    return store.cancel_workload(principal.tenant_id, workload_id)


@router.get("/{workload_id}/receipt", response_model=Receipt, summary="Receipt for a run")
async def receipt(workload_id: str,
                  principal: Principal = Depends(require("workloads:read"))):
    return store.get_receipt_for_workload(principal.tenant_id, workload_id)
